"""History operations executed by the ingestor: backfill, gap check, engagement refresh, media retry."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone
from telethon import errors

from apps.telegram.ingestor import repository, source_repository
from apps.telegram.ingestor.media import MediaDownloader, backfill_light_policy, live_policy
from apps.telegram.ingestor.normalize import reactions_of
from apps.telegram.ingestor.pipeline import agroup_messages, entity_for, group_messages, ingest_group
from apps.telegram.ingestor.source_repository import SourceInfo
from apps.telegram.models import TelegramSource

log = structlog.get_logger(__name__)
BACKFILL_WAIT_SECONDS = 1.5
FLOOD_WAIT_CAP_SECONDS = 3600
GAPCHECK_WINDOW = 100


async def backfill(
    client: Any,
    source: SourceInfo,
    downloader: MediaDownloader,
    *,
    limit: int | None = None,
    ai_limit: int | None = None,
    wait_time: float = BACKFILL_WAIT_SECONDS,
) -> dict[str, int]:
    """Import the newest `limit` messages (albums grouped); outbox events only for the newest `ai_limit`."""
    limit = limit or settings.TELEGRAM_BACKFILL_LIMIT
    ai_limit = settings.BACKFILL_AI_LIMIT_PER_SOURCE if ai_limit is None else ai_limit
    entity = await entity_for(client, source)
    posts = events = 0
    offset_id = 0
    remaining = limit
    while remaining > 0:
        try:
            stream = client.iter_messages(entity, limit=remaining, offset_id=offset_id, wait_time=wait_time)
            async for group in agroup_messages(stream):
                emit = posts < ai_limit
                event = await ingest_group(
                    client, source, group, downloader, is_backfill=True, emit_event=emit,
                    policy=live_policy() if emit else backfill_light_policy(),
                )  # fmt: skip
                posts += 1
                events += int(event is not None)
                remaining -= len(group)
                offset_id = min(m.id for m in group)
            break
        except errors.FloodWaitError as exc:
            wait = min(int(exc.seconds), FLOOD_WAIT_CAP_SECONDS)
            log.warning("telegram_flood_wait", source=source.username, seconds=wait, op="backfill")
            await asyncio.sleep(wait)
    await sync_to_async(_mark_backfill_done)(source.id)
    log.info("telegram_backfill_done", source=source.username, posts=posts, events=events)
    return {"posts": posts, "events": events}


def _mark_backfill_done(source_id: int) -> None:
    TelegramSource.objects.filter(pk=source_id).update(backfill_done_at=timezone.now())


async def gapcheck(client: Any, source: SourceInfo, downloader: MediaDownloader) -> dict[str, int]:
    """Latest 100 messages vs DB: ingest missing, re-ingest edited, two-miss deletions (FR-TG-7)."""
    entity = await entity_for(client, source)
    messages = await client.get_messages(entity, limit=GAPCHECK_WINDOW)
    groups = group_messages(messages)
    ids = [m.id for m in messages]
    known = await sync_to_async(repository.known_message_state)(source.id, ids)
    ingested = edited = 0
    for group in groups:
        group_ids = [m.id for m in group]
        if not any(i in known for i in group_ids):
            await ingest_group(client, source, group, downloader)
            ingested += 1
            continue
        stored_edit = max((known[i] for i in group_ids if known.get(i)), default=None)
        latest_edit = max((m.edit_date for m in group if getattr(m, "edit_date", None)), default=None)
        if latest_edit and (stored_edit is None or latest_edit > stored_edit):
            await ingest_group(client, source, group, downloader)
            edited += 1
    deleted = await sync_to_async(repository.record_gapcheck_window)(source.id, set(ids))
    await sync_to_async(source_repository.touch_source)(source.id, last_gapcheck_at=timezone.now())
    result = {"checked": len(ids), "ingested": ingested, "edited": edited, "deleted": len(deleted)}
    log.info("telegram_gapcheck_done", source=source.username, **result)
    return result


async def refresh_engagement(client: Any, source: SourceInfo, days: int = 7) -> dict[str, int]:
    """Views/forwards/reactions for the last `days` days of posts (FR-TG-8)."""
    entity = await entity_for(client, source)
    ids = await sync_to_async(repository.recent_message_ids)(source.id, days)
    touched = 0
    for start in range(0, len(ids), 100):
        chunk = ids[start : start + 100]
        messages = await client.get_messages(entity, ids=chunk)
        stats = [
            (m.id, getattr(m, "views", None), getattr(m, "forwards", None), reactions_of(m))
            for m in messages
            if m is not None
        ]
        touched += await sync_to_async(repository.update_engagement)(source.id, stats)
    return {"posts": touched}


async def retry_media(client: Any, downloader: MediaDownloader, media_ids: list[int]) -> dict[str, int]:
    """Re-download failed media (FR-TG-4 failure mode); unavailable messages stay failed."""
    targets = await sync_to_async(repository.media_retry_targets)(media_ids)
    downloaded = 0
    for source_id, items in targets.items():
        source = await sync_to_async(source_repository.get_source)(source_id)
        if source is None:
            continue
        entity = await entity_for(client, source)
        messages = await client.get_messages(entity, ids=[message_id for _, message_id in items])
        by_id = {m.id: m for m in messages if m is not None}
        await sync_to_async(repository.reset_media_for_retry)([media_id for media_id, _ in items])
        tasks = await sync_to_async(repository.media_tasks)([media_id for media_id, _ in items])
        results = await downloader.download(client, by_id, tasks, live_policy())
        downloaded += sum(1 for r in results.values() if r == "downloaded")
    return {"downloaded": downloaded, "requested": len(media_ids)}
