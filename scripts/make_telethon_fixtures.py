"""Build recorded Telethon message fixtures (`fixtures/telethon/*.json`) from real Telethon types.

Each fixture is the JSON-safe `to_dict()` of `telethon.tl.types` objects, so tests revive genuine
Telethon messages (`apps/telegram/tests/telethon_fixtures.py`) without talking to Telegram.
Re-run after changing a sample.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from telethon.tl import types  # noqa: E402

OUT = ROOT / "fixtures" / "telethon"
CHANNEL_ID = 1234567890
PEER = types.PeerChannel(CHANNEL_ID)
BASE_DATE = datetime(2026, 9, 20, 9, 30, tzinfo=UTC)


def _jsonable(value: Any) -> Any:
    import base64

    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return {"__bytes__": base64.b64encode(value).decode()}
    return value


def photo(photo_id: int, w: int = 1280, h: int = 853, size: int = 180_000) -> types.MessageMediaPhoto:
    return types.MessageMediaPhoto(
        photo=types.Photo(
            id=photo_id,
            access_hash=photo_id * 7,
            file_reference=b"\x01ref",
            date=BASE_DATE,
            sizes=[
                types.PhotoSize(type="m", w=320, h=213, size=12_000),
                types.PhotoSize(type="y", w=w, h=h, size=size),
            ],
            dc_id=2,
        )
    )


def video(doc_id: int, size: int, w: int = 1280, h: int = 720) -> types.MessageMediaDocument:
    return types.MessageMediaDocument(
        document=types.Document(
            id=doc_id,
            access_hash=doc_id * 3,
            file_reference=b"\x02ref",
            date=BASE_DATE,
            mime_type="video/mp4",
            size=size,
            dc_id=2,
            attributes=[
                types.DocumentAttributeVideo(duration=45, w=w, h=h),
                types.DocumentAttributeFilename(file_name="tadbir.mp4"),
            ],
        )
    )


def sticker(doc_id: int) -> types.MessageMediaDocument:
    return types.MessageMediaDocument(
        document=types.Document(
            id=doc_id,
            access_hash=1,
            file_reference=b"\x03",
            date=BASE_DATE,
            mime_type="application/x-tgsticker",
            size=20_000,
            dc_id=2,
            attributes=[types.DocumentAttributeSticker(alt="👋", stickerset=types.InputStickerSetEmpty())],
        )
    )


def message(
    msg_id: int,
    text: str = "",
    *,
    media: Any = None,
    grouped_id: int | None = None,
    edit_date: datetime | None = None,
    views: int = 1500,
    entities: list[Any] | None = None,
    fwd_from: Any = None,
    reactions: Any = None,
) -> types.Message:
    return types.Message(
        id=msg_id,
        peer_id=PEER,
        date=BASE_DATE.replace(minute=30 + msg_id % 20),
        message=text,
        post=True,
        media=media,
        grouped_id=grouped_id,
        edit_date=edit_date,
        views=views,
        forwards=12,
        entities=entities,
        fwd_from=fwd_from,
        reactions=reactions,
    )


TEXT = (
    "Oʻzbekiston Respublikasi IIV Akademiyasida «Ochiq eshiklar kuni» boʻlib oʻtdi. Tadbirda abituriyentlar "
    "va ularning ota-onalari akademiya faoliyati, taʼlim yoʻnalishlari hamda qabul tartibi bilan tanishdi. "
    "Batafsil: https://akadmvd.uz/news/123 #qabul2026 #kursantlar"
)


def samples() -> dict[str, list[types.TypeMessage]]:
    link_offset = len(TEXT.split("Batafsil: ")[0]) + len("Batafsil: ")
    entities = [
        types.MessageEntityUrl(offset=link_offset, length=len("https://akadmvd.uz/news/123")),
        types.MessageEntityHashtag(offset=TEXT.index("#qabul2026"), length=len("#qabul2026")),
    ]
    reactions = types.MessageReactions(
        results=[
            types.ReactionCount(reaction=types.ReactionEmoji(emoticon="👍"), count=40),
            types.ReactionCount(reaction=types.ReactionCustomEmoji(document_id=99), count=3),
        ]
    )
    edited_text = TEXT.replace("boʻlib oʻtdi", "boʻlib oʻtdi va 300 dan ortiq abituriyent qatnashdi")
    return {
        "single_text": [message(101, TEXT, entities=entities, reactions=reactions)],
        "single_photo": [message(102, TEXT, media=photo(9001))],
        "album_3_photos": [
            message(201, TEXT, media=photo(9101), grouped_id=777),
            message(202, "", media=photo(9102, w=1600, h=1067), grouped_id=777),
            message(203, "", media=photo(9103), grouped_id=777),
        ],
        "edit_text": [message(101, edited_text, entities=entities, edit_date=BASE_DATE.replace(hour=11))],
        "edit_views_only": [
            message(101, TEXT, entities=entities, views=4200, edit_date=BASE_DATE.replace(hour=10))
        ],
        "forwarded": [
            message(301, "Qisqa xabar.", fwd_from=types.MessageFwdHeader(date=BASE_DATE, from_name="Kun.uz"))
        ],
        "service_pin": [
            types.MessageService(id=401, peer_id=PEER, date=BASE_DATE, action=types.MessageActionPinMessage())
        ],
        "video_large": [message(501, TEXT, media=video(9501, size=500 * 1024 * 1024))],
        "sticker_greeting": [message(601, "Assalomu alaykum!", media=sticker(9601))],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, msgs in samples().items():
        payload = [_jsonable(m.to_dict()) for m in msgs]
        (OUT / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote fixtures/telethon/{name}.json ({len(msgs)} message(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
