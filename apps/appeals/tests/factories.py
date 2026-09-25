"""Factories for appeals."""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.appeals.models import Appeal, AppealMessage
from apps.institutions.tests.factories import InstitutionFactory


class AppealFactory(DjangoModelFactory):
    class Meta:
        model = Appeal

    tracking_code = factory.Sequence(lambda n: f"EDC-2026-{n:06d}")
    institution = factory.SubFactory(InstitutionFactory)
    topic = "qabul"
    full_name = factory.Faker("name")
    phone = "+998901234567"
    message = "Qabul jarayoni boʻyicha qoʻshimcha maʼlumot olmoqchiman."
    consent = True


class AppealMessageFactory(DjangoModelFactory):
    class Meta:
        model = AppealMessage

    appeal = factory.SubFactory(AppealFactory)
    body = "Murojaatingiz koʻrib chiqilmoqda."
    is_public = True
