"""Core middleware."""

from __future__ import annotations

from collections.abc import Callable

from csp.constants import SELF, UNSAFE_EVAL, UNSAFE_INLINE
from csp.middleware import CSPMiddleware
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseBase, JsonResponse

from apps.core import health
from apps.core.net import ip_in_cidrs


class HealthMiddleware:
    """Answer `/healthz` and `/readyz` before host validation and SSL redirects.

    Container health checks call these with arbitrary Host headers over plain HTTP, so the
    middleware sits before `SecurityMiddleware`/`CommonMiddleware` (ADR-010).
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        path = request.path_info.rstrip("/")
        if path == "/healthz":
            payload = health.liveness()
            return self._json(payload)
        if path == "/readyz":
            detailed = ip_in_cidrs(request.META.get("REMOTE_ADDR"), settings.METRICS_IP_ALLOWLIST)
            return self._json(health.readiness(detailed=detailed))
        return self.get_response(request)

    @staticmethod
    def _json(payload: dict[str, object]) -> JsonResponse:
        status = 200 if payload.get("status") == "ok" else 503
        response = JsonResponse(payload, status=status)
        response["Cache-Control"] = "no-store"
        return response


class EducoreCSPMiddleware(CSPMiddleware):
    """django-csp with a relaxed policy for the admin only (ADR-020).

    Unfold's admin relies on Alpine expressions and inline styles that need `unsafe-eval`/`unsafe-inline`;
    the public site keeps the strict nonce policy. The admin path is secret and 2FA-protected.
    """

    def process_response(self, request: HttpRequest, response: HttpResponseBase) -> HttpResponseBase:
        if request.path_info.startswith(f"/{settings.ADMIN_URL_PATH}/"):
            response._csp_replace = {  # type: ignore[attr-defined]
                "script-src": [SELF, UNSAFE_INLINE, UNSAFE_EVAL],
                "style-src": [SELF, UNSAFE_INLINE],
                "img-src": [SELF, "data:", "blob:"],
            }
        return super().process_response(request, response)
