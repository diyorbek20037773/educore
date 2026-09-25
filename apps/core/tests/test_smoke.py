"""Phase 0 smoke tests: settings import, health endpoints, Celery app."""

from __future__ import annotations

import importlib

import pytest
from django.conf import settings
from django.test import Client


def test_settings_modules_import() -> None:
    for name in ("config.settings.base", "config.settings.dev", "config.settings.test"):
        assert importlib.import_module(name)
    assert settings.AI_PROVIDER == "mock"
    assert settings.AUTH_USER_MODEL == "accounts.User"


@pytest.mark.django_db
def test_healthz_ok(client: Client) -> None:
    response = client.get("/healthz", HTTP_HOST="any-host.invalid")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readyz_hides_detail_for_public(client: Client) -> None:
    response = client.get("/readyz", REMOTE_ADDR="203.0.113.7")
    assert response.status_code == 200
    assert set(response.json()) == {"status"}


@pytest.mark.django_db
def test_readyz_detail_for_allowlisted(client: Client) -> None:
    response = client.get("/readyz", REMOTE_ADDR="127.0.0.1")
    body = response.json()
    assert body["checks"] == {"database": True, "redis": True, "migrations": True}
    assert "ingestor_heartbeat_age_seconds" in body
    assert body["sources"] == []


def test_metrics_forbidden_outside_allowlist(client: Client) -> None:
    assert client.get("/metrics", REMOTE_ADDR="203.0.113.7").status_code == 403


def test_celery_app_loads() -> None:
    from config.celery import app, ping

    assert app.main == "educore"
    assert {q.name for q in app.conf.task_queues} == {"default", "ingest", "ai", "media"}
    assert ping.delay().get(timeout=5) == "pong"


@pytest.mark.django_db
def test_home_renders(client: Client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert b"EDUCORE" in response.content
