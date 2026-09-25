"""Test helpers for the Redis page-view counters (test Redis is DB 15)."""

from __future__ import annotations

from apps.core.redis import get_redis


def clear_counters() -> None:
    """Delete only our counter keys; never flush the database."""
    client = get_redis()
    for key in client.scan_iter("educore:pv*"):
        client.delete(key)
    for pattern in ("educore:uv:*", "educore:sq*"):
        for key in client.scan_iter(pattern):
            client.delete(key)
