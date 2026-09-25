"""IngestionRequest execution by the ingestor (ADR-009)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from apps.telegram.ingestor.media import MediaDownloader
from apps.telegram.ingestor.requests import run_pending
from apps.telegram.ingestor.source_repository import claim_next_request, requeue_stale_running
from apps.telegram.models import IngestionRequest, RequestStatus, TelegramPost, TelegramSource
from apps.telegram.tests.factories import IngestionRequestFactory, TelegramSourceFactory
from apps.telegram.tests.telethon_fixtures import CHANNEL_ID, FakeClient, load

pytestmark = pytest.mark.django_db
Run = Callable[..., Any]


def _history() -> list[Any]:
    return [*load("album_3_photos"), *load("single_photo"), *load("single_text")]


def test_backfill_request_runs_and_records_result(run: Run, source_row: TelegramSource) -> None:
    req = IngestionRequestFactory(kind="backfill", source=source_row, params={"limit": 50, "ai_limit": 1})
    assert run(run_pending, FakeClient(_history()), MediaDownloader(2)) == 1
    req.refresh_from_db()
    assert req.status == RequestStatus.DONE and req.finished_at is not None
    assert req.result[source_row.username] == {"posts": 3, "events": 1}
    assert TelegramPost.objects.count() == 3


def test_gapcheck_engagement_and_resolve_requests(run: Run, source_row: TelegramSource) -> None:
    IngestionRequestFactory(kind="gapcheck", source=source_row)
    IngestionRequestFactory(kind="refresh_engagement", source=source_row)
    IngestionRequestFactory(kind="resolve_source", source=source_row)
    assert run(run_pending, FakeClient(load("single_text")), MediaDownloader(2)) == 3
    statuses = dict(IngestionRequest.objects.values_list("kind", "status"))
    assert set(statuses.values()) == {RequestStatus.DONE}
    assert IngestionRequest.objects.get(kind="resolve_source").result == {
        source_row.username: {"resolved": True}
    }


def test_unresolved_source_is_resolved_before_backfill(run: Run) -> None:
    source = TelegramSourceFactory(telegram_channel_id=None, access_hash=None)
    IngestionRequestFactory(kind="backfill", source=source, params={"limit": 5, "ai_limit": 5})
    run(run_pending, FakeClient(load("single_text")), MediaDownloader(2))
    source.refresh_from_db()
    assert source.telegram_channel_id == CHANNEL_ID
    assert IngestionRequest.objects.get().status == RequestStatus.DONE


def test_failures_are_recorded_not_raised(run: Run, source_row: TelegramSource) -> None:
    IngestionRequestFactory(kind="backfill", source=source_row)

    class Broken(FakeClient):
        async def iter_messages(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("network down")
            yield  # pragma: no cover

    run(run_pending, Broken(), MediaDownloader(2))
    req = IngestionRequest.objects.get()
    assert req.status == RequestStatus.FAILED and "network down" in req.error


def test_retry_media_request(run: Run, source_row: TelegramSource) -> None:
    run(
        run_pending, FakeClient(load("single_photo"), fail_downloads=True), MediaDownloader(2)
    )  # nothing queued
    IngestionRequestFactory(kind="backfill", source=source_row, params={"limit": 5, "ai_limit": 5})
    run(run_pending, FakeClient(load("single_photo"), fail_downloads=True), MediaDownloader(2))
    media_id = TelegramPost.objects.get().media.get().pk
    IngestionRequestFactory(kind="retry_media", source=None, params={"media_ids": [media_id]})
    run(run_pending, FakeClient(load("single_photo")), MediaDownloader(2))
    assert IngestionRequest.objects.get(kind="retry_media").result == {"downloaded": 1, "requested": 1}


def test_claim_skips_non_pending_and_stale_running_is_requeued() -> None:
    from datetime import timedelta

    from django.utils import timezone

    IngestionRequestFactory(status=RequestStatus.DONE)
    stale = IngestionRequestFactory(
        status=RequestStatus.RUNNING, started_at=timezone.now() - timedelta(hours=2)
    )
    assert claim_next_request() is None
    assert requeue_stale_running() == 1
    claimed = claim_next_request()
    assert claimed is not None and claimed.id == stale.pk
