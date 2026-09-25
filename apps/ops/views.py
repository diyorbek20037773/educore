"""Ops endpoints: Prometheus metrics behind an IP allowlist."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django_prometheus.exports import ExportToDjangoView

from apps.core.net import ip_in_cidrs


def metrics(request: HttpRequest) -> HttpResponse:
    """Expose Prometheus metrics only to `METRICS_IP_ALLOWLIST` (compose subnet + localhost)."""
    if not ip_in_cidrs(request.META.get("REMOTE_ADDR"), settings.METRICS_IP_ALLOWLIST):
        return HttpResponseForbidden("forbidden")
    return ExportToDjangoView(request)
