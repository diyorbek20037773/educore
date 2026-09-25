"""Trusted proxy IP resolution, maintenance mode and HTMX-aware caching headers (T4.6)."""

from __future__ import annotations

from typing import Any

import pytest
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory, override_settings

from apps.core.middleware import TrustedProxyMiddleware
from apps.core.models import SiteSetting


def _resolve(remote: str, forwarded: str | None) -> str:
    request = RequestFactory().get("/", REMOTE_ADDR=remote)
    if forwarded is not None:
        request.META["HTTP_X_FORWARDED_FOR"] = forwarded
    seen: dict[str, str] = {}

    def view(req: HttpRequest) -> HttpResponse:
        seen["ip"] = req.META["REMOTE_ADDR"]
        return HttpResponse()

    TrustedProxyMiddleware(view)(request)
    return seen["ip"]


@override_settings(TRUSTED_PROXY_CIDRS=["172.16.0.0/12"])
@pytest.mark.parametrize(
    "remote,forwarded,expected",
    [
        ("172.18.0.5", "203.0.113.7, 10.0.0.1", "203.0.113.7"),  # from Caddy: first hop wins
        ("198.51.100.4", "203.0.113.7", "198.51.100.4"),  # untrusted peer: header ignored
        ("172.18.0.5", None, "172.18.0.5"),
        ("172.18.0.5", "not-an-ip", "172.18.0.5"),
        ("172.18.0.5", "2001:db8::1", "2001:db8::1"),
    ],
)
def test_trusted_proxy_resolution(remote: str, forwarded: str | None, expected: str) -> None:
    assert _resolve(remote, forwarded) == expected


@pytest.fixture
def maintenance(db: Any) -> Any:
    setting = SiteSetting.get()
    setting.maintenance_mode = True
    setting.save()
    cache.clear()
    yield setting
    cache.clear()


def test_maintenance_mode_serves_503(client: Client, maintenance: Any) -> None:
    response = client.get("/")
    assert response.status_code == 503
    assert response["Retry-After"] == "600"
    assert "texnik ishlar" in response.content.decode()
    assert client.get("/healthz").status_code == 200


def test_maintenance_mode_lets_staff_through(verified_admin_client: Client, maintenance: Any) -> None:
    assert verified_admin_client.get("/").status_code == 200


def test_security_and_vary_headers(client: Client, db: Any) -> None:
    response = client.get("/robots.txt")
    assert "HX-Request" in response["Vary"] and "HX-Boosted" in response["Vary"]
    assert "camera=()" in response["Permissions-Policy"]
    home = client.get("/")
    assert home["X-Content-Type-Options"] == "nosniff"
    assert home["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert (
        "nonce-" in home["Content-Security-Policy"] and "unsafe-eval" not in home["Content-Security-Policy"]
    )
