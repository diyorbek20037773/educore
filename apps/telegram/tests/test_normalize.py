"""Telethon message → DTO normalization from recorded fixtures."""

from __future__ import annotations

import json

from apps.telegram.ingestor.normalize import (
    compute_content_hash,
    extract_hashtags,
    jsonable,
    messages_to_dto,
)
from apps.telegram.tests.telethon_fixtures import CHANNEL_ID, load


def test_single_text_message() -> None:
    dto = messages_to_dto(load("single_text"), "akadmvduz")
    assert dto.channel_id == CHANNEL_ID
    assert dto.message_id == 101
    assert dto.url == "https://t.me/akadmvduz/101"
    assert dto.links == ["https://akadmvd.uz/news/123"]
    assert dto.hashtags == ["qabul2026", "kursantlar"]
    assert dto.reactions == {"👍": 40, "custom:99": 3}
    assert dto.views == 1500 and dto.forwards == 12
    assert dto.media == ()
    json.dumps(dto.raw)  # raw payload is JSON-safe


def test_photo_takes_largest_size() -> None:
    dto = messages_to_dto(load("single_photo"), "akadmvduz")
    (media,) = dto.media
    assert (media.kind, media.file_id, media.width, media.height, media.extension) == (
        "photo",
        9001,
        1280,
        853,
        "jpg",
    )


def test_album_is_one_post_with_three_media() -> None:
    items = load("album_3_photos")
    dto = messages_to_dto(list(reversed(items)), "akadmvduz")
    assert dto.message_id == 201
    assert dto.grouped_id == 777
    assert dto.item_ids == (201, 202, 203)
    assert [m.message_id for m in dto.media] == [201, 202, 203]
    assert [m.order for m in dto.media] == [0, 1, 2]
    assert dto.text.startswith("Oʻzbekiston")
    assert len(dto.raw["items"]) == 3


def test_forwarded_and_service_and_sticker_and_video() -> None:
    fwd = messages_to_dto(load("forwarded"), "x")
    assert fwd.is_forwarded and fwd.forward_from == "Kun.uz"
    service = messages_to_dto(load("service_pin"), "x")
    assert service.is_service and service.text == ""
    sticker = messages_to_dto(load("sticker_greeting"), "x")
    assert sticker.media[0].kind == "sticker"
    video = messages_to_dto(load("video_large"), "x")
    assert (video.media[0].kind, video.media[0].duration_seconds, video.media[0].extension) == (
        "video",
        45,
        "mp4",
    )
    assert video.media[0].size_bytes == 500 * 1024 * 1024


def test_edit_dates_are_carried() -> None:
    assert messages_to_dto(load("edit_text"), "x").edited_at is not None
    assert messages_to_dto(load("single_text"), "x").edited_at is None


def test_content_hash_is_whitespace_and_order_insensitive() -> None:
    a = compute_content_hash("Salom  dunyo\n", ["2", "1"])
    b = compute_content_hash("Salom dunyo", ["1", "2"])
    assert a == b
    assert compute_content_hash("Salom dunyo", ["1"]) != a


def test_hashtags_keep_uzbek_letters_and_dedupe() -> None:
    assert extract_hashtags("#Taʼlim va #taʼlim #qabul") == ["taʼlim", "qabul"]


def test_jsonable_handles_bytes_and_dates() -> None:
    from datetime import UTC, datetime

    assert jsonable({"b": b"\x00", "d": datetime(2026, 1, 1, tzinfo=UTC), "l": (1,)}) == {
        "b": "AA==",
        "d": "2026-01-01T00:00:00+00:00",
        "l": [1],
    }
