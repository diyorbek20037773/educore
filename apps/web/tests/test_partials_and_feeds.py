"""HTMX partials, chart data, search, feeds, sitemap and SEO files."""

from __future__ import annotations

import json
from xml.etree import ElementTree  # noqa: S405 - parses our own responses

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.content.tests.factories import ArticleFactory
from apps.web.services.search import normalize_query
from apps.web.tests.conftest import SiteData

HTMX = {"HTTP_HX_REQUEST": "true"}


def test_live_panel_partial_and_filter(client: Client, site_data: SiteData) -> None:
    response = client.get(reverse("web:live_panel"), **HTMX)
    body = response.content.decode()
    assert response.status_code == 200
    assert "<html" not in body and 'id="live-panel"' in body
    assert site_data.article.title in body
    abbr = site_data.institution.abbreviation
    filtered = client.get(reverse("web:live_panel"), {"inst": abbr}, **HTMX).content.decode()
    assert 'aria-pressed="true"' in filtered and f"?inst={abbr}" in filtered
    other = client.get(reverse("web:live_panel"), {"inst": "JXU" if abbr != "JXU" else "FVV"}, **HTMX)
    assert site_data.article.title not in other.content.decode()


def test_news_filters_and_infinite_scroll(client: Client, site_data: SiteData) -> None:
    for _n in range(30):
        ArticleFactory(primary_institution=site_data.institution, category=site_data.article.category)
    url = reverse("web:news_list")
    results = client.get(url, {"inst": site_data.institution.slug}, **HTMX).content.decode()
    assert "<html" not in results and 'id="results"' in results
    assert 'hx-trigger="revealed"' in results
    page2 = client.get(url, {"page": 2}, **HTMX).content.decode()
    assert "<html" not in page2 and "<article" in page2
    empty = client.get(url, {"category": "yoq-kategoriya"}, **HTMX).content.decode()
    assert "topilmadi" in empty


def test_boosted_and_history_requests_get_full_pages(client: Client, site_data: SiteData) -> None:
    url = reverse("web:news_list")
    boosted = client.get(url, HTTP_HX_REQUEST="true", HTTP_HX_BOOSTED="true").content.decode()
    restore = client.get(url, HTTP_HX_REQUEST="true", HTTP_HX_HISTORY_RESTORE_REQUEST="true").content.decode()
    assert "<html" in boosted and "<html" in restore


def test_news_list_query_count_is_constant(client: Client, site_data: SiteData) -> None:
    url = reverse("web:news_list")
    client.get(url)  # warm the global context cache
    with CaptureQueriesContext(connection) as small:
        client.get(url)
    for _n in range(20):
        ArticleFactory(primary_institution=site_data.institution, category=site_data.article.category)
    with CaptureQueriesContext(connection) as large:
        client.get(url)
    assert len(large.captured_queries) == len(small.captured_queries)


@pytest.mark.parametrize(
    "chart", ["activity", "categories", "heatmap", "engagement", "tags", "compare", "radar"]
)
def test_chart_data_contract(client: Client, site_data: SiteData, chart: str) -> None:
    response = client.get(reverse("web:analytics_data", args=[chart]), {"days": 90})
    assert response.status_code == 200
    data = response.json()
    assert data["kind"] in {"line", "bar", "hbar", "grouped", "heatmap", "radar"}
    assert {"columns", "rows"} <= set(data["table"])
    csv = client.get(reverse("web:analytics_data", args=[chart]), {"days": 90, "format": "csv"})
    assert csv["Content-Type"].startswith("text/csv")
    assert csv.content.decode().splitlines()[0].count(",") == len(data["table"]["columns"]) - 1


def test_activity_series_use_fixed_institution_colours(client: Client, site_data: SiteData) -> None:
    data = client.get(reverse("web:analytics_data", args=["activity"]), {"period": "12m"}).json()
    assert len(data["categories"]) == 12
    first = data["series"][0]
    assert (
        first["name"] == site_data.institution.abbreviation and first["color"] == site_data.institution.color
    )
    assert sum(first["data"]) >= 6


def test_unknown_chart_is_404(client: Client, db: None) -> None:
    assert client.get(reverse("web:analytics_data", args=["nope"])).status_code == 404


def test_search_matches_both_scripts(client: Client, site_data: SiteData) -> None:
    assert normalize_query("  Академия ") == "Akademiya"
    for query in ("ochiq eshiklar", "очиқ эшиклар"):
        body = client.get(reverse("web:search"), {"q": query}).content.decode()
        assert site_data.article.title in body, query
    suggest = client.get(reverse("web:search_suggest"), {"q": "eshiklar"}, **HTMX).content.decode()
    assert "<html" not in suggest and site_data.article.get_absolute_url() in suggest


def test_event_ics(client: Client, site_data: SiteData) -> None:
    response = client.get(reverse("web:event_ics", kwargs={"slug": site_data.event.slug}))
    text = response.content.decode()
    assert response["Content-Type"].startswith("text/calendar")
    assert (
        text.startswith("BEGIN:VCALENDAR\r\n") and "SUMMARY:" in text and text.endswith("END:VCALENDAR\r\n")
    )
    assert all(len(line.encode()) <= 75 for line in text.split("\r\n"))


def test_compare_csv(client: Client, site_data: SiteData) -> None:
    response = client.get(reverse("web:institution_compare_csv"))
    assert response["Content-Type"].startswith("text/csv")
    assert site_data.institution.short_name in response.content.decode()


def test_rss_feeds_are_valid_xml(client: Client, site_data: SiteData) -> None:
    for url in (
        reverse("web:rss"),
        reverse("web:rss_institution", kwargs={"slug": site_data.institution.slug}),
        reverse("web:rss_category", kwargs={"slug": "yangiliklar"}),
    ):
        root = ElementTree.fromstring(client.get(url).content)  # noqa: S314
        titles = [item.findtext("title") for item in root.iter("item")]
        assert site_data.article.title in titles, url
    assert client.get(reverse("web:rss_category", kwargs={"slug": "yoq"})).status_code == 404


def test_sitemap_lists_sections_and_alternates(client: Client, site_data: SiteData) -> None:
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    body = response.content.decode()
    ElementTree.fromstring(response.content)  # noqa: S314
    assert site_data.article.get_absolute_url() in body
    assert 'hreflang="uz-cyrl"' in body and 'hreflang="x-default"' in body
    assert "/ru/muassasalar/" in body


def test_robots_manifest_humans(client: Client, db: None) -> None:
    robots = client.get("/robots.txt").content.decode()
    assert "Sitemap:" in robots and "Disallow: /partials/" in robots
    manifest = json.loads(client.get("/manifest.webmanifest").content)
    assert manifest["name"] == "EDUCORE" and any(i["sizes"] == "512x512" for i in manifest["icons"])
    assert client.get("/humans.txt").status_code == 200


@pytest.mark.parametrize(
    "name", ["home", "event_list", "program_list", "profession_list", "story_list", "search"]
)
def test_list_query_counts_do_not_grow_with_data(client: Client, site_data: SiteData, name: str) -> None:
    from apps.content.tests.factories import EventFactory, StoryFactory

    url = reverse(f"web:{name}") + ("?q=akademiya" if name == "search" else "")
    client.get(url)
    with CaptureQueriesContext(connection) as before:
        client.get(url)
    for _n in range(8):
        ArticleFactory(primary_institution=site_data.institution, category=site_data.article.category)
        EventFactory(institution=site_data.institution)
        StoryFactory(institution=site_data.institution)
    from django.core.cache import cache

    cache.clear()
    client.get(url)
    with CaptureQueriesContext(connection) as after:
        client.get(url)
    assert len(after.captured_queries) <= len(before.captured_queries), name


def test_theme_toggle_and_skip_link_present(client: Client, site_data: SiteData) -> None:
    body = client.get("/").content.decode()
    assert 'x-data="themeToggle"' in body and "aria-pressed" in body
    assert 'class="skip-link" href="#main"' in body
    assert 'localStorage.getItem("educore-theme")' in body


def test_compare_shows_only_metrics_with_values(client: Client, site_data: SiteData) -> None:
    from apps.institutions.models import InstitutionMetric

    InstitutionMetric.objects.all().update(value=None)
    empty = client.get(reverse("web:institution_compare")).content.decode()
    assert "data-chart" not in empty
    InstitutionMetric.objects.filter(institution=site_data.institution, key="students").update(value=1234)
    from django.core.cache import cache

    cache.clear()  # queryset.update() does not bump the content version
    body = client.get(reverse("web:institution_compare")).content.decode()
    assert "234" in body and "compare-students" in body
    assert client.get(reverse("web:analytics_data", args=["compare"]), {"metric": "students"}).json()[
        "series"
    ]
