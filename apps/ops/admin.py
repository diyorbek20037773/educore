"""Admin: alert log (read-only)."""

from __future__ import annotations

from django.contrib import admin

from apps.core.admin_base import ReadOnlyAdmin
from apps.ops.models import AlertEvent


@admin.register(AlertEvent)
class AlertEventAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "kind", "dedupe_key", "channel", "sent_at")
    list_filter = ("kind", "channel")
    search_fields = ("dedupe_key", "message")
