"""Liveness/readiness checks used by `/healthz`, `/readyz` and container health checks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor

from apps.core.redis import get_redis

HEARTBEAT_KEY = "educore:ingestor:heartbeat"


def check_database() -> bool:
    """True when the default database answers ``SELECT 1``."""
    try:
        with connections[DEFAULT_DB_ALIAS].cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    except Exception:
        return False


def check_redis() -> bool:
    """True when the broker/locks Redis answers PING."""
    try:
        return bool(get_redis().ping())
    except Exception:
        return False


def migrations_applied() -> bool:
    """True when no migration is pending on the default database."""
    try:
        connection = connections[DEFAULT_DB_ALIAS]
        executor = MigrationExecutor(connection)
        return not executor.migration_plan(executor.loader.graph.leaf_nodes())
    except Exception:
        return False


def ingestor_heartbeat_age_seconds() -> float | None:
    """Seconds since the ingestor last wrote its heartbeat, or None when absent/unreadable."""
    try:
        raw = get_redis().get(HEARTBEAT_KEY)
    except Exception:
        return None
    if not raw:
        return None
    try:
        beat = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    if beat.tzinfo is None:
        beat = beat.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - beat).total_seconds())


def liveness() -> dict[str, Any]:
    """Payload for `/healthz`: only the aggregate status is exposed publicly."""
    ok = check_database() and check_redis()
    return {"status": "ok" if ok else "error"}


def readiness(detailed: bool) -> dict[str, Any]:
    """Payload for `/readyz`; per-component detail only for allowlisted callers."""
    checks = {"database": check_database(), "redis": check_redis(), "migrations": migrations_applied()}
    payload: dict[str, Any] = {"status": "ok" if all(checks.values()) else "error"}
    if detailed:
        payload["checks"] = checks
        payload["ingestor_heartbeat_age_seconds"] = ingestor_heartbeat_age_seconds()
    return payload
