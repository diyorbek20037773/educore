"""Factories for Telegram ingestion models."""

from __future__ import annotations

import hashlib

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.institutions.tests.factories import InstitutionFactory
from apps.telegram.models import (
    IngestionOutbox,
    IngestionRequest,
    TelegramMedia,
    TelegramPost,
    TelegramSource,
)


class TelegramSourceFactory(DjangoModelFactory):
    class Meta:
        model = TelegramSource
        django_get_or_create = ("username",)

    institution = factory.SubFactory(InstitutionFactory)
    username = factory.LazyAttribute(lambda o: o.institution.telegram_username.lower())
    title = factory.LazyAttribute(lambda o: o.institution.short_name)
    telegram_channel_id = factory.Sequence(lambda n: 1_000_000_000 + n)
    status = "live"


class TelegramPostFactory(DjangoModelFactory):
    class Meta:
        model = TelegramPost

    source = factory.SubFactory(TelegramSourceFactory)
    telegram_message_id = factory.Sequence(lambda n: 1000 + n)
    text = factory.Sequence(
        lambda n: f"Akademiyada {n}-sonli ochiq eshiklar kuni boʻlib oʻtdi va unda kursantlar ishtirok etdi."
    )
    published_at = factory.LazyFunction(timezone.now)
    telegram_url = factory.LazyAttribute(
        lambda o: f"https://t.me/{o.source.username}/{o.telegram_message_id}"
    )
    content_hash = factory.LazyAttribute(lambda o: hashlib.sha256(o.text.encode()).hexdigest())
    views = 100


class TelegramMediaFactory(DjangoModelFactory):
    class Meta:
        model = TelegramMedia

    post = factory.SubFactory(TelegramPostFactory)
    telegram_message_id = factory.LazyAttribute(lambda o: o.post.telegram_message_id)
    kind = "photo"
    mime_type = "image/jpeg"
    width = 1280
    height = 853
    status = "downloaded"


class IngestionOutboxFactory(DjangoModelFactory):
    class Meta:
        model = IngestionOutbox

    post = factory.SubFactory(TelegramPostFactory)
    event_type = "telegram.post.created"
    payload = factory.LazyAttribute(lambda o: {"post_id": o.post.pk, "content_hash": o.post.content_hash})
    payload_hash = factory.LazyAttribute(lambda o: o.post.content_hash)


class IngestionRequestFactory(DjangoModelFactory):
    class Meta:
        model = IngestionRequest

    kind = "backfill"
    source = factory.SubFactory(TelegramSourceFactory)
    params = factory.LazyFunction(lambda: {"limit": 10, "ai_limit": 5})
