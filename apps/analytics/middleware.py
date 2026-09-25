"""Count public page views (full HTML pages only; no bots, staff, admin, fragments or errors)."""

from __future__ import annotations

import re
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from apps.analytics.services.pageviews import record_pageview

BOT_RE = re.compile(r"bot|crawl|spider|slurp|headless|lighthouse|monitor|curl|wget|python", re.IGNORECASE)
SKIP_PREFIXES = ("/static/", "/media/", "/partials/", "/metrics", "/healthz", "/readyz", "/i18n/")


class PageViewMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if self._countable(request, response):
            record_pageview(request.META.get("REMOTE_ADDR", ""), request.META.get("HTTP_USER_AGENT", ""))
        return response

    @staticmethod
    def _countable(request: HttpRequest, response: HttpResponse) -> bool:
        if request.method != "GET" or response.status_code != 200:
            return False
        if not response.get("Content-Type", "").startswith("text/html"):
            return False
        path = request.path_info
        if path.startswith(SKIP_PREFIXES) or path.startswith(f"/{settings.ADMIN_URL_PATH}/"):
            return False
        htmx = getattr(request, "htmx", None)
        if htmx and not htmx.boosted:  # fragments are not page views; boosted navigation is
            return False
        user = getattr(request, "user", None)
        if user is not None and user.is_staff:
            return False
        return not BOT_RE.search(request.META.get("HTTP_USER_AGENT", ""))
