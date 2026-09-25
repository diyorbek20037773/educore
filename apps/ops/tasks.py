"""Ops periodic tasks (CLAUDE.md §11): ingestor heartbeat now; failure-rate/review digests in Phase 7."""

from __future__ import annotations

import redis
import structlog
from celery import shared_task

from apps.core.health import ingestor_heartbeat_age_seconds
from apps.core.redis import get_redis
from apps.ops.services.alerts import send_alert
from apps.telegram.models import SourceStatus, TelegramSource

log = structlog.get_logger(__name__)

STALE_AFTER_SECONDS = 180
STALE_FLAG_KEY = "educore:ingestor:stale"


def _flag(value: bool | None = None) -> bool:
    """Read (value=None) or set/clear the "ingestor is stale" flag; Redis errors read as "not stale"."""
    client = get_redis()
    try:
        if value is None:
            return bool(client.exists(STALE_FLAG_KEY))
        if value:
            client.set(STALE_FLAG_KEY, "1")
        else:
            client.delete(STALE_FLAG_KEY)
    except redis.RedisError:
        return False
    return bool(value)


@shared_task(name="ops.check_heartbeat", ignore_result=True)
def check_heartbeat() -> str:
    """Alert when the heartbeat is older than 3 min and flip sources offline; alert again on recovery."""
    age = ingestor_heartbeat_age_seconds()
    stale = age is None or age > STALE_AFTER_SECONDS
    was_stale = _flag()
    if stale:
        TelegramSource.objects.filter(is_active=True).exclude(status=SourceStatus.OFFLINE).update(
            status=SourceStatus.OFFLINE
        )
        send_alert(
            "ingestor_heartbeat_stale",
            "ingestor_heartbeat_stale",
            f"Ingestor heartbeat is stale ({'missing' if age is None else f'{int(age)} s old'}).",
        )
        _flag(True)
        return "stale"
    if was_stale:
        TelegramSource.objects.filter(is_active=True, status=SourceStatus.OFFLINE).update(
            status=SourceStatus.LIVE
        )
        send_alert(
            "ingestor_recovered",
            "ingestor_recovered",
            f"Ingestor recovered (heartbeat {int(age)} s).",
            force=True,
        )
        _flag(False)
        return "recovered"
    return "ok"
