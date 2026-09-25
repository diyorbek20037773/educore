"""Admin: AI runs (read-only with output viewer), budget days, event clusters (SPEC §8 › AI)."""

from __future__ import annotations

import json

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.ai.models import AIBudgetDay, AIRun, EventCluster
from apps.core.admin_base import EducoreAdmin, ReadOnlyAdmin


@admin.register(AIRun)
class AIRunAdmin(ReadOnlyAdmin):
    list_display = (
        "created_at",
        "stage",
        "status",
        "provider",
        "model",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "duration_ms",
        "post",
        "article",
    )
    list_filter = ("stage", "status", "provider", "model", "prompt_version")
    search_fields = ("post__telegram_message_id", "article__title", "request_id")
    date_hierarchy = "created_at"
    exclude = ("output",)
    readonly_fields = ("output_pretty",)

    @admin.display(description=_("Natija"))
    def output_pretty(self, obj: AIRun) -> str:
        return format_html(
            '<pre style="white-space:pre-wrap;max-height:32rem;overflow:auto;font-size:12px">{}</pre>',
            json.dumps(obj.output, ensure_ascii=False, indent=2, default=str),
        )


@admin.register(AIBudgetDay)
class AIBudgetDayAdmin(ReadOnlyAdmin):
    list_display = ("date", "usd_spent", "runs", "input_tokens", "output_tokens", "is_exhausted")
    list_filter = ("is_exhausted",)
    date_hierarchy = "date"


@admin.register(EventCluster)
class EventClusterAdmin(EducoreAdmin):
    list_display = (
        "__str__",
        "posts_count",
        "sources_count",
        "first_seen_at",
        "last_seen_at",
        "canonical_article",
    )
    search_fields = ("title",)
    exclude = ("embedding",)
    readonly_fields = ("posts_count", "sources_count", "first_seen_at", "last_seen_at")
    raw_id_fields = ("canonical_article",)
