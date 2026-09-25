"""Telegram ingestion models: sources, requests, posts, media and the transactional outbox (SPEC §2.4)."""

from __future__ import annotations

import uuid
from typing import ClassVar

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from pgvector.django import HnswIndex, VectorField

from apps.core.models import TimeStampedModel

EMBEDDING_DIMENSIONS = 384


class SourceStatus(models.TextChoices):
    LIVE = "live", _("Jonli")
    DEGRADED = "degraded", _("Nosoz")
    OFFLINE = "offline", _("Oflayn")
    DISABLED = "disabled", _("Oʻchirilgan")


class IngestMethod(models.TextChoices):
    MTPROTO = "mtproto", _("MTProto (user session)")
    BOT = "bot", _("Bot API (reserved)")


class TelegramSource(TimeStampedModel):
    """A Telegram channel we follow. Adding a row is enough — the ingestor picks it up within 60 s."""

    institution = models.ForeignKey(
        "institutions.Institution",
        verbose_name=_("institution"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="telegram_sources",
    )
    username = models.CharField(
        _("username"), max_length=64, unique=True, help_text=_("Without @, lowercase.")
    )
    title = models.CharField(_("title"), max_length=255, blank=True)
    about_text = models.TextField(_("about"), blank=True)
    photo = models.ImageField(_("photo"), upload_to="telegram/sources/", null=True, blank=True)
    telegram_channel_id = models.BigIntegerField(_("channel id"), unique=True, null=True, blank=True)
    access_hash = models.BigIntegerField(_("access hash"), null=True, blank=True)
    ingest_method = models.CharField(
        _("ingest method"), max_length=10, choices=IngestMethod.choices, default=IngestMethod.MTPROTO
    )
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    status = models.CharField(
        _("status"), max_length=10, choices=SourceStatus.choices, default=SourceStatus.OFFLINE, db_index=True
    )
    last_message_id = models.BigIntegerField(_("last message id"), null=True, blank=True)
    last_message_at = models.DateTimeField(_("last message at"), null=True, blank=True)
    last_update_seen_at = models.DateTimeField(_("last update seen at"), null=True, blank=True)
    last_gapcheck_at = models.DateTimeField(_("last gap check at"), null=True, blank=True)
    backfill_done_at = models.DateTimeField(_("backfill done at"), null=True, blank=True)
    subscribers_count = models.PositiveIntegerField(_("subscribers"), null=True, blank=True)
    error_count = models.PositiveIntegerField(_("error count"), default=0)
    last_error = models.TextField(_("last error"), blank=True)
    joined_at = models.DateTimeField(_("joined at"), null=True, blank=True)
    signature_patterns = models.JSONField(
        _("signature patterns"),
        default=list,
        blank=True,
        help_text=_("Regexes stripped from post text before AI."),
    )

    class Meta:
        ordering = ("institution__order", "username")
        verbose_name = _("Telegram source")
        verbose_name_plural = _("Telegram sources")

    def __str__(self) -> str:
        return f"@{self.username}"

    def save(self, *args: object, **kwargs: object) -> None:
        self.username = self.username.strip().lstrip("@").lower()
        super().save(*args, **kwargs)  # type: ignore[arg-type]


class RequestKind(models.TextChoices):
    BACKFILL = "backfill", _("Backfill")
    GAPCHECK = "gapcheck", _("Gap check")
    REFRESH_ENGAGEMENT = "refresh_engagement", _("Engagement refresh")
    RESOLVE_SOURCE = "resolve_source", _("Resolve source")
    RETRY_MEDIA = "retry_media", _("Retry media")


class RequestStatus(models.TextChoices):
    PENDING = "pending", _("Kutilmoqda")
    RUNNING = "running", _("Bajarilmoqda")
    DONE = "done", _("Bajarildi")
    FAILED = "failed", _("Xato")


class IngestionRequest(TimeStampedModel):
    """Work for the ingestor; only the ingestor (session owner) executes these rows (ADR-009)."""

    kind = models.CharField(_("kind"), max_length=20, choices=RequestKind.choices)
    source = models.ForeignKey(
        TelegramSource,
        verbose_name=_("source"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="requests",
        help_text=_("Empty = all active sources."),
    )
    params = models.JSONField(_("parameters"), default=dict, blank=True)
    status = models.CharField(
        _("status"), max_length=10, choices=RequestStatus.choices, default=RequestStatus.PENDING
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("requested by"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)
    result = models.JSONField(_("result"), default=dict, blank=True)
    error = models.TextField(_("error"), blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("ingestion request")
        verbose_name_plural = _("ingestion requests")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["status", "created_at"], name="tg_request_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.kind} ({self.status})"


class ProcessingStatus(models.TextChoices):
    PENDING = "pending", _("Kutilmoqda")
    QUEUED = "queued", _("Navbatda")
    PROCESSING = "processing", _("Qayta ishlanmoqda")
    PROCESSED = "processed", _("Qayta ishlandi")
    SKIPPED = "skipped", _("Oʻtkazib yuborildi")
    FAILED = "failed", _("Xato")


class TelegramPost(TimeStampedModel):
    """One channel post; an album (`grouped_id`) is one post with N media. Never physically deleted."""

    source = models.ForeignKey(
        TelegramSource, verbose_name=_("source"), on_delete=models.PROTECT, related_name="posts"
    )
    telegram_message_id = models.BigIntegerField(_("message id"))
    grouped_id = models.BigIntegerField(_("album id"), null=True, blank=True, db_index=True)
    text = models.TextField(_("text"), blank=True)
    entities = models.JSONField(_("entities"), default=list, blank=True)
    links = models.JSONField(_("links"), default=list, blank=True)
    hashtags = models.JSONField(_("hashtags"), default=list, blank=True)
    published_at = models.DateTimeField(_("published at"))
    edited_at = models.DateTimeField(_("edited at"), null=True, blank=True)
    telegram_url = models.URLField(_("Telegram URL"), max_length=300, blank=True)
    content_hash = models.CharField(_("content hash"), max_length=64, blank=True, db_index=True)
    has_media = models.BooleanField(_("has media"), default=False)
    media_count = models.PositiveSmallIntegerField(_("media count"), default=0)
    views = models.PositiveIntegerField(_("views"), null=True, blank=True)
    forwards = models.PositiveIntegerField(_("forwards"), null=True, blank=True)
    reactions = models.JSONField(_("reactions"), default=dict, blank=True)
    reply_to_id = models.BigIntegerField(_("reply to"), null=True, blank=True)
    is_forwarded = models.BooleanField(_("forwarded"), default=False)
    forward_from = models.CharField(_("forwarded from"), max_length=255, blank=True)
    is_deleted = models.BooleanField(_("deleted"), default=False, db_index=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)
    is_backfill = models.BooleanField(_("from backfill"), default=False)
    raw_json = models.JSONField(_("raw message"), default=dict, blank=True)
    language = models.CharField(_("language"), max_length=10, null=True, blank=True)
    processing_status = models.CharField(
        _("processing status"),
        max_length=12,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    processing_error = models.TextField(_("processing error"), blank=True)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)
    skip_reason = models.CharField(_("skip reason"), max_length=40, blank=True)
    embedding = VectorField(_("embedding"), dimensions=EMBEDDING_DIMENSIONS, null=True, blank=True)
    cluster = models.ForeignKey(
        "ai.EventCluster",
        verbose_name=_("cluster"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
    )
    search_vector = SearchVectorField(null=True, editable=False)
    importance = models.PositiveSmallIntegerField(_("importance"), null=True, blank=True)
    missing_checks = models.PositiveSmallIntegerField(
        _("consecutive gap-check misses"), default=0, help_text=_("Deleted after two consecutive misses.")
    )

    class Meta:
        ordering = ("-published_at",)
        verbose_name = _("Telegram post")
        verbose_name_plural = _("Telegram posts")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["source", "telegram_message_id"], name="uniq_post_source_message"
            ),
            models.UniqueConstraint(
                fields=["source", "grouped_id"],
                condition=Q(grouped_id__isnull=False),
                name="uniq_post_source_album",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["source", "-published_at"], name="tg_post_source_pub_idx"),
            models.Index(fields=["-published_at"], name="tg_post_pub_idx"),
            models.Index(fields=["processing_status"], name="tg_post_status_idx"),
            GinIndex(fields=["search_vector"], name="tg_post_search_gin"),
            HnswIndex(
                name="tg_post_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self) -> str:
        return f"@{self.source.username}/{self.telegram_message_id}"


class MediaKind(models.TextChoices):
    PHOTO = "photo", _("Rasm")
    VIDEO = "video", _("Video")
    DOCUMENT = "document", _("Hujjat")
    AUDIO = "audio", _("Audio")
    VOICE = "voice", _("Ovozli xabar")
    ANIMATION = "animation", _("Animatsiya")
    STICKER = "sticker", _("Stiker")
    WEBPAGE = "webpage", _("Veb sahifa")
    OTHER = "other", _("Boshqa")


class MediaStatus(models.TextChoices):
    PENDING = "pending", _("Kutilmoqda")
    DOWNLOADED = "downloaded", _("Yuklandi")
    READY = "ready", _("Tayyor")
    FAILED = "failed", _("Xato")


class TelegramMedia(TimeStampedModel):
    """One media item of a post (album items keep their own message id)."""

    post = models.ForeignKey(
        TelegramPost, verbose_name=_("post"), on_delete=models.CASCADE, related_name="media"
    )
    telegram_message_id = models.BigIntegerField(_("message id"), db_index=True)
    order = models.PositiveSmallIntegerField(_("order"), default=0)
    kind = models.CharField(_("kind"), max_length=12, choices=MediaKind.choices)
    telegram_file_id = models.BigIntegerField(_("file id"), null=True, blank=True)
    mime_type = models.CharField(_("MIME type"), max_length=100, blank=True)
    size_bytes = models.BigIntegerField(_("size (bytes)"), null=True, blank=True)
    width = models.PositiveIntegerField(_("width"), null=True, blank=True)
    height = models.PositiveIntegerField(_("height"), null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(_("duration (s)"), null=True, blank=True)
    original = models.FileField(_("original"), max_length=300, blank=True)
    derivatives = models.JSONField(_("derivatives"), default=dict, blank=True)
    caption = models.TextField(_("caption"), blank=True)
    status = models.CharField(
        _("status"), max_length=12, choices=MediaStatus.choices, default=MediaStatus.PENDING, db_index=True
    )
    error = models.TextField(_("error"), blank=True)

    class Meta:
        ordering = ("post", "order")
        verbose_name = _("Telegram media")
        verbose_name_plural = _("Telegram media")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["post", "telegram_message_id"], name="uniq_media_post_message"),
        ]

    def __str__(self) -> str:
        return f"{self.post} #{self.order} {self.kind}"


class OutboxEventType(models.TextChoices):
    CREATED = "telegram.post.created", "telegram.post.created"
    EDITED = "telegram.post.edited", "telegram.post.edited"
    DELETED = "telegram.post.deleted", "telegram.post.deleted"


class IngestionOutbox(TimeStampedModel):
    """Transactional outbox row written with the post; relayed to Celery by `telegram.relay_outbox`."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(_("event type"), max_length=32, choices=OutboxEventType.choices)
    post = models.ForeignKey(
        TelegramPost, verbose_name=_("post"), on_delete=models.CASCADE, related_name="outbox"
    )
    payload = models.JSONField(_("payload"), default=dict)
    payload_hash = models.CharField(_("payload hash"), max_length=64)
    locked_until = models.DateTimeField(_("locked until"), null=True, blank=True)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(_("terminal failures"), default=0)
    last_error = models.TextField(_("last error"), blank=True)
    is_dead = models.BooleanField(_("dead"), default=False, db_index=True)

    class Meta:
        ordering = ("created_at",)
        verbose_name = _("outbox event")
        verbose_name_plural = _("outbox events")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["post", "event_type", "payload_hash"], name="uniq_outbox_post_event_hash"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["created_at"],
                condition=Q(processed_at__isnull=True),
                name="tg_outbox_unprocessed_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} post={self.post_id}"
