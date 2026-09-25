"""Shared fixtures for AI pipeline tests (mock provider + fake embeddings are enforced by test settings)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone

from apps.ai.providers import reset_provider_cache
from apps.core.services.seeding import seed_reference_data
from apps.institutions.models import Institution
from apps.telegram.ingestor.repository import finalize_post
from apps.telegram.models import IngestionOutbox, TelegramPost, TelegramSource
from apps.telegram.tests.factories import TelegramMediaFactory, TelegramPostFactory

NEWS = (
    "IIV Akademiyasida «Ochiq eshiklar kuni» tadbiri boʻlib oʻtdi. Tadbirda abituriyentlar va ularning "
    "ota-onalari akademiyaning oʻquv binolari, sport majmuasi va yotoqxonasi bilan tanishdi. Akademiya "
    "rahbariyati qabul tartibi, taʼlim yoʻnalishlari va kursantlar hayoti haqida batafsil maʼlumot berdi. "
    "#ochiqeshiklar #qabul2026"
)


@pytest.fixture(autouse=True)
def _mock_provider(settings: Any) -> None:
    settings.AI_PROVIDER = "mock"
    settings.PUBLISH_MODE = "auto"
    settings.AI_TRANSLATE_TO = []
    reset_provider_cache()


@pytest.fixture
def seeded(db: Any) -> None:
    seed_reference_data()
    from apps.core.models import SiteSetting

    SiteSetting.objects.filter(pk=1).update(publish_mode="auto", ai_translate_to=[])
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def make_post(seeded: None) -> Callable[..., TelegramPost]:
    """Create a finalized post (with outbox event) for an institution by abbreviation."""

    def _make(
        text: str = NEWS,
        abbreviation: str = "IIV",
        *,
        photos: int = 1,
        minutes_ago: int = 30,
        message_id: int | None = None,
    ) -> TelegramPost:
        institution = Institution.objects.get(abbreviation=abbreviation)
        source = TelegramSource.objects.get(institution=institution)
        kwargs: dict[str, Any] = {
            "source": source,
            "text": text,
            "content_hash": "",
            "published_at": timezone.now() - timedelta(minutes=minutes_ago),
        }
        if message_id is not None:
            kwargs["telegram_message_id"] = message_id
        post = TelegramPostFactory(**kwargs)
        for i in range(photos):
            TelegramMediaFactory(
                post=post,
                telegram_message_id=post.telegram_message_id + i,
                order=i,
                original=f"telegram/x/{post.pk}/{i}.jpg",
                width=1000 + 100 * i,
            )
        post.media_count = photos
        post.has_media = bool(photos)
        post.save()
        finalize_post(post.pk)
        post.refresh_from_db()
        return post

    return _make


def outbox_for(post: TelegramPost) -> IngestionOutbox:
    return IngestionOutbox.objects.filter(post=post).order_by("-created_at").first()  # type: ignore[return-value]
