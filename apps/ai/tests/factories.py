"""Factories for AI bookkeeping models."""

from __future__ import annotations

from decimal import Decimal

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.ai.models import AIBudgetDay, AIRun, EventCluster
from apps.telegram.tests.factories import TelegramPostFactory


class AIRunFactory(DjangoModelFactory):
    class Meta:
        model = AIRun

    post = factory.SubFactory(TelegramPostFactory)
    stage = "extract"
    provider = "mock"
    model = "mock-fast"
    prompt_version = "v1"
    status = "ok"
    input_tokens = 1000
    output_tokens = 200
    cost_usd = Decimal("0.002000")
    output = factory.LazyFunction(dict)


class AIBudgetDayFactory(DjangoModelFactory):
    class Meta:
        model = AIBudgetDay
        django_get_or_create = ("date",)

    date = factory.LazyFunction(timezone.localdate)


class EventClusterFactory(DjangoModelFactory):
    class Meta:
        model = EventCluster

    title = factory.Sequence(lambda n: f"Klaster {n}")
    first_seen_at = factory.LazyFunction(timezone.now)
    last_seen_at = factory.LazyFunction(timezone.now)
