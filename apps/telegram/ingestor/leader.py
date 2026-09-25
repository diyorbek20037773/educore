"""Single-leader lock and heartbeat in Redis (FR-TG-9, ARCHITECTURE §3.5).

Semantics: the ingestor stops only when the lock is positively held by *another* owner. Redis errors
never stop ingestion (compose guarantees one replica); they are logged and retried.
"""

from __future__ import annotations

import os
import socket
from datetime import UTC, datetime
from enum import StrEnum

import redis
import structlog

log = structlog.get_logger(__name__)

LEADER_KEY = "educore:ingestor:leader"
HEARTBEAT_KEY = "educore:ingestor:heartbeat"
LEADER_TTL_SECONDS = 60
HEARTBEAT_TTL_SECONDS = 180

# Extend only when we still own the key (compare-and-extend).
_RENEW_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


class LockState(StrEnum):
    OWNED = "owned"
    HELD_BY_OTHER = "held_by_other"
    UNKNOWN = "unknown"  # Redis unreachable — keep running


def default_owner() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


class LeaderLock:
    """`SET key owner NX EX ttl` + Lua renew/release."""

    def __init__(self, client: redis.Redis, owner: str | None = None, ttl: int = LEADER_TTL_SECONDS) -> None:
        self.client = client
        self.owner = owner or default_owner()
        self.ttl = ttl

    def acquire(self) -> LockState:
        try:
            if self.client.set(LEADER_KEY, self.owner, nx=True, ex=self.ttl):
                return LockState.OWNED
            current = self.client.get(LEADER_KEY)
        except redis.RedisError as exc:
            log.warning("leader_lock_redis_error", op="acquire", error=str(exc))
            return LockState.UNKNOWN
        if current is None:  # expired between SET and GET — try again next tick
            return LockState.UNKNOWN
        return LockState.OWNED if _decode(current) == self.owner else LockState.HELD_BY_OTHER

    def renew(self) -> LockState:
        try:
            if self.client.eval(_RENEW_LUA, 1, LEADER_KEY, self.owner, self.ttl):
                return LockState.OWNED
            current = self.client.get(LEADER_KEY)
            if current is None:  # our key expired (e.g. after a Redis restart) — take it back
                return self.acquire()
        except redis.RedisError as exc:
            log.warning("leader_lock_redis_error", op="renew", error=str(exc))
            return LockState.UNKNOWN
        return LockState.OWNED if _decode(current) == self.owner else LockState.HELD_BY_OTHER

    def release(self) -> None:
        try:
            self.client.eval(_RELEASE_LUA, 1, LEADER_KEY, self.owner)
        except redis.RedisError as exc:
            log.warning("leader_lock_redis_error", op="release", error=str(exc))

    def is_held_by_anyone(self) -> bool | None:
        """For `telegram_login`/`--standalone`: True when an ingestor holds the lock, None if unknown."""
        try:
            return self.client.exists(LEADER_KEY) == 1
        except redis.RedisError:
            return None


def write_heartbeat(client: redis.Redis, now: datetime | None = None) -> bool:
    """`SET heartbeat <iso> EX 180`; False when Redis is unreachable."""
    stamp = (now or datetime.now(UTC)).isoformat()
    try:
        client.set(HEARTBEAT_KEY, stamp, ex=HEARTBEAT_TTL_SECONDS)
        return True
    except redis.RedisError as exc:
        log.warning("heartbeat_redis_error", error=str(exc))
        return False


def _decode(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value
