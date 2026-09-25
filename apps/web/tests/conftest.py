"""Public site fixtures: reference seed data plus a small set of published content."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest
from django.core.cache import cache
from django.utils import timezone, translation

from apps.analytics.services.aggregation import rebuild
from apps.analytics.tests.utils import clear_counters
from apps.content.models import Article, Category, Event, Story
from apps.content.tests.factories import (
    AdmissionFactory,
    ArticleFactory,
    ArticleSourceFactory,
    EventFactory,
    StoryFactory,
)
from apps.core.services.seeding import seed_reference_data
from apps.institutions.models import Institution, Profession, Program
from apps.telegram.models import TelegramSource
from apps.telegram.tests.factories import TelegramPostFactory


@dataclass
class SiteData:
    institution: Institution
    article: Article
    longread: Article
    event: Event
    story: Story
    program: Program
    profession: Profession


@pytest.fixture(autouse=True)
def _clean_state() -> Iterator[None]:
    """Fresh cache, and Uzbek active: LocaleMiddleware leaves the last request's language activated."""
    cache.clear()
    clear_counters()
    translation.activate("uz")
    yield
    translation.deactivate()


@pytest.fixture
def site_data(db: Any) -> SiteData:
    seed_reference_data()
    institution = Institution.objects.order_by("order").first()
    assert institution is not None
    source = TelegramSource.objects.filter(institution=institution).first()
    news = Category.objects.get(slug="yangiliklar")
    articles = []
    for n in range(5):
        article = ArticleFactory(
            title=f"Akademiyada ochiq eshiklar kuni {n}",
            category=news,
            primary_institution=institution,
            published_at=timezone.now() - timedelta(hours=n + 1),
        )
        post = TelegramPostFactory(source=source, views=100 * (n + 1), forwards=n)
        ArticleSourceFactory(article=article, post=post)
        articles.append(article)
    longread = ArticleFactory(
        title="Haftalik sharh",
        content_type="digest",
        category=Category.objects.get(slug="maqolalar"),
        primary_institution=institution,
        body="<h2>Birinchi boʻlim</h2><p>Matn.</p><h3>Tafsilot</h3><p>Matn.</p>",
    )
    event = EventFactory(institution=institution)
    AdmissionFactory(institution=institution)
    story = StoryFactory(institution=institution)
    program = Program.objects.filter(institution=institution, is_active=True).first()
    profession = Profession.objects.filter(is_published=True).first()
    assert program is not None and profession is not None
    rebuild()  # charts read the daily rollups
    return SiteData(institution, articles[0], longread, event, story, program, profession)
