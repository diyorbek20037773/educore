"""Every factory builds a valid, saved object (T1.6)."""

from __future__ import annotations

import pytest
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import UserFactory
from apps.ai.tests.factories import AIBudgetDayFactory, AIRunFactory, EventClusterFactory
from apps.analytics.tests.factories import DailyStatFactory, InstitutionDailyStatFactory, SearchLogFactory
from apps.appeals.tests.factories import AppealFactory, AppealMessageFactory
from apps.content.tests.factories import (
    AdmissionFactory,
    ArticleFactory,
    ArticleMediaFactory,
    ArticleSourceFactory,
    CategoryFactory,
    EventFactory,
    StoryFactory,
    TagFactory,
)
from apps.core.tests.factories import FAQFactory, PageFactory
from apps.institutions.tests.factories import (
    InstitutionContactFactory,
    InstitutionFactory,
    InstitutionMetricFactory,
    ProfessionFactory,
    ProfessionInstitutionFactory,
    ProgramFactory,
)
from apps.ops.tests.factories import AlertEventFactory
from apps.telegram.tests.factories import (
    IngestionOutboxFactory,
    IngestionRequestFactory,
    TelegramMediaFactory,
    TelegramPostFactory,
    TelegramSourceFactory,
)

FACTORIES: list[type[DjangoModelFactory]] = [
    UserFactory, PageFactory, FAQFactory, InstitutionFactory, InstitutionContactFactory,
    InstitutionMetricFactory, ProgramFactory, ProfessionFactory, ProfessionInstitutionFactory,
    TelegramSourceFactory, TelegramPostFactory, TelegramMediaFactory, IngestionOutboxFactory,
    IngestionRequestFactory, AIRunFactory, AIBudgetDayFactory, EventClusterFactory, CategoryFactory,
    TagFactory, ArticleFactory, ArticleSourceFactory, ArticleMediaFactory, EventFactory, AdmissionFactory,
    StoryFactory, AppealFactory, AppealMessageFactory, DailyStatFactory, InstitutionDailyStatFactory,
    SearchLogFactory, AlertEventFactory,
]  # fmt: skip


@pytest.mark.django_db
@pytest.mark.parametrize("factory_cls", FACTORIES, ids=lambda f: f.__name__)
def test_factory_creates_valid_object(factory_cls: type[DjangoModelFactory]) -> None:
    obj = factory_cls()
    assert obj.pk is not None
    obj.full_clean(validate_unique=False)
    assert str(obj)
