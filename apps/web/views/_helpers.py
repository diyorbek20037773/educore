"""Shared view helpers: breadcrumbs (+ JSON-LD), pagination, HTMX partial selection."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.paginator import EmptyPage, Page, Paginator
from django.http import HttpRequest
from django.utils.translation import gettext as _


def breadcrumbs(request: HttpRequest, *items: tuple[str, str]) -> dict[str, Any]:
    """Context for `components/breadcrumbs.html` with a `BreadcrumbList` JSON-LD payload."""
    elements = [
        {"@type": "ListItem", "position": 1, "name": _("Bosh sahifa"), "item": f"{settings.SITE_URL}/"}
    ]
    for index, (label, url) in enumerate(items, start=2):
        elements.append(
            {"@type": "ListItem", "position": index, "name": str(label), "item": f"{settings.SITE_URL}{url}"}
        )
    return {
        "crumbs": list(items),
        "breadcrumb_ld": {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": elements,
        },
    }


def paginate(request: HttpRequest, queryset: Any, per_page: int = 24) -> Page:
    paginator = Paginator(queryset, per_page)
    try:
        number = int(request.GET.get("page", "1"))
    except ValueError:
        number = 1
    try:
        return paginator.page(number)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def is_htmx(request: HttpRequest) -> bool:
    """True for HTMX fragment requests; boosted navigation and history restores need the full page."""
    htmx = getattr(request, "htmx", None)
    return bool(htmx) and not htmx.boosted and not htmx.history_restore_request
