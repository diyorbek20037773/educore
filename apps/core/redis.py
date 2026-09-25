"""Shared Redis client for locks, heartbeat and counters (the `noeviction` instance, `REDIS_URL`)."""

from __future__ import annotations

from functools import lru_cache

import redis
from django.conf import settings


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    """Return a process-wide Redis client with short timeouts (health checks must not hang)."""
    return redis.Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=2,
        socket_timeout=2,
        health_check_interval=30,
        decode_responses=True,
    )
