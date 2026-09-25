"""Translated fields (`_uz`, `_uz_cyrl`, `_ru`, `_en`) for the institutions app (SPEC §2 fields marked *)."""

from __future__ import annotations

from modeltranslation.translator import TranslationOptions, register

from apps.institutions.models import (
    Institution,
    InstitutionContact,
    InstitutionMetric,
    Profession,
    ProfessionInstitution,
    Program,
)


@register(Institution)
class InstitutionTranslationOptions(TranslationOptions):
    fields = ("short_name", "full_name", "parent_body", "description", "mission", "address", "city")


@register(InstitutionContact)
class InstitutionContactTranslationOptions(TranslationOptions):
    fields = ("title", "hours")


@register(InstitutionMetric)
class InstitutionMetricTranslationOptions(TranslationOptions):
    fields = ("unit", "note")


@register(Program)
class ProgramTranslationOptions(TranslationOptions):
    fields = ("name", "language", "description", "admission_requirements", "qualification", "tuition_note")


@register(Profession)
class ProfessionTranslationOptions(TranslationOptions):
    fields = (
        "name",
        "summary",
        "description",
        "responsibilities",
        "requirements",
        "education_path",
        "rank_system",
        "work_places",
        "salary_note",
    )


@register(ProfessionInstitution)
class ProfessionInstitutionTranslationOptions(TranslationOptions):
    fields = ("note",)
