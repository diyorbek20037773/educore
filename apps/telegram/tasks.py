"""Celery tasks for ingestion (CLAUDE.md §11): outbox relay, ingestor requests, media, cleanup."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import structlog
from celery import shared_task
from django.db import connection, transaction
from django.utils import timezone

from apps.ops.services.alerts import send_alert
from apps.telegram.derivatives import process_media as _process_media
from apps.telegram.ingestor.repository import DELETED_MEDIA_ERROR, METADATA_ONLY_ERROR
from apps.telegram.ingestor.source_repository import enqueue_request
from apps.telegram.models import (
    IngestionOutbox,
    IngestionRequest,
    MediaStatus,
    RequestKind,
    RequestStatus,
    SourceStatus,
    TelegramMedia,
    TelegramSource,
)

log = structlog.get_logger(__name__)

PROCESS_POST_TASK = "ai.process_post"
RELAY_BATCH = 50
DISPATCH_LOCK = timedelta(minutes=15)
GAPCHECK_STALE = timedelta(minutes=20)
MEDIA_RETRY_WINDOW = timedelta(days=3)
OUTBOX_RETENTION = timedelta(days=30)

_PICK_SQL = """
WITH picked AS (
    SELECT id FROM telegram_ingestionoutbox
    WHERE processed_at IS NULL AND is_dead = FALSE
      AND (locked_until IS NULL OR locked_until < now())
    ORDER BY created_at
    LIMIT %s
    FOR UPDATE SKIP LOCKED
)
UPDATE telegram_ingestionoutbox o
SET locked_until = now() + %s, updated_at = now()
FROM picked WHERE o.id = picked.id
RETURNING o.id, o.event_type, o.post_id
"""


def _process_post_registered() -> bool:
    from config.celery import app

    return PROCESS_POST_TASK in app.tasks


@shared_task(name="telegram.relay_outbox", ignore_result=True)
def relay_outbox(batch: int = RELAY_BATCH) -> int:
    """Dispatch unprocessed outbox rows to `ai.process_post` (at-least-once; consumers are idempotent)."""
    from config.celery import app

    if not _process_post_registered():
        log.info("relay_outbox_waiting", reason="ai.process_post not registered yet")
        return 0
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(_PICK_SQL, [batch, DISPATCH_LOCK])
        rows = cursor.fetchall()
    dispatched = 0
    for outbox_id, event_type, post_id in rows:
        try:
            app.send_task(PROCESS_POST_TASK, args=[post_id, event_type, str(outbox_id)], queue="ai")
            dispatched += 1
        except Exception as exc:  # broker hiccup: release the lock so the next tick retries
            IngestionOutbox.objects.filter(pk=outbox_id).update(locked_until=None)
            log.warning("relay_outbox_dispatch_failed", outbox_id=str(outbox_id), error=str(exc))
    if dispatched:
        log.info("relay_outbox_dispatched", count=dispatched)
    return dispatched


def renew_outbox_lock(outbox_id: str, minutes: int = 15) -> None:
    """Called every 2 min by a running consumer so the relay never re-dispatches a live task (ADR-011)."""
    IngestionOutbox.objects.filter(pk=outbox_id, processed_at__isnull=True).update(
        locked_until=timezone.now() + timedelta(minutes=minutes)
    )


def _pending_request_exists(kind: str, source_id: int | None = None) -> bool:
    return IngestionRequest.objects.filter(
        kind=kind, source_id=source_id, status__in=[RequestStatus.PENDING, RequestStatus.RUNNING]
    ).exists()


@shared_task(name="telegram.request_gapcheck", ignore_result=True)
def request_gapcheck() -> int:
    """The ingestor gap-checks every 10 min itself; alert (and enqueue) only when that loop is stale."""
    stale_before = timezone.now() - GAPCHECK_STALE
    queued = 0
    for source in TelegramSource.objects.filter(is_active=True, status=SourceStatus.LIVE):
        if source.last_gapcheck_at and source.last_gapcheck_at >= stale_before:
            continue
        send_alert(
            "gapcheck_stale", f"gapcheck_stale:{source.username}",
            f"Gap check for @{source.username} has not run for over 20 minutes.",
        )  # fmt: skip
        if not _pending_request_exists(RequestKind.GAPCHECK, source.pk):
            enqueue_request(RequestKind.GAPCHECK, source.pk)
            queued += 1
    return queued


@shared_task(name="telegram.request_engagement_refresh", ignore_result=True)
def request_engagement_refresh() -> bool:
    if _pending_request_exists(RequestKind.REFRESH_ENGAGEMENT):
        return False
    enqueue_request(RequestKind.REFRESH_ENGAGEMENT)
    return True


@shared_task(name="telegram.request_media_retry", ignore_result=True)
def request_media_retry() -> int:
    """Failed downloads of the last 3 days go back to the ingestor (not metadata-only/deleted/oversized)."""
    ids = list(
        TelegramMedia.objects.filter(
            status=MediaStatus.FAILED, created_at__gte=timezone.now() - MEDIA_RETRY_WINDOW, original=""
        )
        .exclude(error__in=[METADATA_ONLY_ERROR, DELETED_MEDIA_ERROR, "too_large"])
        .values_list("pk", flat=True)[:500]
    )
    if ids and not _pending_request_exists(RequestKind.RETRY_MEDIA):
        enqueue_request(RequestKind.RETRY_MEDIA, params={"media_ids": ids})
    return len(ids)


@shared_task(name="telegram.cleanup_outbox", ignore_result=True)
def cleanup_outbox() -> int:
    """Processed outbox rows older than 30 days are deleted (ARCHITECTURE §6)."""
    deleted, _ = IngestionOutbox.objects.filter(processed_at__lt=timezone.now() - OUTBOX_RETENTION).delete()
    return deleted


@shared_task(
    name="media.process_media",
    autoretry_for=(OSError,),
    retry_backoff=True,
    max_retries=3,
    acks_late=True,
)
def process_media(media_id: int) -> Any:
    """Derivatives for one media row (queue `media`)."""
    return _process_media(media_id)
