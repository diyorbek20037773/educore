"""Daily rollups (SPEC §2.8, T5.1): `DailyStat` and one `InstitutionDailyStat` per institution and local day.

Days are Asia/Tashkent calendar days. Aggregation is idempotent (recomputes a day from source rows), so the
nightly task, the hourly refresh of "today" and `stats_rebuild` can all call `aggregate_day` safely.
Page views, unique visitors and search counts are owned by `pageviews.flush` and never touched here.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import structlog
from django.db import transaction
from django.db.models import Count, Min, Sum
from django.db.models.functions import ExtractHour
from django.utils import timezone

from apps.ai.models import AIRun
from apps.analytics.models import DailyStat, InstitutionDailyStat
from apps.appeals.models import Appeal
from apps.content.models import Article, ArticleStatus
from apps.institutions.models import Institution
from apps.telegram.models import TelegramPost

log = structlog.get_logger(__name__)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """Aware [start, end) of a local calendar day (Asia/Tashkent has no DST, but stay generic)."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), tz)
    end = timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min), tz)
    return start, end


def _institution_rows(day: date, institutions: list[Institution]) -> list[dict[str, Any]]:
    start, end = day_bounds(day)
    tz = timezone.get_current_timezone()
    posts = TelegramPost.objects.filter(published_at__gte=start, published_at__lt=end, is_deleted=False)
    per_inst = {
        r["source__institution"]: r
        for r in posts.order_by()
        .values("source__institution")
        .annotate(n=Count("id"), views=Sum("views"), forwards=Sum("forwards"))
    }
    hours: dict[int, list[int]] = defaultdict(lambda: [0] * 24)
    for r in (
        posts.order_by()
        .annotate(hour=ExtractHour("published_at", tzinfo=tz))
        .values("source__institution", "hour")
        .annotate(n=Count("id"))
    ):
        hours[r["source__institution"]][r["hour"]] = r["n"]
    articles = Article.objects.filter(
        status=ArticleStatus.PUBLISHED, published_at__gte=start, published_at__lt=end
    ).order_by()
    by_category: dict[int, dict[str, int]] = defaultdict(dict)
    for r in articles.values("primary_institution", "category__slug").annotate(n=Count("id")):
        by_category[r["primary_institution"]][r["category__slug"] or "boshqa"] = r["n"]
    by_type: dict[int, dict[str, int]] = defaultdict(dict)
    for r in articles.values("primary_institution", "content_type").annotate(n=Count("id")):
        by_type[r["primary_institution"]][r["content_type"]] = r["n"]
    rows = []
    for inst in institutions:
        post_row = per_inst.get(inst.pk, {})
        rows.append(
            {
                "institution": inst,
                "posts": post_row.get("n", 0),
                "articles": sum(by_category[inst.pk].values()),
                "tg_views_sum": post_row.get("views") or 0,
                "tg_forwards_sum": post_row.get("forwards") or 0,
                "by_category": by_category[inst.pk],
                "by_content_type": by_type[inst.pk],
                "by_hour": hours[inst.pk],
            }
        )
    return rows


def _daily_totals(day: date) -> dict[str, Any]:
    start, end = day_bounds(day)
    runs = AIRun.objects.filter(created_at__gte=start, created_at__lt=end).aggregate(
        n=Count("id"), cost=Sum("cost_usd")
    )
    return {
        "posts_ingested": TelegramPost.objects.filter(created_at__gte=start, created_at__lt=end).count(),
        "articles_published": Article.objects.filter(
            status=ArticleStatus.PUBLISHED, published_at__gte=start, published_at__lt=end
        ).count(),
        "articles_review": Article.objects.filter(
            status=ArticleStatus.REVIEW, created_at__gte=start, created_at__lt=end
        ).count(),
        "ai_runs": runs["n"] or 0,
        "ai_cost_usd": runs["cost"] or Decimal("0"),
        "appeals_new": Appeal.objects.filter(created_at__gte=start, created_at__lt=end).count(),
    }


def aggregate_day(day: date, institutions: list[Institution] | None = None) -> DailyStat:
    """Recompute every rollup for one local day."""
    institutions = institutions if institutions is not None else list(Institution.objects.order_by("order"))
    rows = _institution_rows(day, institutions)
    totals = _daily_totals(day)
    with transaction.atomic():
        stat, _created = DailyStat.objects.update_or_create(date=day, defaults=totals)
        for row in rows:
            institution = row.pop("institution")
            InstitutionDailyStat.objects.update_or_create(date=day, institution=institution, defaults=row)
    return stat


def first_activity_day() -> date | None:
    """Earliest local day with a post or an article (start of `stats_rebuild`)."""
    first_post = TelegramPost.objects.aggregate(first=Min("published_at"))["first"]
    first_article = Article.objects.aggregate(first=Min("published_at"))["first"]
    candidates = [timezone.localtime(d).date() for d in (first_post, first_article) if d]
    return min(candidates) if candidates else None


def rebuild(start: date | None = None, end: date | None = None) -> int:
    """Aggregate every day in [start, end] (defaults: first activity … today). Returns the number of days."""
    end = end or timezone.localdate()
    start = start or first_activity_day() or end
    institutions = list(Institution.objects.order_by("order"))
    days = 0
    day = start
    while day <= end:
        aggregate_day(day, institutions)
        day += timedelta(days=1)
        days += 1
    log.info("stats_rebuilt", start=str(start), end=str(end), days=days)
    return days


def refresh_institution_stats() -> int:
    """Store headline numbers on `Institution.stats_cache` (profile headers, API, cards)."""
    today = timezone.localdate()
    since = today - timedelta(days=29)
    sums = {
        r["institution"]: r
        for r in InstitutionDailyStat.objects.filter(date__gte=since)
        .order_by()
        .values("institution")
        .annotate(posts=Sum("posts"), articles=Sum("articles"), views=Sum("tg_views_sum"))
    }
    totals = {
        r["primary_institution"]: r["n"]
        for r in Article.objects.filter(status=ArticleStatus.PUBLISHED)
        .order_by()
        .values("primary_institution")
        .annotate(n=Count("id"))
    }
    updated = 0
    for inst in Institution.objects.all():
        row = sums.get(inst.pk, {})
        inst.stats_cache = {
            "articles_total": totals.get(inst.pk, 0),
            "articles_30": row.get("articles") or 0,
            "posts_30": row.get("posts") or 0,
            "tg_views_30": row.get("views") or 0,
            "updated_at": timezone.now().isoformat(),
        }
        inst.save(update_fields=["stats_cache", "updated_at"])
        updated += 1
    return updated
