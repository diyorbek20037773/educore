"""History backfill (FR-TG-6): enqueue an IngestionRequest, or `--standalone` when no ingestor runs."""

from __future__ import annotations

import asyncio
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.redis import get_redis
from apps.telegram.ingestor.leader import LeaderLock, LockState
from apps.telegram.ingestor.source_repository import enqueue_request, get_source
from apps.telegram.models import RequestKind, TelegramSource


class Command(BaseCommand):
    help = "Import the newest N messages per source (albums grouped, idempotent)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--source", help="username without @ (default: all active sources)")
        parser.add_argument("--limit", type=int, default=settings.TELEGRAM_BACKFILL_LIMIT)
        parser.add_argument(
            "--ai-limit",
            type=int,
            default=None,
            help="default: every post in verbatim mode, else BACKFILL_AI_LIMIT_PER_SOURCE",
        )
        parser.add_argument(
            "--standalone",
            action="store_true",
            help="Run in this process (requires the ingestor to be stopped — the session cannot be shared).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        source_id = None
        if options.get("source"):
            source = TelegramSource.objects.filter(username=options["source"].lstrip("@").lower()).first()
            if source is None:
                raise CommandError(f"Unknown source {options['source']!r}")
            source_id = source.pk
        params = {"limit": options["limit"]}
        if options["ai_limit"] is not None:
            params["ai_limit"] = options["ai_limit"]
        if not options["standalone"]:
            request_id = enqueue_request(RequestKind.BACKFILL, source_id, params)
            self.stdout.write(f"Queued backfill request #{request_id} ({params}); the ingestor executes it.")
            return
        self._standalone(source_id, params)

    def _standalone(self, source_id: int | None, params: dict[str, int]) -> None:
        lock = LeaderLock(get_redis())
        state = lock.acquire()
        if state == LockState.HELD_BY_OTHER:
            raise CommandError("An ingestor is running (leader lock held). Use the queued mode instead.")
        try:
            result = asyncio.run(self._run(source_id, params))
        finally:
            lock.release()
        self.stdout.write(self.style.SUCCESS(f"Backfill done: {result}"))

    async def _run(self, source_id: int | None, params: dict[str, int]) -> dict[str, Any]:
        from asgiref.sync import sync_to_async

        from apps.telegram.ingestor.client import build_client
        from apps.telegram.ingestor.media import MediaDownloader
        from apps.telegram.ingestor.requests import execute
        from apps.telegram.ingestor.source_repository import RequestInfo

        client = build_client()
        await client.connect()
        if not await client.is_user_authorized():
            raise CommandError("Telegram session is not authorized — run telegram_login first.")
        if source_id is not None and await sync_to_async(get_source)(source_id) is None:
            raise CommandError("Source vanished.")
        try:
            request = RequestInfo(id=0, kind=RequestKind.BACKFILL, source_id=source_id, params=dict(params))
            return await execute(client, MediaDownloader(), request)
        finally:
            await client.disconnect()
