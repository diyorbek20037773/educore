"""Resolve sources: username → channel id/hash, title, about, subscribers; join when needed (FR-TG-2)."""

from __future__ import annotations

from typing import Any

import structlog
from asgiref.sync import sync_to_async
from django.utils import timezone
from telethon import errors
from telethon.tl import functions, types

from apps.telegram.ingestor import source_repository
from apps.telegram.ingestor.source_repository import SourceInfo

log = structlog.get_logger(__name__)


async def resolve_source(client: Any, source: SourceInfo) -> SourceInfo | None:
    """Resolve and persist one source. Failures mark it `degraded` and return None (others continue)."""
    try:
        entity = await client.get_entity(source.username)
        if not isinstance(entity, types.Channel):
            raise ValueError(f"@{source.username} is not a channel")
        full = await client(functions.channels.GetFullChannelRequest(entity))
        joined_at = None
        if getattr(entity, "left", False):
            await client(functions.channels.JoinChannelRequest(entity))
            joined_at = timezone.now()
        await sync_to_async(source_repository.save_resolved)(
            source.id,
            channel_id=entity.id,
            access_hash=entity.access_hash,
            title=entity.title or source.username,
            about=getattr(full.full_chat, "about", "") or "",
            subscribers=getattr(full.full_chat, "participants_count", None),
            joined_at=joined_at,
        )
        log.info("telegram_source_resolved", source=source.username, channel_id=entity.id)
        return await sync_to_async(source_repository.get_source)(source.id)
    except errors.FloodWaitError as exc:
        error = f"FloodWait {exc.seconds}s while resolving"
    except (errors.UsernameNotOccupiedError, errors.UsernameInvalidError, errors.ChannelPrivateError) as exc:
        error = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    log.warning("telegram_source_resolve_failed", source=source.username, error=error)
    await sync_to_async(source_repository.mark_source_error)(source.id, error)
    return None
