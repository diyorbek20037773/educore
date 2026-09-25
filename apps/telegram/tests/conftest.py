"""Shared fixtures for Telegram ingestion tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from asgiref.sync import async_to_sync

from apps.core.redis import get_redis
from apps.telegram.ingestor.leader import HEARTBEAT_KEY, LEADER_KEY
from apps.telegram.ingestor.source_repository import SourceInfo
from apps.telegram.models import TelegramSource
from apps.telegram.tests.factories import TelegramSourceFactory
from apps.telegram.tests.telethon_fixtures import CHANNEL_ID

REDIS_KEYS = (LEADER_KEY, HEARTBEAT_KEY, "educore:ingestor:stale")


@pytest.fixture(autouse=True)
def media_root(tmp_path: Path, settings: Any) -> Path:
    settings.MEDIA_ROOT = tmp_path / "media"
    from django.core.files.storage import storages

    storages._storages.pop("default", None)  # rebuild the storage with the new MEDIA_ROOT
    yield settings.MEDIA_ROOT
    storages._storages.pop("default", None)


@pytest.fixture
def redis_clean() -> Iterator[Any]:
    client = get_redis()
    client.delete(*REDIS_KEYS)
    yield client
    client.delete(*REDIS_KEYS)


@pytest.fixture
def source_row(db: Any) -> TelegramSource:
    return TelegramSourceFactory(telegram_channel_id=CHANNEL_ID, access_hash=1)


@pytest.fixture
def source(source_row: TelegramSource) -> SourceInfo:
    return SourceInfo(
        id=source_row.pk,
        username=source_row.username,
        channel_id=source_row.telegram_channel_id,
        access_hash=source_row.access_hash,
        status=source_row.status,
    )


@pytest.fixture
def run() -> Callable[..., Any]:
    """Run a coroutine function from the test thread so `sync_to_async` shares the test DB connection."""

    def _run(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return async_to_sync(fn)(*args, **kwargs)

    return _run
