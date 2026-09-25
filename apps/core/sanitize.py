"""HTML sanitizer for AI and editor content (SPEC §2, NFR-SEC-3) built on nh3."""

from __future__ import annotations

import re

import nh3

from apps.core.text import normalize_uzbek_apostrophes

ALLOWED_TAGS: set[str] = {
    "p", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "strong", "em", "a", "br",
    "figure", "figcaption", "img", "table", "thead", "tbody", "tr", "th", "td",
}  # fmt: skip
ALLOWED_ATTRIBUTES: dict[str, set[str]] = {
    "a": {"href", "target"},
    "img": {"src", "alt", "width", "height"},
    "th": {"scope"},
}
URL_SCHEMES: set[str] = {"http", "https", "mailto", "tel"}
_TAG_SPLIT = re.compile(r"(<[^>]+>)")


def sanitize_html(html: str | None) -> str:
    """Return safe HTML: allowlisted tags/attributes, safe URL schemes, `rel` forced, official apostrophes."""
    if not html:
        return ""
    cleaned = nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
        strip_comments=True,
    )
    parts = _TAG_SPLIT.split(cleaned)
    return "".join(p if p.startswith("<") else normalize_uzbek_apostrophes(p) for p in parts).strip()


def strip_tags(html: str | None) -> str:
    """Plain text of an HTML fragment (for search, reading time, meta descriptions)."""
    if not html:
        return ""
    text = nh3.clean(html, tags=set())
    return re.sub(r"\s+", " ", text).strip()
