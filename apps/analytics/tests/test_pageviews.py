"""Cookie-less page views: counting rules, unique visitors, hourly flush (SPEC §2.8)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from django.test import Client
from django.utils import timezone

from apps.analytics.models import DailyStat, SearchLog
from apps.analytics.services import pageviews
from apps.analytics.tasks import flush_pageviews
from apps.analytics.tests.utils import clear_counters
from apps.content.tests.factories import ArticleFactory

pytestmark = pytest.mark.django_db
BROWSER = "Mozilla/5.0 (X11; Linux x86_64) Chrome/140"


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    clear_counters()
    yield
    clear_counters()


def _today() -> DailyStat:
    pageviews.flush()
    return DailyStat.objects.get(date=timezone.localdate())


def test_visitor_hash_rotates_daily_and_hides_ip() -> None:
    first = pageviews.visitor_hash("203.0.113.7", BROWSER, timezone.localdate())
    other_day = pageviews.visitor_hash("203.0.113.7", BROWSER, timezone.localdate().replace(year=2020))
    assert first != other_day and "203.0.113.7" not in first and len(first) == 32


def test_pages_are_counted_with_unique_visitors(client: Client) -> None:
    for ip in ("203.0.113.7", "203.0.113.7", "198.51.100.1"):
        assert client.get("/robots.txt", HTTP_USER_AGENT=BROWSER).status_code == 200  # not HTML: ignored
        client.get("/", REMOTE_ADDR=ip, HTTP_USER_AGENT=BROWSER)
    stat = _today()
    assert stat.pageviews == 3 and stat.unique_visitors == 2


def test_bots_fragments_errors_and_staff_are_not_counted(
    client: Client, verified_admin_client: Client
) -> None:
    client.get("/", HTTP_USER_AGENT="Googlebot/2.1")
    client.get("/partials/jonli-lenta/", HTTP_USER_AGENT=BROWSER, HTTP_HX_REQUEST="true")
    client.get("/yoq-sahifa/", HTTP_USER_AGENT=BROWSER)
    verified_admin_client.get("/", HTTP_USER_AGENT=BROWSER)
    pageviews.flush()
    assert not DailyStat.objects.filter(date=timezone.localdate(), pageviews__gt=0).exists()
    client.get("/", HTTP_USER_AGENT=BROWSER, HTTP_HX_REQUEST="true", HTTP_HX_BOOSTED="true")
    assert _today().pageviews == 1


def test_article_views_and_search_terms_flush(client: Client, db: Any) -> None:
    article = ArticleFactory()
    for _n in range(3):
        pageviews.record_article_view(article.pk)
    pageviews.record_search("qabul")
    pageviews.record_search("qabul")
    assert flush_pageviews.apply().get() == {"articles": 1, "terms": 1}
    article.refresh_from_db()
    assert article.view_count == 3
    assert SearchLog.objects.get(query_norm="qabul").count == 2
    assert DailyStat.objects.get(date=timezone.localdate()).search_queries == 2
    # A second flush adds nothing (pending hashes were drained).
    pageviews.flush()
    article.refresh_from_db()
    assert article.view_count == 3


def test_redis_errors_never_break_requests(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    import redis

    def broken() -> Any:
        raise redis.ConnectionError("down")

    monkeypatch.setattr(pageviews, "get_redis", broken)
    pageviews.record_article_view(1)
    pageviews.record_search("x")
    assert client.get("/", HTTP_USER_AGENT=BROWSER).status_code == 200
