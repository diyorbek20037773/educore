"""Institution list, profile tabs and comparison (SPEC §6.3)."""

from __future__ import annotations

import csv
from collections import defaultdict
from typing import Any

from django.core.cache import cache
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from apps.content import selectors as content
from apps.core.cache import content_version
from apps.core.models import FAQ, FAQTopic
from apps.institutions import selectors
from apps.institutions.models import Institution, InstitutionMetric, MetricKey
from apps.web.services.home import cached, institution_cards
from apps.web.services.showcase import activity_totals, build_showcase, split_rails
from apps.web.views._helpers import breadcrumbs, is_htmx, paginate

TABS = (
    ("institution_detail", "Umumiy"),
    ("institution_programs", "Yoʻnalishlar"),
    ("institution_admissions", "Qabul"),
    ("institution_life", "Talabalar va kursantlar"),
    ("institution_news", "Yangiliklar"),
    ("institution_events", "Tadbirlar"),
    ("institution_contacts", "Aloqa"),
)


@require_GET
def institution_list(request: HttpRequest) -> HttpResponse:
    cards = cached("institutions", institution_cards)
    showcase = build_showcase(cards, cached("showcase_totals", activity_totals))
    rail_left, rail_right = split_rails(showcase)
    context = {
        "institution_cards": cards,
        "showcase": showcase,
        "rail_left": rail_left,
        "rail_right": rail_right,
        **breadcrumbs(request, (_("Muassasalar"), request.path)),
    }
    return render(request, "pages/institutions/list.html", context)


def _metric_table() -> tuple[list[Institution], list[dict[str, Any]]]:
    """Rows: metric × institutions, latest year each (with `needs_verification` marks)."""
    institutions = selectors.active_institutions()
    latest: dict[tuple[int, str], InstitutionMetric] = {}
    for metric in InstitutionMetric.objects.filter(institution__is_active=True).order_by("year"):
        latest[(metric.institution_id, metric.key)] = metric
    rows = []
    for key, label in MetricKey.choices:
        cells = [latest.get((i.pk, key)) for i in institutions]
        if any(cell is not None and cell.value is not None for cell in cells):
            rows.append({"key": key, "label": label, "cells": cells})
    return institutions, rows


@require_GET
def compare(request: HttpRequest) -> HttpResponse:
    key = f"web:compare:{content_version()}"
    table = cache.get(key)
    if table is None:
        table = _metric_table()
        cache.set(key, table, 300)
    institutions, rows = table
    context = {
        "institutions": institutions,
        "rows": rows,
        **breadcrumbs(
            request, (_("Muassasalar"), _url("web:institution_list")), (_("Taqqoslash"), request.path)
        ),
    }
    return render(request, "pages/institutions/compare.html", context)


@require_GET
def compare_csv(request: HttpRequest) -> HttpResponse:
    institutions, rows = _metric_table()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="educore-taqqoslash.csv"'
    writer = csv.writer(response)
    writer.writerow([_("Koʻrsatkich"), *[i.short_name for i in institutions]])
    for row in rows:
        writer.writerow(
            [row["label"], *[(c.value if c and c.value is not None else "") for c in row["cells"]]]
        )
    return response


def _url(name: str, **kwargs: Any) -> str:
    from django.urls import reverse

    return reverse(name, kwargs=kwargs or None)


def _institution_context(
    request: HttpRequest, slug: str, tab: str, label: str | None = None
) -> dict[str, Any]:
    institution = selectors.institution_detail(slug)
    if institution is None:
        raise Http404
    tabs = [{"name": name, "label": _(title), "url": _url(f"web:{name}", slug=slug)} for name, title in TABS]
    crumbs: list[tuple[str, str]] = [
        (_("Muassasalar"), _url("web:institution_list")),
        (institution.short_name, _url("web:institution_detail", slug=slug)),
    ]
    if label:
        crumbs.append((label, request.path))
    return {
        "institution": institution,
        "tabs": tabs,
        "active_tab": tab,
        "subscribers": sum(s.subscribers_count or 0 for s in institution.telegram_sources.all()),
        **breadcrumbs(request, *crumbs),
    }


@require_GET
def overview(request: HttpRequest, slug: str) -> HttpResponse:
    context = _institution_context(request, slug, "institution_detail")
    institution: Institution = context["institution"]
    metrics: dict[str, InstitutionMetric] = {}
    for metric in institution.metrics.all():  # newest year first
        metrics.setdefault(metric.key, metric)
    context["metrics"] = list(metrics.values())
    context["latest_articles"] = list(
        content.published_articles().filter(institutions=institution).order_by("-published_at").distinct()[:4]
    )
    context["chart_query"] = f"inst={institution.slug}"
    return render(request, "pages/institutions/overview.html", context)


@require_GET
def programs(request: HttpRequest, slug: str) -> HttpResponse:
    context = _institution_context(request, slug, "institution_programs", _("Yoʻnalishlar"))
    grouped: dict[str, list[Any]] = defaultdict(list)
    for program in selectors.program_list(institution_slug=slug):
        grouped[program.get_level_display()].append(program)
    context["program_groups"] = dict(grouped)
    return render(request, "pages/institutions/programs.html", context)


@require_GET
def admissions(request: HttpRequest, slug: str) -> HttpResponse:
    context = _institution_context(request, slug, "institution_admissions", _("Qabul"))
    context["admissions"] = [
        a for a in content.open_admissions() if a.institution_id == context["institution"].pk
    ]
    context["faqs"] = FAQ.objects.filter(
        is_published=True, topic=FAQTopic.QABUL, institution=context["institution"]
    ).order_by("order")
    return render(request, "pages/institutions/admissions.html", context)


@require_GET
def life(request: HttpRequest, slug: str) -> HttpResponse:
    context = _institution_context(request, slug, "institution_life", _("Talabalar va kursantlar"))
    institution = context["institution"]
    context["articles"] = list(
        content.published_articles()
        .filter(institutions=institution, category__slug__in=["kursantlar", "talabalar"])
        .order_by("-published_at")
        .distinct()[:9]
    )
    context["faqs"] = FAQ.objects.filter(
        is_published=True, topic__in=[FAQTopic.KURSANT, FAQTopic.TALABA], institution=institution
    ).order_by("order")
    return render(request, "pages/institutions/life.html", context)


@require_GET
def news(request: HttpRequest, slug: str) -> HttpResponse:
    context = _institution_context(request, slug, "institution_news", _("Yangiliklar"))
    page = paginate(request, content.article_list(institution_slug=slug), per_page=24)
    context["page_obj"] = page
    if is_htmx(request) and request.GET.get("page"):
        return render(request, "partials/article_grid_page.html", context)
    return render(request, "pages/institutions/news.html", context)


@require_GET
def events(request: HttpRequest, slug: str) -> HttpResponse:
    context = _institution_context(request, slug, "institution_events", _("Tadbirlar"))
    context["upcoming"] = content.upcoming_events(20, institution_slug=slug)
    context["past"] = list(
        context["institution"]
        .events.filter(is_published=True)
        .exclude(pk__in=[e.pk for e in context["upcoming"]])
        .order_by("-starts_at")[:10]
    )
    return render(request, "pages/institutions/events.html", context)


@require_GET
def contacts(request: HttpRequest, slug: str) -> HttpResponse:
    context = _institution_context(request, slug, "institution_contacts", _("Aloqa"))
    return render(request, "pages/institutions/contacts.html", context)
