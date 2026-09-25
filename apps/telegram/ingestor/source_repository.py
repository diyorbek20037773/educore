"""Synchronous DB helpers for sources and `IngestionRequest` rows (the ingestor's control plane)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.telegram.models import IngestionRequest, RequestStatus, SourceStatus, TelegramSource


@dataclass(frozen=True)
class SourceInfo:
    id: int
    username: str
    channel_id: int | None
    access_hash: int | None
    status: str
    signature_patterns: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RequestInfo:
    id: int
    kind: str
    source_id: int | None
    params: dict[str, Any]


def _info(source: TelegramSource) -> SourceInfo:
    return SourceInfo(
        id=source.pk,
        username=source.username,
        channel_id=source.telegram_channel_id,
        access_hash=source.access_hash,
        status=source.status,
        signature_patterns=list(source.signature_patterns or []),
    )


def active_sources() -> list[SourceInfo]:
    """Active MTProto sources (re-read every minute by the refresh loop — FR-TG-12)."""
    return [
        _info(s)
        for s in TelegramSource.objects.filter(is_active=True, ingest_method="mtproto").order_by("pk")
    ]


def get_source(source_id: int) -> SourceInfo | None:
    source = TelegramSource.objects.filter(pk=source_id).first()
    return _info(source) if source else None


def source_by_channel(channel_id: int) -> SourceInfo | None:
    source = TelegramSource.objects.filter(telegram_channel_id=channel_id, is_active=True).first()
    return _info(source) if source else None


def save_resolved(
    source_id: int,
    *,
    channel_id: int,
    access_hash: int | None,
    title: str,
    about: str,
    subscribers: int | None,
    joined_at: datetime | None,
) -> None:
    """Persist resolved channel identity and mark the source live (FR-TG-2)."""
    TelegramSource.objects.filter(pk=source_id).update(
        telegram_channel_id=channel_id,
        access_hash=access_hash,
        title=title[:255],
        about_text=about,
        subscribers_count=subscribers,
        joined_at=joined_at,
        status=SourceStatus.LIVE,
        error_count=0,
        last_error="",
        last_update_seen_at=timezone.now(),
        updated_at=timezone.now(),
    )


def mark_source_error(source_id: int, error: str, status: str = SourceStatus.DEGRADED) -> None:
    TelegramSource.objects.filter(pk=source_id).update(
        status=status, last_error=error[:2000], error_count=F("error_count") + 1, updated_at=timezone.now()
    )


def touch_source(source_id: int, **fields: Any) -> None:
    """Record liveness (`last_update_seen_at`) plus any extra timestamps; revives degraded/offline sources."""
    TelegramSource.objects.filter(pk=source_id, is_active=True).update(
        last_update_seen_at=timezone.now(), status=SourceStatus.LIVE, updated_at=timezone.now(), **fields
    )


def set_all_active_status(status: str) -> int:
    """Flip every active source (e.g. `offline` when unauthorized or heartbeat is stale)."""
    return TelegramSource.objects.filter(is_active=True).update(status=status, updated_at=timezone.now())


# --- IngestionRequest queue ------------------------------------------------------------------------


@transaction.atomic
def claim_next_request() -> RequestInfo | None:
    """Take the oldest pending request (SKIP LOCKED) and mark it running."""
    req = (
        IngestionRequest.objects.select_for_update(skip_locked=True)
        .filter(status=RequestStatus.PENDING)
        .order_by("created_at")
        .first()
    )
    if req is None:
        return None
    req.status, req.started_at = RequestStatus.RUNNING, timezone.now()
    req.save(update_fields=["status", "started_at", "updated_at"])
    return RequestInfo(id=req.pk, kind=req.kind, source_id=req.source_id, params=dict(req.params or {}))


def finish_request(request_id: int, result: dict[str, Any]) -> None:
    IngestionRequest.objects.filter(pk=request_id).update(
        status=RequestStatus.DONE, finished_at=timezone.now(), result=result, updated_at=timezone.now()
    )


def fail_request(request_id: int, error: str) -> None:
    IngestionRequest.objects.filter(pk=request_id).update(
        status=RequestStatus.FAILED, finished_at=timezone.now(), error=error[:4000], updated_at=timezone.now()
    )


def requeue_stale_running(older_than_minutes: int = 30) -> int:
    """Requests left `running` by a crashed ingestor go back to `pending` on startup."""
    cutoff = timezone.now() - timedelta(minutes=older_than_minutes)
    return IngestionRequest.objects.filter(status=RequestStatus.RUNNING, started_at__lt=cutoff).update(
        status=RequestStatus.PENDING, started_at=None, updated_at=timezone.now()
    )


def enqueue_request(kind: str, source_id: int | None = None, params: dict[str, Any] | None = None) -> int:
    """Insert a request (used by commands, admin actions and beat tasks)."""
    return IngestionRequest.objects.create(kind=kind, source_id=source_id, params=params or {}).pk
