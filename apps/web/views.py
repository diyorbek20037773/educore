"""Public website views (thin; data comes from selectors)."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def home(request: HttpRequest) -> HttpResponse:
    """Home page placeholder until Phase 4 builds the full dashboard."""
    return render(request, "pages/home.html")
