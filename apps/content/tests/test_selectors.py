"""List selectors stay at a constant query count (NFR-PERF-2, T1.6)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from apps.content import selectors
from apps.content.tests.factories import (
    AdmissionFactory,
    ArticleFactory,
    ArticleMediaFactory,
    ArticleSourceFactory,
    EventFactory,
    StoryFactory,
    TagFactory,
)
from apps.institutions.tests.factories import InstitutionFactory

pytestmark = pytest.mark.django_db


def _touch_cards(articles: list[Any]) -> None:
    for a in articles:
        _ = (a.category.name, a.primary_institution.short_name, a.cover_media)


def test_latest_articles_constant_queries(django_assert_num_queries: Callable[..., Any]) -> None:
    ArticleFactory.create_batch(15)
    ArticleFactory(draft=True)
    with django_assert_num_queries(1):
        articles = selectors.latest_articles(limit=12)
        _touch_cards(articles)
    assert len(articles) == 12


def test_latest_articles_filters_by_abbreviation() -> None:
    inst = InstitutionFactory(abbreviation="IIV")
    ArticleFactory(primary_institution=inst)
    ArticleFactory.create_batch(3)
    assert [
        a.primary_institution.abbreviation for a in selectors.latest_articles(institution_abbr="iiv")
    ] == ["IIV"]


def test_article_list_filters_and_query_count(django_assert_num_queries: Callable[..., Any]) -> None:
    inst = InstitutionFactory()
    ArticleFactory.create_batch(5, primary_institution=inst)
    ArticleFactory.create_batch(5)
    with django_assert_num_queries(1):
        articles = list(selectors.article_list(institution_slug=inst.slug)[:24])
        _touch_cards(articles)
    assert len(articles) == 5


def test_article_detail_prefetches(django_assert_num_queries: Callable[..., Any]) -> None:
    article = ArticleFactory()
    ArticleSourceFactory.create_batch(3, article=article)
    ArticleMediaFactory.create_batch(2, article=article)
    article.tags.add(*TagFactory.create_batch(3))
    with django_assert_num_queries(4):
        found = selectors.article_detail(article.slug)
        assert found is not None
        for src in found.sources.all():
            _ = (src.post.source.username, src.institution)
        _ = [m.media for m in found.gallery.all()]
        _ = [t.name for t in found.tags.all()]


def test_hidden_articles_are_not_listed() -> None:
    ArticleFactory(draft=True)
    ArticleFactory(review=True)
    assert selectors.latest_articles() == []


def test_events_admissions_stories_constant_queries(django_assert_num_queries: Callable[..., Any]) -> None:
    EventFactory.create_batch(8)
    AdmissionFactory.create_batch(4)
    StoryFactory.create_batch(5)
    with django_assert_num_queries(1):
        _ = [e.institution.short_name for e in selectors.upcoming_events(limit=6)]
    with django_assert_num_queries(2):
        _ = [(a.institution.short_name, list(a.programs.all())) for a in selectors.open_admissions()]
    with django_assert_num_queries(1):
        _ = [(s.institution.short_name, s.cover_media) for s in selectors.published_stories()]
