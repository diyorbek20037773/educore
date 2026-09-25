"""Celery tasks: outbox relay (locking + concurrency), requests, cleanup, derivatives, heartbeat alerts."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest import mock

import pytest
from django.db import connection
from django.utils import timezone
from PIL import Image

from apps.ops.models import AlertEvent
from apps.ops.tasks import check_heartbeat
from apps.telegram import tasks
from apps.telegram.derivatives import process_media
from apps.telegram.ingestor.leader import write_heartbeat
from apps.telegram.models import IngestionOutbox, IngestionRequest, MediaStatus, TelegramSource
from apps.telegram.storage import media_storage
from apps.telegram.tests.factories import IngestionOutboxFactory, TelegramMediaFactory, TelegramSourceFactory
from apps.telegram.tests.telethon_fixtures import jpeg_bytes


@pytest.fixture
def dispatched() -> Any:
    sent: list[str] = []
    lock = threading.Lock()

    def fake_send(name: str, args: list[Any], queue: str) -> None:
        assert name == "ai.process_post" and queue == "ai"
        with lock:
            sent.append(args[2])

    with (
        mock.patch("apps.telegram.tasks._process_post_registered", return_value=True),
        mock.patch("config.celery.app.send_task", side_effect=fake_send),
    ):
        yield sent


@pytest.mark.django_db
def test_relay_dispatches_and_locks(dispatched: list[str]) -> None:
    rows = IngestionOutboxFactory.create_batch(3)
    assert tasks.relay_outbox() == 3
    assert sorted(dispatched) == sorted(str(r.pk) for r in rows)
    assert tasks.relay_outbox() == 0  # locked for 15 minutes
    locked = IngestionOutbox.objects.first()
    assert locked is not None and locked.locked_until > timezone.now() + timedelta(minutes=14)
    assert locked.attempts == 0  # attempts count terminal failures only


@pytest.mark.django_db
def test_relay_skips_processed_dead_and_future_locked(dispatched: list[str]) -> None:
    IngestionOutboxFactory(processed_at=timezone.now())
    IngestionOutboxFactory(is_dead=True)
    IngestionOutboxFactory(locked_until=timezone.now() + timedelta(days=1))
    expired = IngestionOutboxFactory(locked_until=timezone.now() - timedelta(minutes=1))
    assert tasks.relay_outbox() == 1
    assert dispatched == [str(expired.pk)]


@pytest.mark.django_db
def test_relay_waits_until_process_post_exists() -> None:
    IngestionOutboxFactory()
    with mock.patch("apps.telegram.tasks._process_post_registered", return_value=False):
        assert tasks.relay_outbox() == 0
    assert IngestionOutbox.objects.get().locked_until is None


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_relays_dispatch_each_event_once(dispatched: list[str]) -> None:
    rows = IngestionOutboxFactory.create_batch(40)
    barrier = threading.Barrier(2)

    def relay() -> None:
        barrier.wait()
        try:
            tasks.relay_outbox(batch=25)
        finally:
            connection.close()

    threads = [threading.Thread(target=relay) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(dispatched) == len(set(dispatched))
    tasks.relay_outbox(batch=50)
    assert sorted(dispatched) == sorted(str(r.pk) for r in rows)


@pytest.mark.django_db
def test_renew_outbox_lock() -> None:
    row = IngestionOutboxFactory(locked_until=timezone.now())
    tasks.renew_outbox_lock(str(row.pk), minutes=15)
    row.refresh_from_db()
    assert row.locked_until > timezone.now() + timedelta(minutes=14)


@pytest.mark.django_db
def test_request_gapcheck_alerts_and_enqueues_only_for_stale_sources() -> None:
    fresh = TelegramSourceFactory(last_gapcheck_at=timezone.now())
    stale = TelegramSourceFactory(last_gapcheck_at=timezone.now() - timedelta(hours=1))
    assert tasks.request_gapcheck() == 1
    assert tasks.request_gapcheck() == 0  # already pending
    assert list(IngestionRequest.objects.values_list("source_id", flat=True)) == [stale.pk]
    assert AlertEvent.objects.filter(dedupe_key=f"gapcheck_stale:{stale.username}").count() == 1
    assert not AlertEvent.objects.filter(dedupe_key=f"gapcheck_stale:{fresh.username}").exists()


@pytest.mark.django_db
def test_media_retry_and_engagement_requests() -> None:
    TelegramMediaFactory(status=MediaStatus.FAILED, error="download: boom")
    TelegramMediaFactory(status=MediaStatus.FAILED, error="too_large")
    assert tasks.request_media_retry() == 1
    req = IngestionRequest.objects.get(kind="retry_media")
    assert len(req.params["media_ids"]) == 1
    assert tasks.request_engagement_refresh() is True
    assert tasks.request_engagement_refresh() is False


@pytest.mark.django_db
def test_cleanup_outbox_deletes_old_processed_rows() -> None:
    old = IngestionOutboxFactory(processed_at=timezone.now() - timedelta(days=31))
    recent = IngestionOutboxFactory(processed_at=timezone.now() - timedelta(days=1))
    pending = IngestionOutboxFactory()
    assert tasks.cleanup_outbox() == 1
    assert set(IngestionOutbox.objects.values_list("pk", flat=True)) == {recent.pk, pending.pk}
    assert not IngestionOutbox.objects.filter(pk=old.pk).exists()


@pytest.mark.django_db
def test_photo_derivatives_are_webp_and_never_upscaled() -> None:
    from django.core.files.base import ContentFile

    key = media_storage().save("telegram/x/2026/09/1/0.jpg", ContentFile(jpeg_bytes(1000, 600)))
    media = TelegramMediaFactory(original=key, status=MediaStatus.DOWNLOADED)
    assert process_media(media.pk) == MediaStatus.READY
    media.refresh_from_db()
    assert set(media.derivatives) == {"1600", "800", "400"}
    with media_storage().open(media.derivatives["1600"]) as fh, Image.open(fh) as img:
        assert img.format == "WEBP" and img.width == 1000
    with media_storage().open(media.derivatives["400"]) as fh, Image.open(fh) as img:
        assert (img.width, img.height) == (400, 240)
    assert process_media(media.pk) == MediaStatus.READY  # idempotent


@pytest.mark.django_db
def test_media_url_tag_fallbacks() -> None:
    from apps.telegram.templatetags.media_tags import media_srcset, media_url

    media = TelegramMediaFactory(
        original="telegram/a/0.jpg", derivatives={"800": "d/800.webp", "400": "d/400.webp"}
    )
    assert media_url(media, "800").endswith("d/800.webp")
    assert media_url(media, "1600").endswith("d/800.webp")
    assert media_srcset(media).endswith("800w")
    assert media_url(TelegramMediaFactory(derivatives={}, original="o.jpg"), "800").endswith("o.jpg")
    assert media_url(None) == ""


@pytest.mark.django_db
def test_heartbeat_stale_then_recovered(redis_clean: Any) -> None:
    source = TelegramSourceFactory(status="live")
    assert check_heartbeat() == "stale"  # no heartbeat at all
    source.refresh_from_db()
    assert source.status == "offline"
    assert check_heartbeat() == "stale"
    assert AlertEvent.objects.filter(kind="ingestor_heartbeat_stale").count() == 1  # throttled
    write_heartbeat(redis_clean, datetime.now(UTC))
    assert check_heartbeat() == "recovered"
    assert TelegramSource.objects.get(pk=source.pk).status == "live"
    assert AlertEvent.objects.filter(kind="ingestor_recovered").count() == 1
    assert check_heartbeat() == "ok"
