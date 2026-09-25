"""Telethon `Message` → DTO (text, entities, links, hashtags, media descriptors, content hash).

This is the only module (besides the client/handlers) that knows Telethon types.
"""

from __future__ import annotations

import base64
import hashlib
import re
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from typing import Any

from telethon import helpers
from telethon.tl import types

from apps.telegram.ingestor.dto import TelegramMediaDTO, TelegramMessageDTO

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_HASHTAG_RE = re.compile(r"#([\wʻʼ]+)", re.UNICODE)
_WS_RE = re.compile(r"\s+")

MIME_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "application/pdf": "pdf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/x-tgsticker": "tgs",
}


def jsonable(value: Any) -> Any:
    """Make a Telethon `to_dict()` payload JSON-serializable (datetimes → ISO, bytes → base64)."""
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return value


def normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def compute_content_hash(text: str, media_keys: Iterable[str]) -> str:
    """sha256 of normalized text + sorted media unique ids (ARCHITECTURE §3.3)."""
    payload = normalize_text(text) + "|" + ",".join(sorted(media_keys))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _entity_text(text: str, entity: Any) -> str:
    """Slice using Telegram's UTF-16 offsets."""
    surrogated = helpers.add_surrogate(text)
    return helpers.del_surrogate(surrogated[entity.offset : entity.offset + entity.length])


def extract_links(text: str, entities: Sequence[Any] | None) -> list[str]:
    links: list[str] = []
    for entity in entities or ():
        if isinstance(entity, types.MessageEntityTextUrl):
            links.append(entity.url)
        elif isinstance(entity, types.MessageEntityUrl):
            links.append(_entity_text(text, entity))
    links.extend(_URL_RE.findall(text or ""))
    seen: set[str] = set()
    return [u for u in links if not (u in seen or seen.add(u))]


def extract_hashtags(text: str) -> list[str]:
    seen: set[str] = set()
    tags = [t.lower() for t in _HASHTAG_RE.findall(text or "")]
    return [t for t in tags if not (t in seen or seen.add(t))]


def reactions_of(message: Any) -> dict[str, int]:
    reactions = getattr(message, "reactions", None)
    result: dict[str, int] = {}
    for item in getattr(reactions, "results", None) or ():
        reaction = item.reaction
        if isinstance(reaction, types.ReactionEmoji):
            key = reaction.emoticon
        elif isinstance(reaction, types.ReactionCustomEmoji):
            key = f"custom:{reaction.document_id}"
        else:
            key = "other"
        result[key] = result.get(key, 0) + int(item.count)
    return result


def _forward_source(message: Any) -> tuple[bool, str]:
    fwd = getattr(message, "fwd_from", None)
    if fwd is None:
        return False, ""
    if getattr(fwd, "from_name", None):
        return True, str(fwd.from_name)
    peer = getattr(fwd, "from_id", None)
    if isinstance(peer, types.PeerChannel):
        return True, f"channel:{peer.channel_id}"
    if isinstance(peer, types.PeerUser):
        return True, f"user:{peer.user_id}"
    return True, "unknown"


def _largest_photo_size(photo: types.Photo) -> tuple[int | None, int | None, int | None]:
    best: tuple[int | None, int | None, int | None] = (None, None, None)
    for size in photo.sizes or ():
        if isinstance(size, types.PhotoSize):
            candidate = (size.w, size.h, size.size)
        elif isinstance(size, types.PhotoSizeProgressive):
            candidate = (size.w, size.h, max(size.sizes) if size.sizes else None)
        else:
            continue
        if best[0] is None or (candidate[0] or 0) * (candidate[1] or 0) > (best[0] or 0) * (best[1] or 0):
            best = candidate
    return best


def media_from_message(message: Any, order: int) -> TelegramMediaDTO | None:
    """Describe the media of one message, or None when it carries none."""
    media = getattr(message, "media", None)
    caption = (message.message or "") if order else ""  # album items after the first keep their own text
    if isinstance(media, types.MessageMediaPhoto) and isinstance(media.photo, types.Photo):
        w, h, size = _largest_photo_size(media.photo)
        return TelegramMediaDTO(message.id, order, "photo", media.photo.id, "image/jpeg", size, w, h,
                                caption=caption, extension="jpg")  # fmt: skip
    if isinstance(media, types.MessageMediaDocument) and isinstance(media.document, types.Document):
        doc = media.document
        kind, width, height, duration, name = "document", None, None, None, ""
        for attr in doc.attributes or ():
            if isinstance(attr, types.DocumentAttributeVideo):
                kind, width, height, duration = "video", attr.w, attr.h, int(attr.duration or 0)
            elif isinstance(attr, types.DocumentAttributeAudio):
                kind, duration = ("voice" if attr.voice else "audio"), int(attr.duration or 0)
            elif isinstance(attr, types.DocumentAttributeAnimated):
                kind = "animation"
            elif isinstance(attr, types.DocumentAttributeSticker):
                kind = "sticker"
            elif isinstance(attr, types.DocumentAttributeFilename):
                name = attr.file_name
            elif isinstance(attr, types.DocumentAttributeImageSize) and kind == "document":
                width, height = attr.w, attr.h
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else MIME_EXTENSIONS.get(doc.mime_type, "bin")
        return TelegramMediaDTO(message.id, order, kind, doc.id, doc.mime_type or "", doc.size, width, height,
                                duration, name, caption, ext)  # fmt: skip
    if isinstance(media, types.MessageMediaWebPage):
        return TelegramMediaDTO(message.id, order, "webpage", None, caption=caption)
    if media is not None and not isinstance(media, types.MessageMediaEmpty):
        return TelegramMediaDTO(message.id, order, "other", None, caption=caption)
    return None


def messages_to_dto(messages: Sequence[Any], username: str) -> TelegramMessageDTO:
    """One post from a single message or an album (items sorted by id; caption = the item that has text)."""
    items = sorted(messages, key=lambda m: m.id)
    primary = items[0]
    captioned = next((m for m in items if (m.message or "").strip()), primary)
    text = captioned.message or ""
    entities = list(getattr(captioned, "entities", None) or ())
    media: list[TelegramMediaDTO] = []
    for m in items:
        dto = media_from_message(m, len(media))
        if dto is not None:
            media.append(dto)
    is_forwarded, forward_from = _forward_source(primary)
    reply = getattr(primary, "reply_to", None)
    edit_dates = [m.edit_date for m in items if getattr(m, "edit_date", None)]
    peer = getattr(primary, "peer_id", None)
    raw = {"items": [jsonable(m.to_dict()) for m in items]} if len(items) > 1 else jsonable(primary.to_dict())
    return TelegramMessageDTO(
        channel_id=int(getattr(peer, "channel_id", 0) or 0),
        message_id=primary.id,
        grouped_id=getattr(primary, "grouped_id", None),
        text=text,
        published_at=primary.date,
        edited_at=max(edit_dates) if edit_dates else None,
        url=f"https://t.me/{username}/{primary.id}",
        entities=[jsonable(e.to_dict()) for e in entities],
        links=extract_links(text, entities),
        hashtags=extract_hashtags(text),
        views=getattr(primary, "views", None),
        forwards=getattr(primary, "forwards", None),
        reactions=reactions_of(primary),
        reply_to_id=getattr(reply, "reply_to_msg_id", None),
        is_forwarded=is_forwarded,
        forward_from=forward_from,
        is_service=isinstance(primary, types.MessageService),
        item_ids=tuple(m.id for m in items),
        media=tuple(media),
        raw=raw,
    )
