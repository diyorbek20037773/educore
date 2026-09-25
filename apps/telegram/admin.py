"""Admin: Telegram sources monitor, requests, posts (raw JSON), media, outbox (SPEC §8 › Telegram)."""

from __future__ import annotations

import json
from typing import Any

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone
from django.utils.html import format_html
from django.utils.timesince import timesince
from django.utils.translation import gettext_lazy as _
from unfold.admin import TabularInline

from apps.core.admin_base import EducoreAdmin, ReadOnlyAdmin
from apps.telegram.models import (
    IngestionOutbox,
    IngestionRequest,
    ProcessingStatus,
    RequestKind,
    SourceStatus,
    TelegramMedia,
    TelegramPost,
    TelegramSource,
)


def _pretty_json(value: Any) -> str:
    return format_html(
        '<pre style="white-space:pre-wrap;max-height:32rem;overflow:auto;font-size:12px">{}</pre>',
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
    )


def _enqueue(
    request: HttpRequest, queryset: QuerySet[TelegramSource], kind: str, params: dict[str, Any]
) -> int:
    rows = [
        IngestionRequest(kind=kind, source=source, params=params, requested_by=request.user)  # type: ignore[misc]
        for source in queryset
    ]
    IngestionRequest.objects.bulk_create(rows)
    return len(rows)


@admin.register(TelegramSource)
class TelegramSourceAdmin(EducoreAdmin):
    list_display = (
        "username",
        "institution",
        "status",
        "is_active",
        "last_message_at",
        "lag",
        "subscribers_count",
        "error_count",
    )
    list_filter = ("status", "is_active", "institution", "ingest_method")
    search_fields = ("username", "title")
    autocomplete_fields = ("institution",)
    readonly_fields = (
        "telegram_channel_id",
        "access_hash",
        "last_message_id",
        "last_message_at",
        "last_update_seen_at",
        "last_gapcheck_at",
        "backfill_done_at",
        "subscribers_count",
        "error_count",
        "last_error",
        "joined_at",
    )
    actions = ("request_resolve", "request_backfill", "request_gapcheck", "disable_sources")

    @admin.display(description=_("Kechikish"))
    def lag(self, obj: TelegramSource) -> str:
        seen = obj.last_update_seen_at or obj.last_gapcheck_at
        return timesince(seen, timezone.now()) if seen else "—"

    @admin.action(description=_("Maʼlumotlarni yangilash (resolve)"))
    def request_resolve(self, request: HttpRequest, queryset: QuerySet[TelegramSource]) -> None:
        n = _enqueue(request, queryset, RequestKind.RESOLVE_SOURCE, {})
        self.message_user(request, _("%(n)d ta soʻrov navbatga qoʻyildi.") % {"n": n}, messages.SUCCESS)

    @admin.action(description=_("Tarixni yuklash (backfill)"))
    def request_backfill(self, request: HttpRequest, queryset: QuerySet[TelegramSource]) -> None:
        from django.conf import settings

        params = {
            "limit": settings.TELEGRAM_BACKFILL_LIMIT,
            "ai_limit": settings.BACKFILL_AI_LIMIT_PER_SOURCE,
        }
        n = _enqueue(request, queryset, RequestKind.BACKFILL, params)
        self.message_user(request, _("%(n)d ta soʻrov navbatga qoʻyildi.") % {"n": n}, messages.SUCCESS)

    @admin.action(description=_("Boʻshliqlarni tekshirish (gap check)"))
    def request_gapcheck(self, request: HttpRequest, queryset: QuerySet[TelegramSource]) -> None:
        n = _enqueue(request, queryset, RequestKind.GAPCHECK, {})
        self.message_user(request, _("%(n)d ta soʻrov navbatga qoʻyildi.") % {"n": n}, messages.SUCCESS)

    @admin.action(description=_("Oʻchirish (disable)"))
    def disable_sources(self, request: HttpRequest, queryset: QuerySet[TelegramSource]) -> None:
        n = queryset.update(is_active=False, status=SourceStatus.DISABLED)
        self.message_user(request, _("%(n)d ta manba oʻchirildi.") % {"n": n}, messages.WARNING)


@admin.register(IngestionRequest)
class IngestionRequestAdmin(EducoreAdmin):
    list_display = ("kind", "source", "status", "requested_by", "created_at", "started_at", "finished_at")
    list_filter = ("kind", "status", "source")
    readonly_fields = ("status", "started_at", "finished_at", "result", "error", "requested_by")

    def save_model(self, request: HttpRequest, obj: IngestionRequest, form: Any, change: bool) -> None:
        if not change:
            obj.requested_by = request.user  # type: ignore[assignment]
        super().save_model(request, obj, form, change)


class MediaInline(TabularInline):
    model = TelegramMedia
    extra = 0
    can_delete = False
    fields = ("thumb", "order", "kind", "mime_type", "size_bytes", "status")
    readonly_fields = fields

    @admin.display(description=_("Koʻrinish"))
    def thumb(self, obj: TelegramMedia) -> str:
        if obj.kind == "photo" and obj.original:
            return format_html(
                '<img src="{}" style="height:48px;border-radius:6px" alt="">', obj.original.url
            )
        return "—"

    def has_add_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False


@admin.register(TelegramPost)
class TelegramPostAdmin(EducoreAdmin):
    list_display = (
        "__str__",
        "source",
        "published_at",
        "media_count",
        "processing_status",
        "is_deleted",
        "is_backfill",
    )
    list_filter = ("processing_status", "source", "is_deleted", "is_backfill", "has_media")
    search_fields = ("text", "telegram_message_id")
    date_hierarchy = "published_at"
    inlines = (MediaInline,)
    readonly_fields = ("raw_json_pretty", "telegram_link", "content_hash", "embedding_state")
    exclude = ("raw_json", "embedding", "entities")
    actions = ("reprocess", "mark_skipped")

    @admin.display(description=_("Xom maʼlumot (JSON)"))
    def raw_json_pretty(self, obj: TelegramPost) -> str:
        return _pretty_json(obj.raw_json)

    @admin.display(description=_("Telegram havola"))
    def telegram_link(self, obj: TelegramPost) -> str:
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>', obj.telegram_url, obj.telegram_url
        )

    @admin.display(description=_("Embedding"))
    def embedding_state(self, obj: TelegramPost) -> str:
        return _("bor") if obj.embedding is not None else "—"

    @admin.action(description=_("Qayta ishlash (AI)"))
    def reprocess(self, request: HttpRequest, queryset: QuerySet[TelegramPost]) -> None:
        from config.celery import app

        for post in queryset:
            app.send_task("ai.process_post", args=[post.pk, "telegram.post.edited", None, True], queue="ai")
        self.message_user(
            request, _("%(n)d ta post navbatga qoʻyildi.") % {"n": queryset.count()}, messages.INFO
        )

    @admin.action(description=_("Oʻtkazib yuborish (skip)"))
    def mark_skipped(self, request: HttpRequest, queryset: QuerySet[TelegramPost]) -> None:
        n = queryset.update(processing_status=ProcessingStatus.SKIPPED, skip_reason="manual")
        self.message_user(request, _("%(n)d ta post oʻtkazib yuborildi.") % {"n": n}, messages.INFO)


@admin.register(TelegramMedia)
class TelegramMediaAdmin(EducoreAdmin):
    list_display = ("post", "order", "kind", "mime_type", "size_bytes", "status")
    list_filter = ("kind", "status")
    search_fields = ("post__text", "caption")
    readonly_fields = ("derivatives",)


@admin.register(IngestionOutbox)
class IngestionOutboxAdmin(ReadOnlyAdmin):
    list_display = ("event_type", "post", "created_at", "processed_at", "attempts", "is_dead", "locked_until")
    list_filter = ("event_type", "is_dead", ("processed_at", admin.EmptyFieldListFilter))
    search_fields = ("post__telegram_message_id",)
    actions = ("retry",)

    def has_retry_permission(self, request: HttpRequest) -> bool:
        return request.user.has_perm("telegram.change_ingestionoutbox")

    @admin.action(description=_("Qayta urinish (retry)"), permissions=["retry"])
    def retry(self, request: HttpRequest, queryset: QuerySet[IngestionOutbox]) -> None:
        n = queryset.filter(processed_at__isnull=True).update(
            attempts=0, is_dead=False, locked_until=None, last_error=""
        )
        self.message_user(request, _("%(n)d ta hodisa qayta navbatga qoʻyildi.") % {"n": n}, messages.SUCCESS)
