"""HTML sanitizer allowlist (SPEC §2) and apostrophe normalization."""

from __future__ import annotations

import pytest

from apps.core.sanitize import sanitize_html, strip_tags


def test_removes_scripts_handlers_and_unknown_tags() -> None:
    dirty = '<p onclick="x()">Salom<script>alert(1)</script><iframe src="//evil"></iframe><span>!</span></p>'
    assert sanitize_html(dirty) == "<p>Salom!</p>"


def test_javascript_links_dropped_and_rel_forced() -> None:
    out = sanitize_html('<a href="javascript:alert(1)">x</a> <a href="https://t.me/x" target="_blank">t</a>')
    assert "javascript" not in out
    assert 'href="https://t.me/x"' in out
    assert 'rel="noopener noreferrer nofollow"' in out


def test_allowlist_kept() -> None:
    html = (
        "<h2>Sarlavha</h2><ul><li><strong>a</strong></li></ul><blockquote><em>b</em></blockquote>"
        '<figure><img src="/media/a.webp" alt="A" width="10" height="5"><figcaption>c</figcaption></figure>'
        '<table><thead><tr><th scope="col">h</th></tr></thead><tbody><tr><td>d</td></tr></tbody></table>'
    )
    assert sanitize_html(html) == html


def test_img_attributes_restricted() -> None:
    out = sanitize_html('<img src="/a.png" onerror="x()" style="color:red" alt="a">')
    assert "onerror" not in out and "style" not in out


def test_apostrophes_normalized_in_text_but_not_in_attributes() -> None:
    out = sanitize_html("<p>O'zbekiston ta'lim</p><a href=\"https://x.uz/o'z\">g'oya</a>")
    assert "Oʻzbekiston taʼlim" in out
    assert "gʻoya" in out
    assert "https://x.uz/o'z" in out or "https://x.uz/o%27z" in out


def test_empty_and_strip_tags() -> None:
    assert sanitize_html(None) == ""
    assert strip_tags("<p>Bir</p>\n<p>ikki   uch</p>") == "Bir ikki uch"


@pytest.mark.django_db
def test_models_sanitize_rich_fields_in_every_language() -> None:
    from apps.core.models import Page

    page = Page.objects.create(
        slug="t", title="T", body="<p>ok</p><script>x</script>", body_ru='<p onclick="x()">ru</p>'
    )
    page.refresh_from_db()
    assert page.body_uz == "<p>ok</p>"
    assert page.body_ru == "<p>ru</p>"
