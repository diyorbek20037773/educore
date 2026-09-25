"""Public-site middleware: maintenance mode and cache-correct HTMX responses."""

from __future__ import annotations

from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.utils.cache import patch_vary_headers

from apps.core.models import SiteSetting

EXEMPT_PREFIXES = ("/static/", "/media/", "/i18n/", "/metrics")


class MaintenanceMiddleware:
    """Serve the 503 page while `SiteSetting.maintenance_mode` is on; staff and the admin keep working."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path_info
        exempt = path.startswith(EXEMPT_PREFIXES) or path.startswith(f"/{settings.ADMIN_URL_PATH}/")
        if not exempt and not request.user.is_staff and SiteSetting.get().maintenance_mode:
            response = HttpResponse(render_to_string("errors/503.html"), status=503)
            response["Retry-After"] = "600"
            response["Cache-Control"] = "no-store"
            return response
        return self.get_response(request)


class HtmxVaryMiddleware:
    """Fragments and full pages share URLs, so shared caches must key on the HTMX headers."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        patch_vary_headers(response, ("HX-Request", "HX-Boosted", "HX-History-Restore-Request"))
        return response
