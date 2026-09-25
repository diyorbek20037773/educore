"""Pure data carried from Telethon messages into the repository — no Telethon types past this point."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class TelegramMediaDTO:
    """One downloadable (or metadata-only) media item of a message/album."""

    message_id: int
    order: int
    kind: str
    file_id: int | None
    mime_type: str = ""
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: int | None = None
    file_name: str = ""
    caption: str = ""
    extension: str = ""


@dataclass(frozen=True)
class TelegramMessageDTO:
    """A channel post (single message or a whole album merged by `grouped_id`)."""

    channel_id: int
    message_id: int
    grouped_id: int | None
    text: str
    published_at: datetime
    edited_at: datetime | None
    url: str
    entities: list[dict[str, Any]] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    views: int | None = None
    forwards: int | None = None
    reactions: dict[str, int] = field(default_factory=dict)
    reply_to_id: int | None = None
    is_forwarded: bool = False
    forward_from: str = ""
    is_service: bool = False
    item_ids: tuple[int, ...] = ()
    media: tuple[TelegramMediaDTO, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def all_message_ids(self) -> tuple[int, ...]:
        """Every Telegram message id that belongs to this post (album items included)."""
        return self.item_ids or (self.message_id,)
