"""Home page and the live panel partial (SPEC §6.2)."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.content import selectors as content
from apps.web.services.home import home_context

LIVE_FILTERS = ("FVV", "IIV", "DBQ", "HMQA", "JXU")


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    context = home_context()
    context["live_filters"] = LIVE_FILTERS
    return render(request, "pages/home.html", context)


@require_GET
def live_panel(request: HttpRequest) -> HttpResponse:
    """HTMX: latest 12 published articles, optionally for one institution abbreviation."""
    abbreviation = request.GET.get("inst", "").upper()
    if abbreviation not in LIVE_FILTERS:
        abbreviation = ""
    articles = content.latest_articles(12, institution_abbr=abbreviation or None)
    known = {s for s in request.GET.get("seen", "").split(",") if s}
    return render(
        request,
        "partials/live_items.html",
        {"live_articles": articles, "active_filter": abbreviation, "seen_ids": known},
    )
