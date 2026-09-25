"""Admin: aggregated statistics (read-only)."""

from __future__ import annotations

from django.contrib import admin

from apps.analytics.models import DailyStat, InstitutionDailyStat, SearchLog
from apps.core.admin_base import ReadOnlyAdmin


@admin.register(DailyStat)
class DailyStatAdmin(ReadOnlyAdmin):
    list_display = (
        "date",
        "posts_ingested",
        "articles_published",
        "articles_review",
        "ai_runs",
        "ai_cost_usd",
        "appeals_new",
        "pageviews",
        "unique_visitors",
    )
    date_hierarchy = "date"


@admin.register(InstitutionDailyStat)
class InstitutionDailyStatAdmin(ReadOnlyAdmin):
    list_display = ("date", "institution", "posts", "articles", "tg_views_sum", "tg_forwards_sum")
    list_filter = ("institution",)
    date_hierarchy = "date"


@admin.register(SearchLog)
class SearchLogAdmin(ReadOnlyAdmin):
    list_display = ("query_norm", "count", "last_searched_at")
    search_fields = ("query_norm",)
