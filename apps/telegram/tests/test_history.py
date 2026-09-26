"""Backfill (grouping, idempotency, AI limit, FloodWait) and gap check (missing, edits, two-miss deletion)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest import mock

import pytest

from apps.telegram.ingestor import history
from apps.telegram.ingestor.media import MediaDownloader
from apps.telegram.ingestor.source_repository import SourceInfo
from apps.telegram.models import IngestionOutbox, TelegramPost, TelegramSource
from apps.telegram.tests.telethon_fixtures import FakeClient, load

pytestmark = pytest.mark.django_db
Run = Callable[..., Any]


def _history() -> list[Any]:
    return [*load("album_3_photos"), *load("single_photo"), *load("single_text"), *load("forwarded")]


def test_backfill_groups_albums_and_is_idempotent(run: Run, source: SourceInfo) -> None:
    client = FakeClient(_history())
    first = run(history.backfill, client, source, MediaDownloader(2), limit=500, ai_limit=150, wait_time=0)
    assert first == {"posts": 4, "events": 4}
    assert TelegramPost.objects.count() == 4
    assert TelegramPost.objects.get(grouped_id=777).media.count() == 3
    assert set(TelegramPost.objects.values_list("is_backfill", flat=True)) == {True}
    second = run(history.backfill, client, source, MediaDownloader(2), limit=500, ai_limit=150, wait_time=0)
    assert second["events"] == 0
    assert TelegramPost.objects.count() == 4
    assert TelegramSource.objects.get(pk=source.id).backfill_done_at is not None


def test_backfill_emits_events_only_for_newest_ai_limit(run: Run, source: SourceInfo) -> None:
    run(
        history.backfill,
        FakeClient(_history()),
        source,
        MediaDownloader(2),
        limit=500,
        ai_limit=2,
        wait_time=0,
    )
    assert IngestionOutbox.objects.count() == 2
    newest_two = set(TelegramPost.objects.order_by("-telegram_message_id").values_list("pk", flat=True)[:2])
    assert set(IngestionOutbox.objects.values_list("post_id", flat=True)) == newest_two
    assert TelegramPost.objects.filter(skip_reason="backfill_beyond_ai_limit").count() == 2


def test_backfill_respects_limit(run: Run, source: SourceInfo) -> None:
    run(
        history.backfill,
        FakeClient(_history()),
        source,
        MediaDownloader(2),
        limit=2,
        ai_limit=150,
        wait_time=0,
    )
    assert TelegramPost.objects.count() == 2


def test_backfill_honours_flood_wait(run: Run, source: SourceInfo) -> None:
    client = FakeClient(_history(), flood_once=True)
    with mock.patch("apps.telegram.ingestor.history.asyncio.sleep") as sleep:
        sleep.return_value = None

        async def no_sleep(_: float) -> None:
            return None

        sleep.side_effect = no_sleep
        result = run(
            history.backfill, client, source, MediaDownloader(2), limit=500, ai_limit=150, wait_time=0
        )
    sleep.assert_called_once_with(0)
    assert result["posts"] == 4


def test_gapcheck_ingests_missing_and_detects_edits(run: Run, source: SourceInfo) -> None:
    run(
        history.backfill,
        FakeClient(load("single_text")),
        source,
        MediaDownloader(2),
        limit=10,
        ai_limit=10,
        wait_time=0,
    )
    client = FakeClient([*load("edit_text"), *load("single_photo")])
    result = run(history.gapcheck, client, source, MediaDownloader(2))
    assert result["ingested"] == 1 and result["edited"] == 1
    assert IngestionOutbox.objects.filter(event_type="telegram.post.edited").count() == 1
    assert TelegramSource.objects.get(pk=source.id).last_gapcheck_at is not None


def test_gapcheck_deletes_only_after_two_consecutive_misses(run: Run, source: SourceInfo) -> None:
    everything = [*load("single_text"), *load("single_photo"), *load("forwarded")]
    run(
        history.backfill,
        FakeClient(everything),
        source,
        MediaDownloader(2),
        limit=10,
        ai_limit=10,
        wait_time=0,
    )
    without_102 = FakeClient([*load("single_text"), *load("forwarded")])
    run(history.gapcheck, without_102, source, MediaDownloader(2))
    assert not TelegramPost.objects.get(telegram_message_id=102).is_deleted
    result = run(history.gapcheck, without_102, source, MediaDownloader(2))
    assert result["deleted"] == 1
    assert TelegramPost.objects.get(telegram_message_id=102).is_deleted


def test_gapcheck_resets_miss_counter_when_seen_again(run: Run, source: SourceInfo) -> None:
    everything = [*load("single_text"), *load("single_photo"), *load("forwarded")]
    run(
        history.backfill,
        FakeClient(everything),
        source,
        MediaDownloader(2),
        limit=10,
        ai_limit=10,
        wait_time=0,
    )
    run(history.gapcheck, FakeClient([*load("single_text"), *load("forwarded")]), source, MediaDownloader(2))
    run(history.gapcheck, FakeClient(everything), source, MediaDownloader(2))
    run(history.gapcheck, FakeClient([*load("single_text"), *load("forwarded")]), source, MediaDownloader(2))
    assert not TelegramPost.objects.get(telegram_message_id=102).is_deleted


def test_refresh_engagement_updates_counters(run: Run, source: SourceInfo) -> None:
    run(
        history.backfill,
        FakeClient(load("single_text")),
        source,
        MediaDownloader(2),
        limit=10,
        ai_limit=10,
        wait_time=0,
    )
    result = run(history.refresh_engagement, FakeClient(load("edit_views_only")), source)
    assert result == {"posts": 1}
    assert TelegramPost.objects.get().views == 4200


def test_retry_media_downloads_again(run: Run, source: SourceInfo) -> None:
    run(
        history.backfill, FakeClient(load("single_photo"), fail_downloads=True), source, MediaDownloader(2),
        limit=10, ai_limit=10, wait_time=0,
    )  # fmt: skip
    media = TelegramPost.objects.get().media.get()
    assert media.status == "failed"
    result = run(history.retry_media, FakeClient(load("single_photo")), MediaDownloader(2), [media.pk])
    assert result == {"downloaded": 1, "requested": 1}
    media.refresh_from_db()
    assert media.status == "downloaded" and media.original


def test_default_ai_limit_covers_every_post_in_verbatim_mode(settings: Any) -> None:
    settings.BACKFILL_AI_LIMIT_PER_SOURCE = 150
    settings.CONTENT_MODE = "verbatim"
    assert history.default_ai_limit(500) == 500
    settings.CONTENT_MODE = "ai"
    assert history.default_ai_limit(500) == 150
