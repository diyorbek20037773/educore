"""Daily rollups: known counts, Asia/Tashkent day boundaries, empty days, rebuild and tasks (T5.4)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.core.management import call_command
from django.utils import timezone
from freezegun import freeze_time

from apps.ai.tests.factories import AIRunFactory
from apps.analytics.models import DailyStat, InstitutionDailyStat
from apps.analytics.services.aggregation import aggregate_day, day_bounds, rebuild, refresh_institution_stats
from apps.analytics.tasks import aggregate_daily
from apps.appeals.tests.factories import AppealFactory
from apps.content.tests.factories import ArticleFactory, CategoryFactory
from apps.institutions.tests.factories import InstitutionFactory
from apps.telegram.models import TelegramPost
from apps.telegram.tests.factories import TelegramPostFactory, TelegramSourceFactory

pytestmark = pytest.mark.django_db
DAY = date(2026, 9, 10)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


@pytest.fixture
def world() -> dict[str, Any]:
    first = InstitutionFactory(order=1, abbreviation="FVV", slug="fvv")
    second = InstitutionFactory(order=2, abbreviation="IIV", slug="iiv")
    return {
        "first": first,
        "second": second,
        "source": TelegramSourceFactory(institution=first),
        "other_source": TelegramSourceFactory(institution=second),
        "news": CategoryFactory(slug="yangiliklar"),
        "sport": CategoryFactory(slug="sport"),
    }


def test_day_bounds_are_tashkent_midnights() -> None:
    start, end = day_bounds(DAY)
    assert start == utc(2026, 9, 9, 19, 0) and end == utc(2026, 9, 10, 19, 0)


def test_known_counts(world: dict[str, Any]) -> None:
    # 09:30 and 23:30 local on DAY, plus 00:30 local on the next day (still 19:30 UTC of DAY).
    TelegramPostFactory(source=world["source"], published_at=utc(2026, 9, 10, 4, 30), views=100, forwards=3)
    TelegramPostFactory(source=world["source"], published_at=utc(2026, 9, 10, 18, 30), views=50, forwards=1)
    TelegramPostFactory(source=world["source"], published_at=utc(2026, 9, 10, 19, 30), views=999)
    TelegramPostFactory(source=world["other_source"], published_at=utc(2026, 9, 10, 6, 0), views=10)
    TelegramPostFactory(source=world["source"], published_at=utc(2026, 9, 10, 5, 0), is_deleted=True)
    ArticleFactory(
        primary_institution=world["first"], category=world["news"], published_at=utc(2026, 9, 10, 5, 0)
    )
    ArticleFactory(
        primary_institution=world["first"], category=world["sport"], published_at=utc(2026, 9, 10, 6, 0)
    )
    ArticleFactory(
        primary_institution=world["first"], category=world["sport"], content_type="event",
        published_at=utc(2026, 9, 10, 7, 0),
    )  # fmt: skip
    ArticleFactory(primary_institution=world["first"], review=True)

    stat = aggregate_day(DAY)

    first = InstitutionDailyStat.objects.get(date=DAY, institution=world["first"])
    assert first.posts == 2 and first.tg_views_sum == 150 and first.tg_forwards_sum == 4
    assert first.articles == 3
    assert first.by_category == {"yangiliklar": 1, "sport": 2}
    assert first.by_content_type == {"news": 2, "event": 1}
    assert first.by_hour[9] == 1 and first.by_hour[23] == 1 and sum(first.by_hour) == 2
    second = InstitutionDailyStat.objects.get(date=DAY, institution=world["second"])
    assert second.posts == 1 and second.articles == 0 and second.by_hour[11] == 1
    assert stat.articles_published == 3
    next_day = InstitutionDailyStat.objects.none()
    assert not next_day.exists()


def test_daily_totals_ai_and_appeals(world: dict[str, Any]) -> None:
    with freeze_time("2026-09-10 08:00:00+05:00"):
        AIRunFactory(cost_usd=Decimal("0.012500"))
        AIRunFactory(cost_usd=Decimal("0.002500"))
        AppealFactory(institution=world["first"])
        TelegramPostFactory(source=world["source"])
    stat = aggregate_day(DAY)
    assert stat.ai_runs == 2 and stat.ai_cost_usd == Decimal("0.015")
    assert stat.appeals_new == 1
    # AI runs are created with their own posts: every post created that local day counts.
    assert stat.posts_ingested == TelegramPost.objects.count()


def test_aggregation_is_idempotent_and_keeps_pageviews(world: dict[str, Any]) -> None:
    DailyStat.objects.create(date=DAY, pageviews=42, unique_visitors=7)
    TelegramPostFactory(source=world["source"], published_at=utc(2026, 9, 10, 4, 30))
    aggregate_day(DAY)
    aggregate_day(DAY)
    stat = DailyStat.objects.get(date=DAY)
    assert stat.pageviews == 42 and stat.unique_visitors == 7
    assert InstitutionDailyStat.objects.filter(date=DAY).count() == 2


def test_empty_day_creates_zero_rows(world: dict[str, Any]) -> None:
    stat = aggregate_day(DAY)
    assert stat.articles_published == 0
    row = InstitutionDailyStat.objects.get(date=DAY, institution=world["first"])
    assert row.posts == 0 and row.by_hour == [0] * 24 and row.by_category == {}


@freeze_time("2026-09-12 10:00:00+05:00")
def test_rebuild_and_command_cover_history(world: dict[str, Any]) -> None:
    TelegramPostFactory(source=world["source"], published_at=utc(2026, 9, 8, 6, 0))
    assert rebuild() == 5  # 8th … 12th
    assert InstitutionDailyStat.objects.filter(institution=world["first"]).count() == 5
    call_command("stats_rebuild", "--start", "2026-09-11")
    world["first"].refresh_from_db()
    assert world["first"].stats_cache["posts_30"] == 1


@freeze_time("2026-09-12 02:00:00+05:00")
def test_aggregate_daily_task_covers_last_week(world: dict[str, Any]) -> None:
    assert aggregate_daily.apply().get() == 8
    assert DailyStat.objects.filter(date=timezone.localdate()).exists()


def test_refresh_institution_stats(world: dict[str, Any]) -> None:
    ArticleFactory(primary_institution=world["first"], category=world["news"])
    rebuild(start=timezone.localdate(), end=timezone.localdate())
    assert refresh_institution_stats() == 2
    world["first"].refresh_from_db()
    assert world["first"].stats_cache["articles_total"] == 1
    assert world["first"].stats_cache["articles_30"] == 1
