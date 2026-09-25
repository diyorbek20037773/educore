"""Home page data (SPEC §6.2). Heavy aggregates are cached per content version (ARCHITECTURE §5)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from django.core.cache import cache
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.content import selectors as content
from apps.content.models import Article, ArticleStatus, Event
from apps.core.cache import content_version
from apps.institutions.models import Institution, Profession, Program

HOME_CACHE_SECONDS = 60
SPARK_DAYS = 30


def _days(n: int) -> list[date]:
    today = timezone.localdate()
    return [today - timedelta(days=n - 1 - i) for i in range(n)]


def daily_counts(qs: Any, field: str, days: int = SPARK_DAYS) -> list[int]:
    """Counts per local day for the last `days` days (zero-filled) — sparkline data."""
    start = timezone.localdate() - timedelta(days=days - 1)
    rows = (
        qs.filter(**{f"{field}__date__gte": start})
        .annotate(day=TruncDate(field))
        .order_by()
        .values("day")
        .annotate(n=Count("id"))
    )
    by_day = {r["day"]: r["n"] for r in rows}
    return [by_day.get(d, 0) for d in _days(days)]


def hero_articles() -> list[Article]:
    """Pinned > featured (still valid) > most important of the last 24 h, then the newest (1 + 3 cards)."""
    now = timezone.now()
    qs = content.published_articles()
    picked: list[Article] = []
    for candidate in (
        qs.filter(is_pinned=True).order_by("-published_at"),
        qs.filter(is_featured=True)
        .filter(Q(featured_until__isnull=True) | Q(featured_until__gt=now))
        .order_by("-published_at"),
        qs.filter(published_at__gte=now - timedelta(hours=24)).order_by("-importance", "-published_at"),
        qs.order_by("-published_at"),
    ):
        for article in candidate[:4]:
            if article not in picked:
                picked.append(article)
            if len(picked) == 4:
                return picked
    return picked


def kpis() -> list[dict[str, Any]]:
    today = timezone.localdate()
    published = Article.objects.filter(status=ArticleStatus.PUBLISHED)
    news_today = published.filter(published_at__date=today).count()
    upcoming = Event.objects.filter(is_published=True, starts_at__gte=timezone.now())
    return [
        {
            "key": "institutions",
            "value": Institution.objects.filter(is_active=True).count(),
            "url": "web:institution_list",
            "spark": None,
        },
        {
            "key": "news_today",
            "value": news_today,
            "url": "web:news_list",
            "spark": daily_counts(published, "published_at"),
        },
        {
            "key": "events",
            "value": upcoming.count(),
            "url": "web:event_list",
            "spark": daily_counts(Event.objects.filter(is_published=True), "created_at"),
        },
        {
            "key": "programs",
            "value": Program.objects.filter(is_active=True).count(),
            "url": "web:program_list",
            "spark": None,
        },
        {
            "key": "professions",
            "value": Profession.objects.filter(is_published=True).count(),
            "url": "web:profession_list",
            "spark": None,
        },
    ]


def institution_cards() -> list[dict[str, Any]]:
    """Five cards: news in 30 days, programs, upcoming events, 30-day sparkline (4 queries total)."""
    since = timezone.now() - timedelta(days=30)
    institutions = list(
        Institution.objects.filter(is_active=True)
        .annotate(
            news_30=Count(
                "primary_articles",
                filter=Q(
                    primary_articles__status=ArticleStatus.PUBLISHED,
                    primary_articles__published_at__gte=since,
                ),
                distinct=True,
            ),
            programs_n=Count("programs", filter=Q(programs__is_active=True), distinct=True),
            events_n=Count(
                "events",
                filter=Q(events__is_published=True, events__starts_at__gte=timezone.now()),
                distinct=True,
            ),
        )
        .order_by("order")
    )
    spark_rows = (
        Article.objects.filter(status=ArticleStatus.PUBLISHED, published_at__gte=since)
        .annotate(day=TruncDate("published_at"))
        .order_by()
        .values("primary_institution", "day")
        .annotate(n=Count("id"))
    )
    series: dict[int, dict[date, int]] = defaultdict(dict)
    for row in spark_rows:
        series[row["primary_institution"]][row["day"]] = row["n"]
    days = _days(SPARK_DAYS)
    return [{"institution": i, "spark": [series[i.pk].get(d, 0) for d in days]} for i in institutions]


def cached(name: str, builder: Any) -> Any:
    key = f"web:home:{name}:{content_version()}"
    value = cache.get(key)
    if value is None:
        value = builder()
        cache.set(key, value, HOME_CACHE_SECONDS)
    return value


def home_context() -> dict[str, Any]:
    hero = cached("hero", hero_articles)
    return {
        "hero": hero[0] if hero else None,
        "hero_secondary": hero[1:4],
        "kpis": cached("kpis", kpis),
        "live_articles": content.latest_articles(12),
        "institution_cards": cached("institutions", institution_cards),
        "admissions": content.open_admissions()[:5],
        "programs_by_institution": cached("programs", programs_by_institution),
        "cadet_student_articles": content.articles_in_categories(["kursantlar", "talabalar"], 6),
        "professions": list(
            Profession.objects.filter(is_published=True).prefetch_related("institutions")[:6]
        ),
        "events": content.upcoming_events(6),
        "stories": content.published_stories(8),
        "teaser": cached("teaser", analytics_teaser),
    }


def programs_by_institution() -> list[dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    for program in (
        Program.objects.filter(is_active=True)
        .select_related("institution")
        .order_by("institution__order", "level", "name")
    ):
        entry = rows.setdefault(program.institution_id, {"institution": program.institution, "programs": []})
        if len(entry["programs"]) < 5:
            entry["programs"].append(program)
    return list(rows.values())


def analytics_teaser() -> dict[str, int]:
    since = timezone.now() - timedelta(days=30)
    published = Article.objects.filter(status=ArticleStatus.PUBLISHED)
    return {
        "articles_30": published.filter(published_at__gte=since).count(),
        "articles_total": published.count(),
    }
