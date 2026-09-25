"""The shared ingestion step: one message or album → post + media + outbox (live, backfill and gap check)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Sequence
from typing import Any

import structlog
from asgiref.sync import sync_to_async
from telethon import utils
from telethon.tl import types

from apps.telegram.ingestor import repository, source_repository
from apps.telegram.ingestor.media import MediaDownloader, MediaPolicy, live_policy
from apps.telegram.ingestor.normalize import messages_to_dto
from apps.telegram.ingestor.source_repository import SourceInfo

log = structlog.get_logger(__name__)


def marked_channel_id(channel_id: int) -> int:
    """Telethon's marked peer id (`-100…`) for a raw channel id — what `event.chat_id` carries."""
    return utils.get_peer_id(types.PeerChannel(channel_id))


async def entity_for(client: Any, source: SourceInfo) -> Any:
    """Input peer from stored id/hash when resolved (no API call), else resolve by username."""
    if source.channel_id and source.access_hash is not None:
        return types.InputPeerChannel(source.channel_id, source.access_hash)
    return await client.get_input_entity(source.username)


def group_messages(messages: Iterable[Any]) -> list[list[Any]]:
    """Group consecutive messages sharing a `grouped_id` (albums) while preserving order."""
    groups: list[list[Any]] = []
    for message in messages:
        gid = getattr(message, "grouped_id", None)
        if gid is not None and groups and getattr(groups[-1][0], "grouped_id", None) == gid:
            groups[-1].append(message)
        else:
            groups.append([message])
    return groups


async def agroup_messages(messages: AsyncIterator[Any]) -> AsyncIterator[list[Any]]:
    """Async variant of `group_messages` for `iter_messages` streams."""
    buffer: list[Any] = []
    async for message in messages:
        gid = getattr(message, "grouped_id", None)
        if buffer and (gid is None or getattr(buffer[0], "grouped_id", None) != gid):
            yield buffer
            buffer = []
        buffer.append(message)
    if buffer:
        yield buffer


async def ingest_group(
    client: Any,
    source: SourceInfo,
    messages: Sequence[Any],
    downloader: MediaDownloader,
    *,
    is_backfill: bool = False,
    emit_event: bool = True,
    policy: MediaPolicy | None = None,
) -> str | None:
    """Persist one post (single message or album). Returns the outbox event type written, if any."""
    if not messages:
        return None
    dto = messages_to_dto(messages, source.username)
    result = await sync_to_async(repository.upsert_post)(source.id, dto, is_backfill=is_backfill)
    if result.pending_media_ids:
        tasks = await sync_to_async(repository.media_tasks)(result.pending_media_ids)
        await downloader.download(client, {m.id: m for m in messages}, tasks, policy or live_policy())
    event = await sync_to_async(repository.finalize_post)(result.post_id, emit_event=emit_event)
    await sync_to_async(source_repository.touch_source)(source.id)
    log.info(
        "telegram_post_ingested",
        source=source.username,
        post_id=result.post_id,
        message_id=dto.message_id,
        created=result.created,
        media=len(dto.media),
        outbox_event=event,
        backfill=is_backfill,
    )
    return event
