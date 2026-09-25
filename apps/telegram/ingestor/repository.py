"""Synchronous, transactional writes for the ingestor (called via `sync_to_async`, ARCHITECTURE §3.2).

One transaction = post upsert + media rows; `finalize_post` writes the outbox event in the same transaction as
the final content hash. Posts are never physically deleted (FR-TG-11).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.telegram.ingestor.dto import TelegramMessageDTO
from apps.telegram.ingestor.normalize import compute_content_hash
from apps.telegram.models import (
    IngestionOutbox,
    MediaStatus,
    OutboxEventType,
    ProcessingStatus,
    TelegramMedia,
    TelegramPost,
    TelegramSource,
)

log = structlog.get_logger(__name__)

DOWNLOADABLE_KINDS = frozenset({"photo", "video", "document", "audio", "voice", "animation"})
METADATA_ONLY_ERROR = "metadata_only"
DELETED_MEDIA_ERROR = "deleted_in_telegram"
BACKFILL_SKIP_REASON = "backfill_beyond_ai_limit"


@dataclass(frozen=True)
class UpsertResult:
    post_id: int
    created: bool
    pending_media_ids: tuple[int, ...]


@dataclass(frozen=True)
class MediaTask:
    """Everything the downloader needs for one media row."""

    media_id: int
    message_id: int
    order: int
    kind: str
    size_bytes: int | None
    extension: str
    username: str
    published_at: datetime


def _find_post(source_id: int, dto: TelegramMessageDTO) -> TelegramPost | None:
    base = TelegramPost.objects.select_for_update()
    if dto.grouped_id is not None:
        post = base.filter(source_id=source_id, grouped_id=dto.grouped_id).first()
        if post:
            return post
    post = base.filter(source_id=source_id, telegram_message_id__in=dto.all_message_ids).first()
    if post:
        return post
    media = (
        TelegramMedia.objects.filter(post__source_id=source_id, telegram_message_id__in=dto.all_message_ids)
        .values_list("post_id", flat=True)
        .first()
    )
    return base.filter(pk=media).first() if media else None


def _post_fields(dto: TelegramMessageDTO) -> dict[str, object]:
    return {
        "entities": dto.entities,
        "links": dto.links,
        "hashtags": dto.hashtags,
        "edited_at": dto.edited_at,
        "views": dto.views,
        "forwards": dto.forwards,
        "reactions": dto.reactions,
        "reply_to_id": dto.reply_to_id,
        "is_forwarded": dto.is_forwarded,
        "forward_from": dto.forward_from,
        "raw_json": dto.raw,
    }


@transaction.atomic
def upsert_post(source_id: int, dto: TelegramMessageDTO, *, is_backfill: bool = False) -> UpsertResult:
    """Create or update a post and its media rows. Idempotent for repeated updates of the same message."""
    post = _find_post(source_id, dto)
    created = post is None
    if post is None:
        try:
            with transaction.atomic():
                post = TelegramPost.objects.create(
                    source_id=source_id,
                    telegram_message_id=dto.message_id,
                    grouped_id=dto.grouped_id,
                    text=dto.text,
                    published_at=dto.published_at,
                    telegram_url=dto.url,
                    is_backfill=is_backfill,
                    **_post_fields(dto),
                )
        except IntegrityError:  # concurrent insert of the same message/album — update instead
            created = False
            post = _find_post(source_id, dto)
            if post is None:
                raise
    if not created:
        if dto.text or not post.text:
            post.text = dto.text
        for name, value in _post_fields(dto).items():
            setattr(post, name, value)
        if dto.message_id < post.telegram_message_id:
            post.telegram_message_id = dto.message_id
            post.telegram_url = dto.url
        post.published_at = min(post.published_at, dto.published_at)
        post.grouped_id = post.grouped_id or dto.grouped_id
        post.save()

    for item in dto.media:
        defaults = {
            "order": item.order,
            "kind": item.kind,
            "telegram_file_id": item.file_id,
            "mime_type": item.mime_type,
            "size_bytes": item.size_bytes,
            "width": item.width,
            "height": item.height,
            "duration_seconds": item.duration_seconds,
            "caption": item.caption,
        }
        if item.kind not in DOWNLOADABLE_KINDS:
            defaults.update(status=MediaStatus.FAILED, error=METADATA_ONLY_ERROR)
        media, media_created = TelegramMedia.objects.get_or_create(
            post=post, telegram_message_id=item.message_id, defaults=defaults
        )
        if not media_created and media.telegram_file_id != item.file_id:  # media replaced by an edit
            for name, value in defaults.items():
                setattr(media, name, value)
            if item.kind in DOWNLOADABLE_KINDS:
                media.status, media.error, media.original, media.derivatives = MediaStatus.PENDING, "", "", {}
            media.save()
        elif not media_created and item.order != media.order:
            media.order = item.order
            media.save(update_fields=["order", "updated_at"])

    live_media = post.media.exclude(error=DELETED_MEDIA_ERROR)
    post.media_count = live_media.count()
    post.has_media = post.media_count > 0
    post.save(update_fields=["media_count", "has_media", "updated_at"])
    pending = tuple(
        live_media.filter(status=MediaStatus.PENDING, kind__in=DOWNLOADABLE_KINDS).values_list(
            "pk", flat=True
        )
    )
    return UpsertResult(post_id=post.pk, created=created, pending_media_ids=pending)


def media_tasks(media_ids: Iterable[int]) -> list[MediaTask]:
    rows = (
        TelegramMedia.objects.filter(pk__in=list(media_ids)).select_related("post__source").order_by("order")
    )
    return [
        MediaTask(
            media_id=m.pk,
            message_id=m.telegram_message_id,
            order=m.order,
            kind=m.kind,
            size_bytes=m.size_bytes,
            extension=_extension(m),
            username=m.post.source.username,
            published_at=m.post.published_at,
        )
        for m in rows
    ]


def _extension(media: TelegramMedia) -> str:
    from apps.telegram.ingestor.normalize import MIME_EXTENSIONS

    return "jpg" if media.kind == "photo" else MIME_EXTENSIONS.get(media.mime_type, "bin")


def mark_media_downloaded(media_id: int, storage_key: str, size_bytes: int | None = None) -> None:
    """Record a stored original and queue derivative generation after commit."""
    with transaction.atomic():
        update: dict[str, object] = {"original": storage_key, "status": MediaStatus.DOWNLOADED, "error": ""}
        if size_bytes is not None:
            update["size_bytes"] = size_bytes
        TelegramMedia.objects.filter(pk=media_id).update(**update, updated_at=timezone.now())
        transaction.on_commit(lambda: _enqueue_media_processing(media_id))


def _enqueue_media_processing(media_id: int) -> None:
    try:
        from config.celery import app

        app.send_task("media.process_media", args=[media_id], queue="media")
    except Exception:  # broker down — the media retry job picks it up later
        log.warning("media_enqueue_failed", media_id=media_id)


def mark_media_failed(media_id: int, error: str) -> None:
    TelegramMedia.objects.filter(pk=media_id).update(
        status=MediaStatus.FAILED, error=error[:500], updated_at=timezone.now()
    )


def _media_keys(post: TelegramPost) -> list[str]:
    return [
        str(m.telegram_file_id) if m.telegram_file_id else f"{m.kind}:{m.telegram_message_id}"
        for m in post.media.exclude(error=DELETED_MEDIA_ERROR)
    ]


def _nudge_relay() -> None:
    try:
        from config.celery import app

        app.send_task("telegram.relay_outbox", queue="ingest")
    except Exception:  # nudge failures are swallowed — the 10 s beat relay is the guarantee (ADR-003)
        log.info("relay_nudge_failed")


def _add_event(post: TelegramPost, event_type: str, payload_hash: str) -> bool:
    _event, created = IngestionOutbox.objects.get_or_create(
        post=post,
        event_type=event_type,
        payload_hash=payload_hash,
        defaults={"payload": {"post_id": post.pk, "content_hash": post.content_hash,
                              "message_id": post.telegram_message_id}},
    )  # fmt: skip
    if created:
        transaction.on_commit(_nudge_relay)
    return created


@transaction.atomic
def finalize_post(post_id: int, *, emit_event: bool = True) -> str | None:
    """Compute the final content hash and write the outbox event (created/edited). Returns the event type."""
    post = TelegramPost.objects.select_for_update().select_related("source").get(pk=post_id)
    new_hash = compute_content_hash(post.text, _media_keys(post))
    event: str | None = None
    if not post.content_hash:
        event = OutboxEventType.CREATED
    elif post.content_hash != new_hash:
        event = OutboxEventType.EDITED
    post.content_hash = new_hash
    fields = ["content_hash", "updated_at"]
    if event and emit_event and not post.is_deleted:
        if _add_event(post, event, new_hash):
            post.processing_status = ProcessingStatus.QUEUED
            fields.append("processing_status")
    elif event == OutboxEventType.CREATED and not emit_event:
        post.processing_status, post.skip_reason = ProcessingStatus.SKIPPED, BACKFILL_SKIP_REASON
        fields += ["processing_status", "skip_reason"]
    post.save(update_fields=fields)
    TelegramSource.objects.filter(pk=post.source_id).filter(
        Q(last_message_id__isnull=True) | Q(last_message_id__lt=post.telegram_message_id)
    ).update(last_message_id=post.telegram_message_id, last_message_at=post.published_at)
    return event if emit_event else None


@transaction.atomic
def mark_deleted(source_id: int, message_ids: Iterable[int]) -> list[int]:
    """Archive posts whose messages were deleted; partially deleted albums become an edit."""
    ids = set(message_ids)
    if not ids:
        return []
    affected: set[int] = set(
        TelegramPost.objects.filter(source_id=source_id, telegram_message_id__in=ids).values_list(
            "pk", flat=True
        )
    )
    TelegramMedia.objects.filter(post__source_id=source_id, telegram_message_id__in=ids).update(
        status=MediaStatus.FAILED, error=DELETED_MEDIA_ERROR, updated_at=timezone.now()
    )
    affected |= set(
        TelegramMedia.objects.filter(post__source_id=source_id, telegram_message_id__in=ids).values_list(
            "post_id", flat=True
        )
    )
    deleted: list[int] = []
    for post in TelegramPost.objects.select_for_update().filter(pk__in=affected, is_deleted=False):
        if post.grouped_id and post.media.exclude(error=DELETED_MEDIA_ERROR).exists():
            finalize_post(post.pk)  # some album items remain → content changed → `edited` event
            continue
        post.is_deleted, post.deleted_at = True, timezone.now()
        post.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        _add_event(
            post, OutboxEventType.DELETED, hashlib.sha256(f"deleted:{post.content_hash}".encode()).hexdigest()
        )
        deleted.append(post.pk)
    return deleted


@transaction.atomic
def record_gapcheck_window(source_id: int, seen_ids: set[int]) -> list[int]:
    """Two-miss deletion rule (FR-TG-7): ids inside the window's range but absent twice are archived."""
    if not seen_ids:
        return []
    low, high = min(seen_ids), max(seen_ids)
    window = TelegramPost.objects.filter(
        source_id=source_id, is_deleted=False, telegram_message_id__gte=low, telegram_message_id__lte=high
    )
    present_album_posts = set(
        TelegramMedia.objects.filter(post__in=window, telegram_message_id__in=seen_ids).values_list(
            "post_id", flat=True
        )
    )
    missing = window.exclude(telegram_message_id__in=seen_ids).exclude(pk__in=present_album_posts)
    window.filter(Q(telegram_message_id__in=seen_ids) | Q(pk__in=present_album_posts)).update(
        missing_checks=0
    )
    missing.update(missing_checks=F("missing_checks") + 1)
    gone = list(
        TelegramPost.objects.filter(pk__in=missing.values("pk"), missing_checks__gte=2).values_list(
            "telegram_message_id", flat=True
        )
    )
    return mark_deleted(source_id, gone)


def known_message_state(source_id: int, message_ids: Iterable[int]) -> dict[int, datetime | None]:
    """{message_id: edited_at} for posts (and album items) already stored."""
    ids = list(message_ids)
    state: dict[int, datetime | None] = dict(
        TelegramPost.objects.filter(source_id=source_id, telegram_message_id__in=ids).values_list(
            "telegram_message_id", "edited_at"
        )
    )
    for item_id, edited in TelegramMedia.objects.filter(
        post__source_id=source_id, telegram_message_id__in=ids
    ).values_list("telegram_message_id", "post__edited_at"):
        state.setdefault(item_id, edited)
    return state


def update_engagement(
    source_id: int, stats: Iterable[tuple[int, int | None, int | None, dict[str, int]]]
) -> int:
    """Bulk-update views/forwards/reactions; returns the number of posts touched."""
    touched = 0
    with transaction.atomic():
        for message_id, views, forwards, reactions in stats:
            touched += TelegramPost.objects.filter(
                source_id=source_id, telegram_message_id=message_id
            ).update(views=views, forwards=forwards, reactions=reactions, updated_at=timezone.now())
    return touched


def recent_message_ids(source_id: int, days: int = 7) -> list[int]:
    """Message ids of this source's non-deleted posts from the last `days` days (engagement refresh)."""
    since = timezone.now() - timedelta(days=days)
    return list(
        TelegramPost.objects.filter(
            source_id=source_id, is_deleted=False, published_at__gte=since
        ).values_list("telegram_message_id", flat=True)
    )


def media_retry_targets(media_ids: Iterable[int]) -> dict[int, list[tuple[int, int]]]:
    """{source_id: [(media_id, message_id), …]} for failed media that should be downloaded again."""
    targets: dict[int, list[tuple[int, int]]] = {}
    rows = TelegramMedia.objects.filter(pk__in=list(media_ids)).exclude(
        error__in=[METADATA_ONLY_ERROR, DELETED_MEDIA_ERROR]
    )
    for media_id, message_id, source_id in rows.values_list("pk", "telegram_message_id", "post__source_id"):
        targets.setdefault(source_id, []).append((media_id, message_id))
    return targets


def reset_media_for_retry(media_ids: Iterable[int]) -> None:
    TelegramMedia.objects.filter(pk__in=list(media_ids)).update(
        status=MediaStatus.PENDING, error="", updated_at=timezone.now()
    )
