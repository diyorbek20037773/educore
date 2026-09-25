"""Cookie-less page view counting in Redis (SPEC §2.8) and the hourly flush into the database.

Keys (all expire after `KEY_TTL`):
- `educore:pv:{day}`          total page views of a local day (INCR)
- `educore:uv:{day}`          HyperLogLog of salted visitor hashes (IP + user agent, salt rotates daily)
- `educore:sq:{day}`          search requests of the day
- `educore:pv:articles`       hash article id -> pending views (moved away atomically on flush)
- `educore:sq:terms`          hash normalized query -> pending count
Redis problems never break a request: every write is best effort and logged.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import date, timedelta

import redis
import structlog
from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.analytics.models import DailyStat, SearchLog
from apps.content.models import Article
from apps.core.redis import get_redis

log = structlog.get_logger(__name__)

PREFIX = "educore"
KEY_TTL = 3 * 24 * 3600
ARTICLES_KEY = f"{PREFIX}:pv:articles"
TERMS_KEY = f"{PREFIX}:sq:terms"


def _day(day: date | None = None) -> str:
    return (day or timezone.localdate()).isoformat()


def visitor_hash(ip: str, user_agent: str, day: date | None = None) -> str:
    """Salted, daily-rotated hash: counts unique visitors without storing IPs or setting cookies."""
    salt = hmac.new(settings.SECRET_KEY.encode(), _day(day).encode(), hashlib.sha256).digest()
    return hashlib.sha256(salt + f"{ip}|{user_agent}".encode()).hexdigest()[:32]


def record_pageview(ip: str, user_agent: str) -> None:
    day = _day()
    try:
        pipe = get_redis().pipeline()
        pipe.incr(f"{PREFIX}:pv:{day}")
        pipe.expire(f"{PREFIX}:pv:{day}", KEY_TTL)
        pipe.pfadd(f"{PREFIX}:uv:{day}", visitor_hash(ip, user_agent))
        pipe.expire(f"{PREFIX}:uv:{day}", KEY_TTL)
        pipe.execute()
    except redis.RedisError as exc:
        log.warning("pageview_record_failed", error=str(exc))


def record_article_view(article_id: int) -> None:
    try:
        get_redis().hincrby(ARTICLES_KEY, str(article_id), 1)
    except redis.RedisError as exc:
        log.warning("article_view_record_failed", article_id=article_id, error=str(exc))


def record_search(query_norm: str) -> None:
    if not query_norm:
        return
    day = _day()
    try:
        pipe = get_redis().pipeline()
        pipe.incr(f"{PREFIX}:sq:{day}")
        pipe.expire(f"{PREFIX}:sq:{day}", KEY_TTL)
        pipe.hincrby(TERMS_KEY, query_norm.lower()[:200], 1)
        pipe.execute()
    except redis.RedisError as exc:
        log.warning("search_record_failed", error=str(exc))


def _drain_hash(key: str) -> dict[str, int]:
    """Atomically move a hash away and return it (increments arriving meanwhile start a new hash)."""
    client = get_redis()
    temp = f"{key}:flushing:{uuid.uuid4().hex}"
    try:
        client.rename(key, temp)
    except redis.ResponseError:  # key does not exist: nothing pending
        return {}
    values = {field: int(count) for field, count in client.hgetall(temp).items()}
    client.delete(temp)
    return values


def flush(days: int = 2) -> dict[str, int]:
    """Write Redis counters to the database: day totals (absolute, idempotent) and pending increments."""
    client = get_redis()
    today = timezone.localdate()
    for offset in range(days):
        day = today - timedelta(days=offset)
        key = _day(day)
        pageviews = int(client.get(f"{PREFIX}:pv:{key}") or 0)
        searches = int(client.get(f"{PREFIX}:sq:{key}") or 0)
        visitors = int(client.pfcount(f"{PREFIX}:uv:{key}"))
        if pageviews or searches or visitors:
            DailyStat.objects.update_or_create(
                date=day,
                defaults={"pageviews": pageviews, "unique_visitors": visitors, "search_queries": searches},
            )
    articles = _drain_hash(ARTICLES_KEY)
    for article_id, count in articles.items():
        Article.objects.filter(pk=int(article_id)).update(view_count=F("view_count") + count)
    terms = _drain_hash(TERMS_KEY)
    now = timezone.now()
    for query, count in terms.items():
        updated = SearchLog.objects.filter(query_norm=query).update(
            count=F("count") + count, last_searched_at=now
        )
        if not updated:
            SearchLog.objects.create(query_norm=query, count=count, last_searched_at=now)
    result = {"articles": len(articles), "terms": len(terms)}
    log.info("pageviews_flushed", **result)
    return result
