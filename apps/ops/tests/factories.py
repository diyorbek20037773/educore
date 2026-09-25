"""Factories for ops models."""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.ops.models import AlertEvent


class AlertEventFactory(DjangoModelFactory):
    class Meta:
        model = AlertEvent

    kind = "ingestor_heartbeat_stale"
    dedupe_key = factory.Sequence(lambda n: f"alert-{n}")
    message = "Ingestor heartbeat is stale."
