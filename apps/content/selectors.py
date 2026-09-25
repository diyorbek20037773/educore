"""Read queries for editorial content (lists stay within a constant number of queries — NFR-PERF-2)."""

from __future__ import annotations

from datetime import date

from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from apps.content.models import Admission, Article, ArticleSource, Event, Story

LIST_RELATED = ("category", "primary_institution", "cover_media")


def published_articles() -> QuerySet[Article]:
    """Public articles with the relations every card needs."""
    return Article.objects.published().select_related(*LIST_RELATED)


def latest_articles(limit: int = 12, institution_abbr: str | None = None) -> list[Article]:
    """Live panel: newest published articles, optionally for one institution (by abbreviation)."""
    qs = published_articles()
    if institution_abbr:
        qs = qs.filter(primary_institution__abbreviation__iexact=institution_abbr)
    return list(qs.order_by("-published_at")[:limit])


def article_list(
    *,
    institution_slug: str | None = None,
    category_slug: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: str = "new",
) -> QuerySet[Article]:
    """Filtered news list (paginated by the caller)."""
    qs = published_articles()
    if institution_slug:
        qs = qs.filter(institutions__slug=institution_slug)
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    if date_from:
        qs = qs.filter(published_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(published_at__date__lte=date_to)
    order = {"new": "-published_at", "old": "published_at", "popular": "-view_count"}.get(
        sort, "-published_at"
    )
    return qs.order_by(order, "-pk").distinct()


def articles_in_categories(slugs: list[str], limit: int = 6) -> list[Article]:
    return list(published_articles().filter(category__slug__in=slugs).order_by("-published_at")[:limit])


def article_detail(slug: str) -> Article | None:
    """One article with sources, gallery and tags prefetched (any status; views decide visibility)."""
    return (
        Article.objects.select_related(*LIST_RELATED, "cluster")
        .prefetch_related(
            "tags",
            "gallery__media",
            Prefetch(
                "sources",
                queryset=ArticleSource.objects.select_related("post__source", "institution").order_by(
                    "-is_primary", "added_at"
                ),
            ),
        )
        .filter(slug=slug)
        .first()
    )


def upcoming_events(limit: int = 6, institution_slug: str | None = None) -> list[Event]:
    qs = Event.objects.filter(is_published=True, starts_at__gte=timezone.now()).select_related("institution")
    if institution_slug:
        qs = qs.filter(institution__slug=institution_slug)
    return list(qs.order_by("starts_at")[:limit])


def open_admissions() -> list[Admission]:
    return list(
        Admission.objects.filter(is_published=True)
        .exclude(status="closed")
        .select_related("institution")
        .prefetch_related("programs")
        .order_by("ends_at", "institution__order")
    )


def published_stories(limit: int = 8) -> list[Story]:
    return list(
        Story.objects.filter(is_published=True)
        .select_related("institution", "cover_media")
        .order_by("order", "-published_at")[:limit]
    )
