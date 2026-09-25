"""Search page and HTMX suggestions (SPEC §6.11), rate-limited per IP."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET
from django_ratelimit.decorators import ratelimit

from apps.web.services.search import search as run_search
from apps.web.services.search import suggestions
from apps.web.views._helpers import breadcrumbs


@require_GET
@ratelimit(key="ip", rate="30/m", block=True)
def search(request: HttpRequest) -> HttpResponse:
    raw = request.GET.get("q", "")
    context = {
        "q": raw.strip()[:100],
        "results": run_search(raw) if raw.strip() else None,
        **breadcrumbs(request, (_("Qidiruv"), request.path)),
    }
    return render(request, "pages/search.html", context)


@require_GET
@ratelimit(key="ip", rate="60/m", block=True)
def suggest(request: HttpRequest) -> HttpResponse:
    return render(request, "partials/search_suggest.html", {"items": suggestions(request.GET.get("q", ""))})
