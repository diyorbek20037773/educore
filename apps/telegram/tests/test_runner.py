"""Ingestor runner: handlers, source refresh (new source without restart), leadership, unauthorized exit."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any
from unittest import mock

import pytest

from apps.ops.models import AlertEvent
from apps.telegram.ingestor.leader import LEADER_KEY, LeaderLock
from apps.telegram.ingestor.pipeline import marked_channel_id
from apps.telegram.ingestor.runner import EXIT_LOST_LEADERSHIP, EXIT_UNAUTHORIZED, Ingestor
from apps.telegram.models import IngestionOutbox, TelegramPost, TelegramSource
from apps.telegram.tests.factories import TelegramSourceFactory
from apps.telegram.tests.telethon_fixtures import CHANNEL_ID, FakeClient, FakeEvent, load

pytestmark = pytest.mark.django_db
Run = Callable[..., Any]
CHAT = marked_channel_id(CHANNEL_ID)


def _ingestor(client: FakeClient, redis_clean: Any) -> Ingestor:
    return Ingestor(client, redis_clean, lock=LeaderLock(redis_clean, owner="test:1"))


def test_refresh_sources_resolves_new_source_and_registers_handlers(run: Run, redis_clean: Any) -> None:
    new = TelegramSourceFactory(telegram_channel_id=None, access_hash=None, status="offline")
    client = FakeClient()
    ingestor = _ingestor(client, redis_clean)
    run(ingestor.refresh_sources)
    new.refresh_from_db()
    assert (new.telegram_channel_id, new.status, new.subscribers_count) == (CHANNEL_ID, "live", 15000)
    assert new.about_text == "Rasmiy kanal" and new.joined_at is not None
    assert list(ingestor.sources) == [CHAT]
    assert len(client.handlers) == 4
    run(ingestor.refresh_sources)  # unchanged chat list → handlers not re-registered twice
    assert len(client.handlers) == 4


def test_handlers_ingest_edit_and_delete(run: Run, redis_clean: Any, source_row: TelegramSource) -> None:
    ingestor = _ingestor(FakeClient(load("single_photo")), redis_clean)
    run(ingestor.refresh_sources)
    run(ingestor.handle_new_message, FakeEvent(CHAT, load("single_photo")))
    run(ingestor.handle_new_message, FakeEvent(CHAT, load("album_3_photos")[:1]))  # album item → ignored here
    assert TelegramPost.objects.count() == 1
    run(ingestor.handle_album, FakeEvent(CHAT, load("album_3_photos")))
    assert TelegramPost.objects.get(grouped_id=777).media.count() == 3
    run(ingestor.handle_deleted, FakeEvent(CHAT, deleted_ids=[102]))
    assert TelegramPost.objects.get(telegram_message_id=102).is_deleted
    run(ingestor.handle_new_message, FakeEvent(-100999, load("single_text")))  # unknown chat → ignored
    assert TelegramPost.objects.count() == 2
    assert IngestionOutbox.objects.filter(event_type="telegram.post.deleted").count() == 1


def test_unauthorized_exits_non_zero_sets_offline_and_alerts(
    run: Run, redis_clean: Any, source_row: Any
) -> None:
    client = FakeClient()
    client.authorized = False
    assert run(_ingestor(client, redis_clean).run) == EXIT_UNAUTHORIZED
    source_row.refresh_from_db()
    assert source_row.status == "offline"
    assert AlertEvent.objects.filter(kind="ingestor_unauthorized").exists()
    assert redis_clean.get(LEADER_KEY) is None  # lock released on shutdown


def test_lost_leadership_stops_with_exit_1(run: Run, redis_clean: Any) -> None:
    ingestor = _ingestor(FakeClient(), redis_clean)
    ingestor.lock.acquire()
    redis_clean.set(LEADER_KEY, "someone-else:9", ex=60)
    run(ingestor.renew_leadership)
    assert ingestor.exit_code == EXIT_LOST_LEADERSHIP
    assert ingestor._stop.is_set()


def test_standby_while_another_instance_leads(run: Run, redis_clean: Any) -> None:
    redis_clean.set(LEADER_KEY, "other:1", ex=60)
    ingestor = _ingestor(FakeClient(), redis_clean)

    async def scenario() -> bool:
        asyncio.get_running_loop().call_later(0.05, ingestor.stop)
        with mock.patch("apps.telegram.ingestor.runner.STANDBY_RETRY_SECONDS", 0.01):
            return await ingestor.wait_for_leadership()

    assert run(scenario) is False


def test_full_run_starts_loops_and_stops_gracefully(run: Run, redis_clean: Any, source_row: Any) -> None:
    client = FakeClient(load("single_text"))
    ingestor = _ingestor(client, redis_clean)

    async def scenario() -> int:
        asyncio.get_running_loop().call_later(0.3, ingestor.stop)
        return await ingestor.run()

    assert run(scenario) == 0
    assert redis_clean.get("educore:ingestor:heartbeat") is not None
    assert TelegramPost.objects.filter(telegram_message_id=101).exists()  # startup gap check ingested it
    assert redis_clean.get(LEADER_KEY) is None
