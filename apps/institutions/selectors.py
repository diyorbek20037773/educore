"""Read queries for institutions, programs and professions."""

from __future__ import annotations

from django.db.models import Prefetch, QuerySet

from apps.institutions.models import Institution, InstitutionMetric, Profession, Program


def active_institutions() -> list[Institution]:
    """All active institutions in fixed chart order (ADR-007)."""
    return list(Institution.objects.filter(is_active=True).order_by("order"))


def institution_detail(slug: str) -> Institution | None:
    return (
        Institution.objects.filter(slug=slug, is_active=True)
        .prefetch_related(
            "contacts",
            Prefetch("metrics", queryset=InstitutionMetric.objects.order_by("-year", "key")),
            "telegram_sources",
        )
        .first()
    )


def program_list(
    *, institution_slug: str | None = None, level: str | None = None, form: str | None = None
) -> QuerySet[Program]:
    qs = Program.objects.filter(is_active=True, institution__is_active=True).select_related("institution")
    if institution_slug:
        qs = qs.filter(institution__slug=institution_slug)
    if level:
        qs = qs.filter(level=level)
    if form:
        qs = qs.filter(form=form)
    return qs.order_by("institution__order", "level", "name")


def program_detail(institution_slug: str, slug: str) -> Program | None:
    return (
        Program.objects.select_related("institution")
        .prefetch_related("professions", "admissions")
        .filter(institution__slug=institution_slug, slug=slug, is_active=True)
        .first()
    )


def profession_list(*, institution_slug: str | None = None, query: str | None = None) -> QuerySet[Profession]:
    qs = Profession.objects.filter(is_published=True).prefetch_related(
        Prefetch("institutions", queryset=Institution.objects.order_by("order"))
    )
    if institution_slug:
        qs = qs.filter(institutions__slug=institution_slug)
    if query:
        qs = qs.filter(name__icontains=query)
    return qs.order_by("order", "name").distinct()


def profession_detail(slug: str) -> Profession | None:
    return (
        Profession.objects.filter(slug=slug, is_published=True)
        .prefetch_related(
            Prefetch("institutions", queryset=Institution.objects.order_by("order")),
            Prefetch("programs", queryset=Program.objects.select_related("institution")),
        )
        .first()
    )
