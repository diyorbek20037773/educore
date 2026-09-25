"""Factories for aggregated statistics."""

from __future__ import annotations

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.analytics.models import DailyStat, InstitutionDailyStat, SearchLog
from apps.institutions.tests.factories import InstitutionFactory


class DailyStatFactory(DjangoModelFactory):
    class Meta:
        model = DailyStat
        django_get_or_create = ("date",)

    date = factory.LazyFunction(timezone.localdate)


class InstitutionDailyStatFactory(DjangoModelFactory):
    class Meta:
        model = InstitutionDailyStat

    date = factory.LazyFunction(timezone.localdate)
    institution = factory.SubFactory(InstitutionFactory)
    posts = 3
    articles = 2
    by_hour = factory.LazyFunction(lambda: [0] * 24)


class SearchLogFactory(DjangoModelFactory):
    class Meta:
        model = SearchLog

    query_norm = factory.Sequence(lambda n: f"qabul {n}")
    count = 1
    last_searched_at = factory.LazyFunction(timezone.now)
