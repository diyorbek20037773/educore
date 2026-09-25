"""Revive recorded Telethon fixtures and provide a fake Telethon client for ingestion tests."""

from __future__ import annotations

import asyncio
import base64
import inspect
import io
import json
from collections.abc import AsyncIterator, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image
from telethon import errors
from telethon.tl import types

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "telethon"
CHANNEL_ID = 1234567890
DATE_KEYS = frozenset({"date", "edit_date", "expires"})


def revive(value: Any, key: str = "") -> Any:
    """JSON (Telethon `to_dict()` shape) → genuine `telethon.tl.types` objects."""
    if isinstance(value, list):
        return [revive(v) for v in value]
    if isinstance(value, dict):
        if "__bytes__" in value:
            return base64.b64decode(value["__bytes__"])
        if "_" in value:
            cls = getattr(types, value["_"])
            params = set(inspect.signature(cls.__init__).parameters) - {"self"}
            return cls(**{k: revive(v, k) for k, v in value.items() if k in params})
        return {k: revive(v, k) for k, v in value.items()}
    if key in DATE_KEYS and isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


def load(name: str) -> list[Any]:
    return revive(json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8")))


def jpeg_bytes(width: int = 64, height: int = 48) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (27, 58, 107)).save(buffer, "JPEG")
    return buffer.getvalue()


class FakeClient:
    """Enough of `TelegramClient` for the ingestor code paths (no network)."""

    def __init__(
        self, history: Iterable[Any] = (), *, flood_once: bool = False, fail_downloads: bool = False
    ) -> None:
        self.history = sorted(history, key=lambda m: m.id, reverse=True)  # newest first, like Telegram
        self.flood_once = flood_once
        self.fail_downloads = fail_downloads
        self.downloads: list[int] = []
        self.handlers: list[tuple[Any, Any]] = []
        self.authorized = True

    async def get_input_entity(self, username: str) -> Any:
        return types.InputPeerChannel(CHANNEL_ID, 1)

    async def get_entity(self, username: str) -> Any:
        return types.Channel(
            id=CHANNEL_ID,
            title=f"@{username}",
            photo=types.ChatPhotoEmpty(),
            date=datetime(2020, 1, 1),
            access_hash=42,
            username=username,
            left=True,
        )

    async def __call__(self, request: Any) -> Any:
        name = type(request).__name__
        if name == "GetFullChannelRequest":
            full = types.ChannelFull(
                id=CHANNEL_ID,
                about="Rasmiy kanal",
                read_inbox_max_id=0,
                read_outbox_max_id=0,
                unread_count=0,
                chat_photo=types.PhotoEmpty(id=0),
                notify_settings=types.PeerNotifySettings(),
                pts=1,
                participants_count=15000,
                exported_invite=None,
                bot_info=[],
            )
            return types.messages.ChatFull(full_chat=full, chats=[], users=[])
        return None

    async def iter_messages(
        self, entity: Any, limit: int | None = None, offset_id: int = 0, **_: Any
    ) -> AsyncIterator[Any]:
        if self.flood_once:
            self.flood_once = False
            raise errors.FloodWaitError(request=None, capture=0)
        count = 0
        for message in self.history:
            if offset_id and message.id >= offset_id:
                continue
            if limit is not None and count >= limit:
                return
            count += 1
            yield message

    async def get_messages(
        self, entity: Any, limit: int | None = None, ids: list[int] | None = None
    ) -> list[Any]:
        if ids is not None:
            by_id = {m.id: m for m in self.history}
            return [by_id.get(i) for i in ids]
        return self.history[: limit or len(self.history)]

    async def download_media(self, message: Any, file: str) -> str:
        if self.fail_downloads:
            raise ConnectionError("download failed")
        self.downloads.append(message.id)
        path = Path(file) / f"{message.id}.jpg"
        path.write_bytes(jpeg_bytes())
        return str(path)

    def add_event_handler(self, callback: Any, event: Any) -> None:
        self.handlers.append((callback, event))

    def remove_event_handler(self, callback: Any) -> None:
        self.handlers = [(c, e) for c, e in self.handlers if c != callback]

    # --- connection lifecycle used by the runner ---------------------------------------------------
    async def connect(self) -> None:
        self._disconnected: asyncio.Future[None] = asyncio.get_running_loop().create_future()

    async def is_user_authorized(self) -> bool:
        return self.authorized

    async def disconnect(self) -> None:
        fut = getattr(self, "_disconnected", None)
        if fut is not None and not fut.done():
            fut.set_result(None)

    @property
    def disconnected(self) -> asyncio.Future[None]:
        return self._disconnected


class FakeEvent:
    """Minimal stand-in for Telethon NewMessage/Album/MessageEdited/MessageDeleted events."""

    def __init__(
        self, chat_id: int, messages: list[Any] | None = None, deleted_ids: list[int] | None = None
    ) -> None:
        self.chat_id = chat_id
        self.messages = messages or []
        self.message = self.messages[0] if self.messages else None
        self.deleted_ids = deleted_ids or []
