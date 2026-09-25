"""Professions catalogue and detail (SPEC §6.6)."""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from apps.content import selectors as content
from apps.institutions import selectors
from apps.web.views._helpers import breadcrumbs, is_htmx


@require_GET
def profession_list(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "").strip()[:100]
    institution = request.GET.get("inst") or None
    context = {
        "professions": list(selectors.profession_list(institution_slug=institution, query=query or None)),
        "institutions": selectors.active_institutions(),
        "filters": {"q": query, "inst": institution},
    }
    if is_htmx(request):
        return render(request, "partials/profession_results.html", context)
    context.update(breadcrumbs(request, (_("Kasblar"), request.path)))
    return render(request, "pages/professions/list.html", context)


@require_GET
def profession_detail(request: HttpRequest, slug: str) -> HttpResponse:
    profession = selectors.profession_detail(slug)
    if profession is None:
        raise Http404
    institutions = list(profession.institutions.all())
    context = {
        "profession": profession,
        "institutions": institutions,
        "programs": list(profession.programs.all()),
        "articles": list(
            content.published_articles()
            .filter(institutions__in=institutions, category__slug__in=["kasblar", "kursantlar", "talabalar"])
            .order_by("-published_at")
            .distinct()[:3]
        ),
        **breadcrumbs(
            request, (_("Kasblar"), reverse("web:profession_list")), (profession.name, request.path)
        ),
    }
    return render(request, "pages/professions/detail.html", context)
