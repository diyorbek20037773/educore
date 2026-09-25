"""Content-version key for fragment/sitemap cache invalidation (ARCHITECTURE §5)."""

from __future__ import annotations

import time

from django.core.cache import cache

CONTENT_VERSION_KEY = "content_version"


def content_version() -> int:
    """Current version; part of every fragment cache key."""
    value = cache.get(CONTENT_VERSION_KEY)
    if value is None:
        value = int(time.time())
        cache.add(CONTENT_VERSION_KEY, value, timeout=None)
    return int(value)


def bump_content_version() -> int:
    """Invalidate every fragment keyed by the content version (publish/edit/archive)."""
    try:
        return int(cache.incr(CONTENT_VERSION_KEY))
    except ValueError:
        value = int(time.time())
        cache.set(CONTENT_VERSION_KEY, value, timeout=None)
        return value
