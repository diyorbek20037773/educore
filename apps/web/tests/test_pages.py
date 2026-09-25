"""Public pages: every route renders in all four languages; detail visibility rules (SPEC §6)."""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import translation

from apps.web.tests.conftest import SiteData

LANGS = ("uz", "uz-cyrl", "ru", "en")
STATIC_ROUTES = (
    "home",
    "institution_list",
    "institution_compare",
    "news_list",
    "longread_list",
    "program_list",
    "admissions",
    "students_hub",
    "cadets_hub",
    "profession_list",
    "event_list",
    "story_list",
    "analytics",
    "appeal_form",
    "appeal_track",
    "search",
    "about",
    "contact",
    "privacy",
    "terms",
)
INSTITUTION_TABS = ("detail", "programs", "admissions", "life", "news", "events", "contacts")


def _detail_urls(data: SiteData) -> list[str]:
    urls = [
        reverse(f"web:institution_{tab}", kwargs={"slug": data.institution.slug}) for tab in INSTITUTION_TABS
    ]
    urls += [
        data.article.get_absolute_url(),
        data.longread.get_absolute_url(),
        data.event.get_absolute_url(),
        data.story.get_absolute_url(),
        data.program.get_absolute_url(),
        data.profession.get_absolute_url(),
        reverse("web:search") + "?q=akademiya",
        reverse("web:search") + "?q=академия",
        reverse("web:event_list") + "?view=calendar",
        reverse("web:event_list") + "?when=past",
        reverse("web:appeal_success", kwargs={"code": "EDU-TEST"}),
    ]
    return urls


@pytest.mark.parametrize("lang", LANGS)
def test_every_page_renders(client: Client, site_data: SiteData, lang: str) -> None:
    with translation.override(lang):
        urls = [reverse(f"web:{name}") for name in STATIC_ROUTES] + _detail_urls(site_data)
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, url
        assert response["Content-Type"].startswith("text/html"), url
        if lang != "uz":
            assert url.startswith(f"/{lang}/"), url
        body = response.content.decode()
        assert "<html" in body and 'rel="canonical"' in body, url
        assert 'hreflang="uz-Cyrl"' in body, url


def test_language_prefixes_and_html_lang(client: Client, site_data: SiteData) -> None:
    assert 'lang="uz-Latn"' in client.get("/").content.decode()
    assert 'lang="uz-Cyrl"' in client.get("/uz-cyrl/").content.decode()
    assert 'lang="ru"' in client.get("/ru/").content.decode()


def test_home_blocks(client: Client, site_data: SiteData) -> None:
    body = client.get("/").content.decode()
    assert site_data.article.title in body
    assert 'id="live-panel"' in body
    assert "data-chart" in body
    assert site_data.institution.short_name in body


def test_article_detail_has_jsonld_source_and_breadcrumbs(client: Client, site_data: SiteData) -> None:
    body = client.get(site_data.article.get_absolute_url()).content.decode()
    assert '"@type":"NewsArticle"' in body
    assert "BreadcrumbList" in body
    assert "rasmiy Telegram kanalidagi xabar asosida tayyorlandi" in body
    post = site_data.article.sources.get().post
    assert post.telegram_url and f'href="{post.telegram_url}"' in body
    assert 'property="og:type" content="article"' in body


def test_article_view_counter(client: Client, site_data: SiteData) -> None:
    client.get(site_data.article.get_absolute_url())
    site_data.article.refresh_from_db()
    assert site_data.article.view_count == 1


def test_longread_has_toc_and_redirects_from_news_route(client: Client, site_data: SiteData) -> None:
    body = client.get(site_data.longread.get_absolute_url()).content.decode()
    assert 'id="birinchi-bolim"' in body and 'href="#birinchi-bolim"' in body
    wrong = reverse("web:news_detail", kwargs={"slug": site_data.longread.slug})
    response = client.get(wrong)
    assert response.status_code == 301
    assert response["Location"] == site_data.longread.get_absolute_url()


def test_archived_article_is_gone(client: Client, site_data: SiteData) -> None:
    site_data.article.status = "archived"
    site_data.article.save(update_fields=["status"])
    response = client.get(site_data.article.get_absolute_url())
    assert response.status_code == 410
    assert (
        reverse("web:institution_news", kwargs={"slug": site_data.institution.slug})
        in response.content.decode()
    )


def test_draft_is_404_for_public_and_previewable_for_staff(
    client: Client, verified_admin_client: Client, site_data: SiteData
) -> None:
    site_data.article.status = "review"
    site_data.article.save(update_fields=["status"])
    url = site_data.article.get_absolute_url()
    assert client.get(url).status_code == 404
    assert client.get(url + "?preview=1").status_code == 404
    assert verified_admin_client.get(url).status_code == 404
    response = verified_admin_client.get(url + "?preview=1")
    assert response.status_code == 200
    assert b'name="robots" content="noindex"' in response.content


@pytest.mark.parametrize(
    "name,kwargs",
    [
        ("news_detail", {"slug": "yoq-maqola"}),
        ("institution_detail", {"slug": "yoq-muassasa"}),
        ("event_detail", {"slug": "yoq"}),
        ("story_detail", {"slug": "yoq"}),
        ("profession_detail", {"slug": "yoq"}),
        ("program_detail", {"institution": "yoq", "slug": "yoq"}),
    ],
)
def test_unknown_slugs_are_404(
    client: Client, site_data: SiteData, name: str, kwargs: dict[str, Any]
) -> None:
    response = client.get(reverse(f"web:{name}", kwargs=kwargs))
    assert response.status_code == 404
    assert "Sahifa topilmadi" in response.content.decode()


def test_unpublished_event_is_404(client: Client, site_data: SiteData) -> None:
    site_data.event.is_published = False
    site_data.event.save(update_fields=["is_published"])
    assert client.get(site_data.event.get_absolute_url()).status_code == 404


def test_fallback_notice_for_untranslated_content(client: Client, site_data: SiteData) -> None:
    uz_url = site_data.article.get_absolute_url()
    with translation.override("ru"):
        ru_url = site_data.article.get_absolute_url()
    assert "Эта страница ещё не переведена" in client.get(ru_url).content.decode()
    assert "Ushbu sahifa hali tarjima qilinmagan" not in client.get(uz_url).content.decode()


def test_missing_cms_page_is_404(client: Client, db: Any) -> None:
    assert client.get(reverse("web:about")).status_code == 404


def test_appeal_form_validation(client: Client, site_data: SiteData) -> None:
    url = reverse("web:appeal_form")
    response = client.post(url, {"topic": "qabul", "full_name": "Ali", "phone": "123", "message": "qisqa"})
    body = response.content.decode()
    assert response.status_code == 200
    assert 'aria-invalid="true"' in body and 'id="phone-error"' in body
    valid = {
        "topic": "qabul",
        "full_name": "Ali Valiyev",
        "phone": "+998 90 123 45 67",
        "message": "Qabul hujjatlari boʻyicha savolim bor, iltimos javob bering.",
        "consent": "on",
    }
    assert "Maʼlumotlar toʻgʻri toʻldirildi" in client.post(url, valid).content.decode()


def test_appeal_tracking(client: Client, site_data: SiteData) -> None:
    from apps.appeals.tests.factories import AppealFactory, AppealMessageFactory

    appeal = AppealFactory(tracking_code="EDU-ABC123", institution=site_data.institution)
    AppealMessageFactory(appeal=appeal, body="Javob matni", author=None, is_public=True)
    url = reverse("web:appeal_track")
    body = client.get(url, {"code": "edu-abc123"}).content.decode()
    assert "EDU-ABC123" in body
    # Applicant's own messages (author=None) are not listed as replies.
    assert "Javob matni" not in body
    assert "topilmadi" in client.get(url, {"code": "NOPE"}).content.decode()


def test_jsonld_blocks_are_valid_json(client: Client, site_data: SiteData) -> None:
    import json
    import re

    pattern = re.compile(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
    urls = [
        "/",
        site_data.article.get_absolute_url(),
        site_data.event.get_absolute_url(),
        site_data.institution.get_absolute_url(),
    ]
    types = set()
    for url in urls:
        for block in pattern.findall(client.get(url).content.decode()):
            types.add(json.loads(block)["@type"])
    assert {
        "WebSite",
        "Organization",
        "NewsArticle",
        "Event",
        "CollegeOrUniversity",
        "BreadcrumbList",
    } <= types
