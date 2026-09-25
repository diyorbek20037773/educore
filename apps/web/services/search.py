"""Site search (SPEC §6.11): Postgres FTS over articles (`simple` + `unaccent`) with a trigram fallback,
plus plain lookups over programs, professions, events, institutions and FAQ. Cyrillic queries are
transliterated to Latin first, so both scripts match the Latin source content."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import BooleanField, FloatField, Q
from django.db.models.expressions import RawSQL

from apps.content import selectors as content
from apps.content.models import Article, Event
from apps.core.models import FAQ
from apps.core.text import normalize_uzbek_apostrophes
from apps.core.translit import is_mostly_cyrillic, to_latin
from apps.institutions.models import Institution, Profession, Program

MAX_QUERY = 100
TRIGRAM_THRESHOLD = 0.2
TSQUERY = "plainto_tsquery('simple', unaccent(%s))"
MATCH_SQL = "content_article.search_vector @@ " + TSQUERY
RANK_SQL = "ts_rank(content_article.search_vector, " + TSQUERY + ")"


def normalize_query(raw: str) -> str:
    query = " ".join((raw or "").split())[:MAX_QUERY]
    if is_mostly_cyrillic(query):
        query = to_latin(query)
    return normalize_uzbek_apostrophes(query)


@dataclass
class SearchResults:
    query: str
    articles: list[Article] = field(default_factory=list)
    programs: list[Program] = field(default_factory=list)
    professions: list[Profession] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    institutions: list[Institution] = field(default_factory=list)
    faqs: list[FAQ] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(
            len(group)
            for group in (
                self.articles,
                self.programs,
                self.professions,
                self.events,
                self.institutions,
                self.faqs,
            )
        )


def search_articles(query: str, limit: int = 20) -> list[Article]:
    matches = list(
        content.published_articles()
        .annotate(
            hit=RawSQL(MATCH_SQL, (query,), output_field=BooleanField()),  # noqa: S611 - constant SQL, bound params
            rank=RawSQL(RANK_SQL, (query,), output_field=FloatField()),  # noqa: S611
        )
        .filter(hit=True)
        .order_by("-rank", "-published_at")[:limit]
    )
    if len(matches) < 5:
        seen = {a.pk for a in matches}
        similar = (
            content.published_articles()
            .annotate(similarity=TrigramSimilarity("title_uz", query))
            .filter(similarity__gte=TRIGRAM_THRESHOLD)
            .exclude(pk__in=seen)
            .order_by("-similarity")[: limit - len(matches)]
        )
        matches.extend(similar)
    return matches


def search(raw: str) -> SearchResults:
    query = normalize_query(raw)
    results = SearchResults(query=query)
    if len(query) < 2:
        return results
    results.articles = search_articles(query)
    results.programs = list(
        Program.objects.filter(is_active=True)
        .filter(Q(name__icontains=query) | Q(code__icontains=query) | Q(qualification__icontains=query))
        .select_related("institution")[:10]
    )
    results.professions = list(
        Profession.objects.filter(is_published=True).filter(
            Q(name__icontains=query) | Q(summary__icontains=query)
        )[:10]
    )
    results.events = list(
        Event.objects.filter(is_published=True, title__icontains=query).select_related("institution")[:10]
    )
    results.institutions = list(
        Institution.objects.filter(is_active=True).filter(
            Q(short_name__icontains=query) | Q(full_name__icontains=query) | Q(abbreviation__iexact=query)
        )
    )
    results.faqs = list(
        FAQ.objects.filter(is_published=True).filter(
            Q(question__icontains=query) | Q(answer__icontains=query)
        )[:10]
    )
    return results


def suggestions(raw: str, limit: int = 6) -> list[dict[str, Any]]:
    query = normalize_query(raw)
    if len(query) < 2:
        return []
    items: list[dict[str, Any]] = [
        {"label": i.short_name, "url": i.get_absolute_url(), "kind": "institution"}
        for i in Institution.objects.filter(is_active=True).filter(
            Q(short_name__icontains=query) | Q(abbreviation__iexact=query)
        )[:2]
    ]
    items += [
        {"label": a.title, "url": a.get_absolute_url(), "kind": "article"}
        for a in search_articles(query, limit=limit)
    ]
    return items[:limit]
