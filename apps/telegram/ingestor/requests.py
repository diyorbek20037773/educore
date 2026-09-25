"""Execute `IngestionRequest` rows — the only way other processes get Telegram work done (ADR-009)."""

from __future__ import annotations

from typing import Any

import structlog
from asgiref.sync import sync_to_async

from apps.telegram.ingestor import history, source_repository
from apps.telegram.ingestor.bootstrap import resolve_source
from apps.telegram.ingestor.media import MediaDownloader
from apps.telegram.ingestor.source_repository import RequestInfo, SourceInfo
from apps.telegram.models import RequestKind

log = structlog.get_logger(__name__)


async def _targets(request: RequestInfo) -> list[SourceInfo]:
    if request.source_id is not None:
        source = await sync_to_async(source_repository.get_source)(request.source_id)
        return [source] if source else []
    return await sync_to_async(source_repository.active_sources)()


async def execute(client: Any, downloader: MediaDownloader, request: RequestInfo) -> dict[str, Any]:
    """Run one request and return its JSON result (per source where applicable)."""
    if request.kind == RequestKind.RETRY_MEDIA:
        return await history.retry_media(
            client, downloader, [int(i) for i in request.params.get("media_ids", [])]
        )

    result: dict[str, Any] = {}
    for source in await _targets(request):
        if request.kind == RequestKind.RESOLVE_SOURCE:
            resolved = await resolve_source(client, source)
            result[source.username] = {"resolved": resolved is not None}
            continue
        if not source.channel_id:  # unresolved sources are resolved first
            resolved = await resolve_source(client, source)
            if resolved is None:
                result[source.username] = {"error": "unresolved"}
                continue
            source = resolved
        if request.kind == RequestKind.BACKFILL:
            result[source.username] = await history.backfill(
                client,
                source,
                downloader,
                limit=request.params.get("limit"),
                ai_limit=request.params.get("ai_limit"),
            )
        elif request.kind == RequestKind.GAPCHECK:
            result[source.username] = await history.gapcheck(client, source, downloader)
        elif request.kind == RequestKind.REFRESH_ENGAGEMENT:
            result[source.username] = await history.refresh_engagement(client, source)
        else:
            raise ValueError(f"unknown request kind {request.kind!r}")
    return result


async def run_pending(client: Any, downloader: MediaDownloader, max_requests: int = 5) -> int:
    """Claim and execute up to `max_requests` pending rows; failures are recorded, never raised."""
    done = 0
    for _ in range(max_requests):
        request = await sync_to_async(source_repository.claim_next_request)()
        if request is None:
            break
        try:
            result = await execute(client, downloader, request)
            await sync_to_async(source_repository.finish_request)(request.id, result)
            log.info("ingestion_request_done", request_id=request.id, kind=request.kind)
        except Exception as exc:
            log.exception("ingestion_request_failed", request_id=request.id, kind=request.kind)
            await sync_to_async(source_repository.fail_request)(request.id, f"{type(exc).__name__}: {exc}")
        done += 1
    return done
