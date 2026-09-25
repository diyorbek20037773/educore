"""The ingestor process: leader lock → client → sources → handlers → background loops (ARCHITECTURE §3.2)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import redis
import structlog
from asgiref.sync import sync_to_async
from telethon import events

from apps.ops.services.alerts import send_alert
from apps.telegram.ingestor import history, repository, source_repository
from apps.telegram.ingestor.bootstrap import resolve_source
from apps.telegram.ingestor.leader import LeaderLock, LockState, write_heartbeat
from apps.telegram.ingestor.media import MediaDownloader
from apps.telegram.ingestor.pipeline import ingest_group, marked_channel_id
from apps.telegram.ingestor.requests import run_pending
from apps.telegram.ingestor.source_repository import SourceInfo
from apps.telegram.models import SourceStatus

log = structlog.get_logger(__name__)

LEADER_RENEW_SECONDS = 20
HEARTBEAT_SECONDS = 30
SOURCE_REFRESH_SECONDS = 60
REQUEST_POLL_SECONDS = 15
GAPCHECK_SECONDS = 10 * 60
ENGAGEMENT_SECONDS = 6 * 3600
STANDBY_RETRY_SECONDS = 10

EXIT_OK = 0
EXIT_LOST_LEADERSHIP = 1
EXIT_UNAUTHORIZED = 2


class Ingestor:
    """Owns the Telegram session. Everything Telegram-related in EDUCORE happens here."""

    def __init__(
        self,
        client: Any,
        redis_client: redis.Redis,
        *,
        lock: LeaderLock | None = None,
        downloader: MediaDownloader | None = None,
    ) -> None:
        self.client = client
        self.redis = redis_client
        self.lock = lock or LeaderLock(redis_client)
        self.downloader = downloader or MediaDownloader()
        self.sources: dict[int, SourceInfo] = {}
        self._registered_chats: tuple[int, ...] = ()
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []
        self.exit_code = EXIT_OK

    # --- handlers (thin: map chat → source, delegate) -------------------------------------------
    async def handle_new_message(self, event: Any) -> None:
        if getattr(event.message, "grouped_id", None) is not None:
            return  # albums arrive through `events.Album`
        await self._ingest(event.chat_id, [event.message])

    async def handle_album(self, event: Any) -> None:
        await self._ingest(event.chat_id, list(event.messages))

    async def handle_edited(self, event: Any) -> None:
        await self._ingest(event.chat_id, [event.message])

    async def handle_deleted(self, event: Any) -> None:
        source = self.sources.get(event.chat_id) if event.chat_id is not None else None
        if source is None:
            return
        deleted = await sync_to_async(repository.mark_deleted)(source.id, list(event.deleted_ids))
        log.info(
            "telegram_messages_deleted", source=source.username, ids=list(event.deleted_ids), posts=deleted
        )

    async def _ingest(self, chat_id: int | None, messages: list[Any]) -> None:
        source = self.sources.get(chat_id) if chat_id is not None else None
        if source is None:
            return
        try:
            await ingest_group(self.client, source, messages, self.downloader)
        except Exception as exc:
            log.exception(
                "telegram_ingest_failed", source=source.username, message_ids=[m.id for m in messages]
            )
            await sync_to_async(source_repository.mark_source_error)(
                source.id, f"ingest: {exc}", SourceStatus.LIVE
            )

    # --- sources ---------------------------------------------------------------------------------
    async def refresh_sources(self) -> None:
        """Reload active sources, resolve new ones, re-register handlers when the chat list changed."""
        resolved: list[SourceInfo] = []
        for source in await sync_to_async(source_repository.active_sources)():
            if not source.channel_id:
                source = await resolve_source(self.client, source) or source
            if source.channel_id:
                resolved.append(source)
        self.sources = {marked_channel_id(s.channel_id): s for s in resolved if s.channel_id}
        chats = tuple(sorted(self.sources))
        if chats != self._registered_chats:
            self._register_handlers(chats)

    def _register_handlers(self, chats: tuple[int, ...]) -> None:
        for callback in (self.handle_new_message, self.handle_album, self.handle_edited, self.handle_deleted):
            self.client.remove_event_handler(callback)
        if chats:
            ids = list(chats)
            self.client.add_event_handler(self.handle_new_message, events.NewMessage(chats=ids))
            self.client.add_event_handler(self.handle_album, events.Album(chats=ids))
            self.client.add_event_handler(self.handle_edited, events.MessageEdited(chats=ids))
            self.client.add_event_handler(self.handle_deleted, events.MessageDeleted(chats=ids))
        self._registered_chats = chats
        log.info("telegram_handlers_registered", chats=len(chats))

    # --- loops -----------------------------------------------------------------------------------
    async def _every(
        self, seconds: float, job: Callable[[], Awaitable[Any]], name: str, *, now: bool = False
    ) -> None:
        if not now:
            await self._sleep(seconds)
        while not self._stop.is_set():
            try:
                await job()
            except Exception:
                log.exception("ingestor_loop_failed", loop=name)
            await self._sleep(seconds)

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except TimeoutError:
            pass

    async def renew_leadership(self) -> None:
        if self.lock.renew() == LockState.HELD_BY_OTHER:
            log.error("ingestor_leadership_lost")
            self.exit_code = EXIT_LOST_LEADERSHIP
            self.stop()

    async def heartbeat(self) -> None:
        write_heartbeat(self.redis)

    async def gapcheck_all(self) -> None:
        for source in list(self.sources.values()):
            try:
                await history.gapcheck(self.client, source, self.downloader)
            except Exception as exc:
                log.exception("telegram_gapcheck_failed", source=source.username)
                await sync_to_async(source_repository.mark_source_error)(source.id, f"gapcheck: {exc}")

    async def engagement_all(self) -> None:
        for source in list(self.sources.values()):
            try:
                await history.refresh_engagement(self.client, source)
            except Exception:
                log.exception("telegram_engagement_failed", source=source.username)

    async def poll_requests(self) -> None:
        await run_pending(self.client, self.downloader)

    # --- lifecycle -------------------------------------------------------------------------------
    async def wait_for_leadership(self) -> bool:
        """Block in standby while another instance leads. Redis outages do not block startup."""
        while not self._stop.is_set():
            state = self.lock.acquire()
            if state in (LockState.OWNED, LockState.UNKNOWN):
                return True
            log.info("ingestor_standby", owner=self.lock.owner)
            await self._sleep(STANDBY_RETRY_SECONDS)
        return False

    async def run(self) -> int:
        if not await self.wait_for_leadership():
            return self.exit_code
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                log.error("ingestor_unauthorized", hint="run `make tg-login` (telegram_login)")
                await sync_to_async(source_repository.set_all_active_status)(SourceStatus.OFFLINE)
                await sync_to_async(send_alert)(
                    "ingestor_unauthorized", "ingestor_unauthorized",
                    "Telegram ingestor is not authorized. Run `make tg-login` on the server.",
                )  # fmt: skip
                return EXIT_UNAUTHORIZED
            await sync_to_async(source_repository.requeue_stale_running)()
            await self.refresh_sources()
            write_heartbeat(self.redis)
            self._tasks = [
                asyncio.create_task(self._every(LEADER_RENEW_SECONDS, self.renew_leadership, "leader")),
                asyncio.create_task(self._every(HEARTBEAT_SECONDS, self.heartbeat, "heartbeat")),
                asyncio.create_task(self._every(SOURCE_REFRESH_SECONDS, self.refresh_sources, "sources")),
                asyncio.create_task(
                    self._every(REQUEST_POLL_SECONDS, self.poll_requests, "requests", now=True)
                ),
                asyncio.create_task(self._every(GAPCHECK_SECONDS, self.gapcheck_all, "gapcheck", now=True)),
                asyncio.create_task(self._every(ENGAGEMENT_SECONDS, self.engagement_all, "engagement")),
            ]
            log.info("ingestor_started", sources=[s.username for s in self.sources.values()])
            disconnected = asyncio.ensure_future(self.client.disconnected)
            stopped = asyncio.ensure_future(self._stop.wait())
            await asyncio.wait({disconnected, stopped}, return_when=asyncio.FIRST_COMPLETED)
            for fut in (disconnected, stopped):
                fut.cancel()
            return self.exit_code
        finally:
            await self.shutdown()

    def stop(self) -> None:
        self._stop.set()

    async def shutdown(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        self.lock.release()
        try:
            await self.client.disconnect()
        except Exception:
            log.warning("ingestor_disconnect_failed")
        log.info("ingestor_stopped", exit_code=self.exit_code)
