"""Live ingestion: single, album, edit, delete, forwarded, service, oversized media, outbox uniqueness."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from apps.telegram.ingestor import repository
from apps.telegram.ingestor.media import MediaDownloader
from apps.telegram.ingestor.normalize import messages_to_dto
from apps.telegram.ingestor.pipeline import group_messages, ingest_group
from apps.telegram.ingestor.source_repository import SourceInfo
from apps.telegram.models import IngestionOutbox, MediaStatus, ProcessingStatus, TelegramMedia, TelegramPost
from apps.telegram.tests.telethon_fixtures import FakeClient, load

pytestmark = pytest.mark.django_db
Run = Callable[..., Any]


def _ingest(
    run: Run, source: SourceInfo, name: str, client: FakeClient | None = None, **kw: Any
) -> str | None:
    messages = load(name)
    return run(ingest_group, client or FakeClient(messages), source, messages, MediaDownloader(2), **kw)


def test_single_text_post_creates_post_and_created_event(run: Run, source: SourceInfo) -> None:
    event = _ingest(run, source, "single_text")
    post = TelegramPost.objects.get()
    assert event == "telegram.post.created"
    assert (post.telegram_message_id, post.processing_status, post.has_media) == (
        101,
        ProcessingStatus.QUEUED,
        False,
    )
    assert post.links == ["https://akadmvd.uz/news/123"]
    assert post.search_vector is not None  # DB trigger
    outbox = IngestionOutbox.objects.get()
    assert outbox.payload["post_id"] == post.pk and outbox.payload_hash == post.content_hash
    post.source.refresh_from_db()
    assert post.source.last_message_id == 101


def test_photo_is_downloaded_to_storage(run: Run, source: SourceInfo, media_root: Any) -> None:
    client = FakeClient(load("single_photo"))
    _ingest(run, source, "single_photo", client)
    media = TelegramMedia.objects.get()
    assert media.status == MediaStatus.DOWNLOADED
    assert media.original.name.startswith(f"telegram/{source.username}/2026/09/102/0")
    assert (media_root / media.original.name).exists()
    assert client.downloads == [102]


def test_album_is_one_post_and_late_item_adds_media_only(run: Run, source: SourceInfo) -> None:
    items = load("album_3_photos")
    client = FakeClient(items)
    run(ingest_group, client, source, items[:2], MediaDownloader(2))
    run(ingest_group, client, source, items[2:], MediaDownloader(2))  # late album item / catch-up burst
    post = TelegramPost.objects.get()
    assert post.grouped_id == 777 and post.telegram_message_id == 201
    assert post.media.count() == 3 and post.media_count == 3
    assert post.text.startswith("Oʻzbekiston")
    assert IngestionOutbox.objects.filter(event_type="telegram.post.created").count() == 1
    assert (
        IngestionOutbox.objects.filter(event_type="telegram.post.edited").count() == 1
    )  # a new photo = new content


def test_edit_with_new_text_emits_edited_but_views_only_does_not(run: Run, source: SourceInfo) -> None:
    _ingest(run, source, "single_text")
    assert _ingest(run, source, "edit_views_only") is None
    post = TelegramPost.objects.get()
    assert post.views == 4200 and post.edited_at is not None
    assert _ingest(run, source, "edit_text") == "telegram.post.edited"
    assert "300 dan ortiq" in TelegramPost.objects.get().text
    assert IngestionOutbox.objects.count() == 2


def test_same_update_twice_is_idempotent(run: Run, source: SourceInfo) -> None:
    _ingest(run, source, "single_photo")
    _ingest(run, source, "single_photo")
    assert TelegramPost.objects.count() == 1
    assert TelegramMedia.objects.count() == 1
    assert IngestionOutbox.objects.count() == 1


def test_delete_archives_and_emits_deleted(run: Run, source: SourceInfo) -> None:
    _ingest(run, source, "single_photo")
    deleted = repository.mark_deleted(source.id, [102])
    post = TelegramPost.objects.get()
    assert deleted == [post.pk]
    assert post.is_deleted and post.deleted_at is not None
    assert IngestionOutbox.objects.filter(event_type="telegram.post.deleted").count() == 1
    assert repository.mark_deleted(source.id, [102]) == []  # repeated delete is a no-op


def test_partial_album_delete_is_an_edit(run: Run, source: SourceInfo) -> None:
    items = load("album_3_photos")
    run(ingest_group, FakeClient(items), source, items, MediaDownloader(2))
    assert repository.mark_deleted(source.id, [203]) == []
    post = TelegramPost.objects.get()
    assert not post.is_deleted and post.media_count == 3
    assert post.media.filter(error=repository.DELETED_MEDIA_ERROR).count() == 1
    assert IngestionOutbox.objects.filter(event_type="telegram.post.edited").count() == 1
    assert repository.mark_deleted(source.id, [201, 202]) == [post.pk]


def test_forwarded_and_service_messages_are_stored(run: Run, source: SourceInfo) -> None:
    _ingest(run, source, "forwarded")
    _ingest(run, source, "service_pin")
    fwd = TelegramPost.objects.get(telegram_message_id=301)
    assert fwd.is_forwarded and fwd.forward_from == "Kun.uz"
    assert TelegramPost.objects.filter(telegram_message_id=401).exists()


def test_oversized_video_is_metadata_only_and_post_still_finalized(run: Run, source: SourceInfo) -> None:
    client = FakeClient(load("video_large"))
    event = _ingest(run, source, "video_large", client)
    media = TelegramMedia.objects.get()
    assert (media.status, media.error) == (MediaStatus.FAILED, "too_large")
    assert client.downloads == []
    assert event == "telegram.post.created"


def test_sticker_is_metadata_only(run: Run, source: SourceInfo) -> None:
    client = FakeClient(load("sticker_greeting"))
    _ingest(run, source, "sticker_greeting", client)
    assert TelegramMedia.objects.get().error == repository.METADATA_ONLY_ERROR
    assert client.downloads == []


def test_download_failure_marks_media_failed_but_keeps_post(run: Run, source: SourceInfo) -> None:
    client = FakeClient(load("single_photo"), fail_downloads=True)
    assert _ingest(run, source, "single_photo", client) == "telegram.post.created"
    assert TelegramMedia.objects.get().status == MediaStatus.FAILED


def test_backfill_posts_beyond_ai_limit_are_skipped_without_event(run: Run, source: SourceInfo) -> None:
    _ingest(run, source, "single_text", is_backfill=True, emit_event=False)
    post = TelegramPost.objects.get()
    assert post.is_backfill
    assert (post.processing_status, post.skip_reason) == (
        ProcessingStatus.SKIPPED,
        repository.BACKFILL_SKIP_REASON,
    )
    assert not IngestionOutbox.objects.exists()


def test_outbox_unique_per_post_event_and_hash(run: Run, source: SourceInfo) -> None:
    _ingest(run, source, "single_text")
    post = TelegramPost.objects.get()
    assert not repository._add_event(post, "telegram.post.created", post.content_hash)
    assert IngestionOutbox.objects.count() == 1


def test_group_messages_keeps_albums_together() -> None:
    album = load("album_3_photos")
    single = load("single_text")
    groups = group_messages([*reversed(album), *single])
    assert [len(g) for g in groups] == [3, 1]
    assert messages_to_dto(groups[0], "x").item_ids == (201, 202, 203)
