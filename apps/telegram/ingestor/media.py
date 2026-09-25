"""Bounded-concurrency media downloader (FR-TG-4, FR-TG-6); derivatives are produced by Celery."""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.files import File

from apps.telegram.ingestor import repository
from apps.telegram.ingestor.repository import MediaTask
from apps.telegram.storage import media_storage, original_path

log = structlog.get_logger(__name__)
MB = 1024 * 1024
POST_MEDIA_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class MediaPolicy:
    """Max bytes per media kind; kinds absent from the map are stored as metadata only."""

    max_bytes: Mapping[str, int]

    def allows(self, task: MediaTask) -> tuple[bool, str]:
        limit = self.max_bytes.get(task.kind)
        if limit is None:
            return False, "metadata_only"
        if task.size_bytes is not None and task.size_bytes > limit:
            return False, "too_large"
        return True, ""


def live_policy() -> MediaPolicy:
    """Live posts and the AI-processed part of a backfill."""
    big = settings.TELEGRAM_MAX_MEDIA_MB * MB
    return MediaPolicy({"photo": big, "video": big, "animation": big, "audio": big, "voice": big,
                        "document": 50 * MB})  # fmt: skip


def backfill_light_policy() -> MediaPolicy:
    """Backfill posts beyond the AI limit: photos only, capped (bounds disk usage)."""
    return MediaPolicy({"photo": settings.TELEGRAM_BACKFILL_MAX_MEDIA_MB * MB})


def _store(key: str, local_path: str) -> tuple[str, int]:
    storage = media_storage()
    if storage.exists(key):
        storage.delete(key)
    with open(local_path, "rb") as fh:
        saved = storage.save(key, File(fh))
    return saved, Path(local_path).stat().st_size


class MediaDownloader:
    """Downloads originals for one post at a time with a global concurrency bound."""

    def __init__(self, concurrency: int | None = None) -> None:
        self.semaphore = asyncio.Semaphore(concurrency or settings.TELEGRAM_MEDIA_CONCURRENCY)

    async def download(
        self,
        client: Any,
        messages: Mapping[int, Any],
        tasks: Sequence[MediaTask],
        policy: MediaPolicy,
        deadline_seconds: float = POST_MEDIA_TIMEOUT_SECONDS,
    ) -> dict[int, str]:
        """Download every task; returns {media_id: "downloaded" | reason}. One failure never raises."""
        results: dict[int, str] = {}

        async def one(task: MediaTask) -> None:
            allowed, reason = policy.allows(task)
            if not allowed:
                await sync_to_async(repository.mark_media_failed)(task.media_id, reason)
                results[task.media_id] = reason
                return
            message = messages.get(task.message_id)
            if message is None:
                await sync_to_async(repository.mark_media_failed)(task.media_id, "message_unavailable")
                results[task.media_id] = "message_unavailable"
                return
            async with self.semaphore:
                try:
                    with tempfile.TemporaryDirectory(prefix="educore-media-") as tmp:
                        local = await client.download_media(message, file=tmp)
                        if not local:
                            raise RuntimeError("empty download")
                        key = original_path(task.username, task.published_at, task.message_id, task.order,
                                            task.extension)  # fmt: skip
                        saved, size = await sync_to_async(_store)(key, str(local))
                    await sync_to_async(repository.mark_media_downloaded)(task.media_id, saved, size)
                    results[task.media_id] = "downloaded"
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log.warning("media_download_failed", media_id=task.media_id, error=str(exc))
                    await sync_to_async(repository.mark_media_failed)(task.media_id, f"download: {exc}")
                    results[task.media_id] = "failed"

        jobs = [asyncio.create_task(one(t)) for t in tasks]
        if not jobs:
            return results
        _done, pending = await asyncio.wait(jobs, timeout=deadline_seconds)
        for job in pending:
            job.cancel()
        for task in tasks:
            if task.media_id not in results:
                await sync_to_async(repository.mark_media_failed)(task.media_id, "timeout")
                results[task.media_id] = "timeout"
        return results
