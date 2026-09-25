"""Admin dashboard shows real rollup numbers (T5.3)."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from apps.analytics.models import DailyStat
from apps.ops.dashboard import activity_chart, ai_budget

pytestmark = pytest.mark.django_db


def test_activity_chart_uses_daily_stats() -> None:
    DailyStat.objects.create(date=timezone.localdate(), posts_ingested=7, articles_published=5, pageviews=40)
    context = activity_chart()
    data = json.loads(context["activity_chart"])
    assert len(data["labels"]) == 14
    assert data["datasets"][0]["data"][-1] == 7 and data["datasets"][1]["data"][-1] == 5
    assert context["pageviews_14"] == 40


def test_ai_budget_percent(monkeypatch: pytest.MonkeyPatch) -> None:
    from apps.ai import budget

    monkeypatch.setattr(budget, "spent_today", lambda: Decimal("2.5"))
    monkeypatch.setattr(budget, "daily_budget", lambda: Decimal("10"))
    assert ai_budget() == {"ai_spent_today": "2.50", "ai_budget": "10.00", "ai_budget_percent": 25}


def test_dashboard_renders_chart(verified_admin_client: Client) -> None:
    body = verified_admin_client.get(f"/{settings.ADMIN_URL_PATH}/").content.decode()
    assert 'data-type="bar"' in body and "AI xarajati" in body
