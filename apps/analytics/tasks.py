"""Analytics Celery tasks (CLAUDE.md §11)."""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from apps.analytics.services import aggregation, pageviews
from apps.core.cache import bump_content_version

# Telegram views keep growing after publication; re-aggregating a week keeps engagement charts current.
RECENT_DAYS = 7


@shared_task(name="analytics.aggregate_daily", ignore_result=True)
def aggregate_daily() -> int:
    """02:00: recompute the last week (views/forwards drift) up to and including today."""
    today = timezone.localdate()
    days = aggregation.rebuild(start=today - timedelta(days=RECENT_DAYS), end=today)
    bump_content_version()
    return days


@shared_task(name="analytics.flush_pageviews", ignore_result=True)
def flush_pageviews() -> dict[str, int]:
    """Hourly: Redis counters → DB, and refresh today's rollups so charts lag by at most an hour (ADR-026)."""
    result = pageviews.flush()
    aggregation.aggregate_day(timezone.localdate())
    return result


@shared_task(name="analytics.refresh_institution_stats", ignore_result=True)
def refresh_institution_stats() -> int:
    return aggregation.refresh_institution_stats()
