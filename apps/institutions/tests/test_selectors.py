"""Institution/program/profession selectors: query counts and filters (T1.6)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from apps.institutions import selectors
from apps.institutions.tests.factories import (
    InstitutionContactFactory,
    InstitutionFactory,
    InstitutionMetricFactory,
    ProfessionFactory,
    ProfessionInstitutionFactory,
    ProgramFactory,
)

pytestmark = pytest.mark.django_db


def test_active_institutions_in_order() -> None:
    later = InstitutionFactory(order=5)
    first = InstitutionFactory(order=1)
    InstitutionFactory(order=3, is_active=False)
    assert selectors.active_institutions() == [first, later]


def test_institution_detail_prefetch(django_assert_num_queries: Callable[..., Any]) -> None:
    inst = InstitutionFactory()
    InstitutionContactFactory.create_batch(3, institution=inst)
    InstitutionMetricFactory(institution=inst, key="students")
    InstitutionMetricFactory(institution=inst, key="cadets")
    with django_assert_num_queries(4):
        found = selectors.institution_detail(inst.slug)
        assert found is not None
        assert len(found.contacts.all()) == 3
        assert len(found.metrics.all()) == 2
        _ = list(found.telegram_sources.all())


def test_program_list_filters_and_queries(django_assert_num_queries: Callable[..., Any]) -> None:
    inst = InstitutionFactory()
    ProgramFactory.create_batch(4, institution=inst, level="bakalavr")
    ProgramFactory(institution=inst, level="magistr")
    ProgramFactory.create_batch(3)
    with django_assert_num_queries(1):
        programs = list(selectors.program_list(institution_slug=inst.slug, level="bakalavr"))
        _ = [p.institution.short_name for p in programs]
    assert len(programs) == 4


def test_profession_list_prefetches_institutions(django_assert_num_queries: Callable[..., Any]) -> None:
    for _ in range(6):
        ProfessionInstitutionFactory(profession=ProfessionFactory())
    with django_assert_num_queries(2):
        professions = list(selectors.profession_list())
        _ = [[i.abbreviation for i in p.institutions.all()] for p in professions]
    assert len(professions) == 6


def test_program_and_profession_detail() -> None:
    program = ProgramFactory()
    link = ProfessionInstitutionFactory(institution=program.institution)
    program.professions.add(link.profession)
    assert selectors.program_detail(program.institution.slug, program.slug) == program
    detail = selectors.profession_detail(link.profession.slug)
    assert detail is not None and list(detail.programs.all()) == [program]
    assert selectors.profession_detail("missing") is None
