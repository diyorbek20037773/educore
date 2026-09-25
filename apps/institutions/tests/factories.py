"""Factories for institutions, programs and professions."""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from apps.institutions.models import (
    Institution,
    InstitutionContact,
    InstitutionMetric,
    Profession,
    ProfessionInstitution,
    Program,
)

PALETTE = [
    ("#E4552F", "#B93A1E"),
    ("#2B6FD6", "#1F55B0"),
    ("#1FA463", "#177A49"),
    ("#9C4DC4", "#7A36A0"),
    ("#0E97A5", "#0B7381"),
]


class InstitutionFactory(DjangoModelFactory):
    class Meta:
        model = Institution
        django_get_or_create = ("slug",)

    order = factory.Sequence(lambda n: n + 1)
    slug = factory.Sequence(lambda n: f"muassasa-{n}")
    abbreviation = factory.Sequence(lambda n: f"M{n}")
    short_name = factory.Sequence(lambda n: f"Muassasa {n}")
    full_name = factory.LazyAttribute(lambda o: f"Oʻzbekiston Respublikasi {o.short_name}")
    kind = "academy"
    color = factory.LazyAttribute(lambda o: PALETTE[(o.order - 1) % 5][0])
    color_text = factory.LazyAttribute(lambda o: PALETTE[(o.order - 1) % 5][1])
    telegram_username = factory.Sequence(lambda n: f"channel_{n}")


class InstitutionContactFactory(DjangoModelFactory):
    class Meta:
        model = InstitutionContact

    institution = factory.SubFactory(InstitutionFactory)
    kind = "admissions"
    title = "Qabul komissiyasi"
    phone = "+998 71 000 00 00"


class InstitutionMetricFactory(DjangoModelFactory):
    class Meta:
        model = InstitutionMetric

    institution = factory.SubFactory(InstitutionFactory)
    year = 2026
    key = "students"
    value = 1200


class ProfessionFactory(DjangoModelFactory):
    class Meta:
        model = Profession

    slug = factory.Sequence(lambda n: f"kasb-{n}")
    name = factory.Sequence(lambda n: f"Kasb {n}")
    summary = "Qisqa tavsif"


class ProgramFactory(DjangoModelFactory):
    class Meta:
        model = Program

    institution = factory.SubFactory(InstitutionFactory)
    slug = factory.Sequence(lambda n: f"yonalish-{n}")
    name = factory.Sequence(lambda n: f"Yoʻnalish {n}")
    level = "bakalavr"
    form = "kunduzgi"
    duration_years = 4


class ProfessionInstitutionFactory(DjangoModelFactory):
    class Meta:
        model = ProfessionInstitution

    profession = factory.SubFactory(ProfessionFactory)
    institution = factory.SubFactory(InstitutionFactory)
