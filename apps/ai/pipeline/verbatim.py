"""`CONTENT_MODE=verbatim`: publish a Telegram post as it is — no LLM call, no rewriting (ADR-033).

The post text becomes the article body unchanged (Telegram formatting and links kept), the first line becomes
the title, and every photo and video of the post is attached. Edits rewrite the article from the new text;
deletions archive it through the shared runner path.
"""

from __future__ import annotations

import html
import re
from typing import Any

from django.utils.text import Truncator

from apps.ai.pipeline import rules
from apps.ai.pipeline.context import PostContext
from apps.ai.providers.mock import CATEGORY_KEYWORDS
from apps.ai.schemas import Draft, Extraction, FactCheck
from apps.core.translit import is_mostly_cyrillic
from apps.telegram.models import MediaStatus, TelegramMedia, TelegramPost

VERBATIM_VERSION = "verbatim-1"
SKIP_REASONS = frozenset({"deleted", "service", "empty"})
_URL = re.compile(r"https?://\S+|t\.me/\S+", re.IGNORECASE)
_HASHTAG = re.compile(r"#[\wʻʼ]+")
_NON_TEXT = re.compile(r"[^\w\s.,:;!?«»\"'ʻʼ()№%/+\-–—]", re.UNICODE)
_SPACES = re.compile(r"\s+")

# Telethon entity class → (opening tag, closing tag); anything else is rendered as plain text.
_TAGS: dict[str, tuple[str, str]] = {
    "MessageEntityBold": ("<strong>", "</strong>"),
    "MessageEntityItalic": ("<em>", "</em>"),
    "MessageEntityBlockquote": ("<blockquote>", "</blockquote>"),
}


def skip_reason(post: TelegramPost, media: list[TelegramMedia]) -> str | None:
    """Only posts with nothing to show are skipped (service messages, empty posts, deleted posts)."""
    reason = rules.triage(post, media, set())
    return reason if reason in SKIP_REASONS else None


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


TagMap = dict[int, list[str]]


def _entity_tags(text: str, entities: list[dict[str, Any]]) -> tuple[TagMap, TagMap]:
    """Opening/closing tags keyed by UTF-16 offset (Telegram entity offsets are UTF-16 code units)."""
    opens: TagMap = {}
    closes: TagMap = {}
    for entity in entities or []:
        kind = str(entity.get("_", ""))
        start = int(entity.get("offset", 0))
        end = start + int(entity.get("length", 0))
        if end <= start:
            continue
        if kind == "MessageEntityTextUrl" and entity.get("url"):
            pair = (f'<a href="{html.escape(str(entity["url"]), quote=True)}">', "</a>")
        elif kind == "MessageEntityUrl":
            raw = text.encode("utf-16-le")[start * 2 : end * 2].decode("utf-16-le", errors="ignore")
            href = raw if raw.lower().startswith(("http://", "https://")) else f"https://{raw}"
            pair = (f'<a href="{html.escape(href, quote=True)}">', "</a>")
        elif kind in _TAGS:
            pair = _TAGS[kind]
        else:
            continue
        opens.setdefault(start, []).append(pair[0])
        closes.setdefault(end, []).insert(0, pair[1])
    return opens, closes


def text_to_html(text: str, entities: list[dict[str, Any]] | None = None) -> str:
    """Post text → HTML: escaped, Telegram bold/italic/links kept, blank lines → <p>, newlines → <br>."""
    if not text.strip():
        return ""
    opens, closes = _entity_tags(text, entities or [])
    out: list[str] = []
    position = 0
    for char in text:
        out.extend(closes.pop(position, []))
        out.extend(opens.pop(position, []))
        out.append(html.escape(char, quote=False))
        position += _utf16_len(char)
    out.extend(closes.pop(position, []))
    body = "".join(out).strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    return "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)


def make_title(text: str, fallback: str) -> str:
    """First meaningful line without links, hashtags and emoji; `fallback` for media-only posts."""
    for line in text.splitlines():
        clean = _SPACES.sub(" ", _NON_TEXT.sub(" ", _HASHTAG.sub(" ", _URL.sub(" ", line)))).strip(" -–—:.,")
        if sum(ch.isalpha() for ch in clean) >= 3:
            return Truncator(clean).chars(90)
    return fallback


def _category(text: str) -> str:
    low = text.lower()
    for slug, words in CATEGORY_KEYWORDS:
        if any(w in low for w in words):
            return slug
    return "yangiliklar"


def build(ctx: PostContext) -> tuple[Extraction, Draft, FactCheck]:
    """The pipeline DTOs for a verbatim article, derived only from the post itself."""
    post = ctx.post
    text = post.text or ""
    plain = _SPACES.sub(" ", text).strip()
    words = rules.word_count(text)
    category = _category(text)
    fallback = f"{ctx.source_name} — {post.published_at.date().isoformat()}"
    hashtags = [h.lstrip("#") for h in (post.hashtags or [])][:6]
    extraction = Extraction(
        language="uz-cyrl" if is_mostly_cyrillic(text) else "uz",
        content_type="congratulation" if category == "tabriklar" else "news",
        category_slug=category,
        importance=3,
        is_low_value=False,
        summary_uz=plain,
        tags=hashtags,
    )
    title = make_title(text, fallback)
    draft = Draft(
        title=title,
        lead="",
        body_html=text_to_html(text, list(post.entities or [])),
        seo_title=title,
        seo_description=plain or title,
        tags=hashtags,
        reading_time_min=min(30, max(1, round(words / 200))),
        confidence=1.0,
    )
    return extraction, draft, FactCheck(verdict="pass")


def decision(publish_mode: str) -> rules.Decision:
    """Verbatim posts are published straight away unless publishing is switched off in admin."""
    if publish_mode == "off":
        return rules.Decision("draft", "publish_mode_off")
    return rules.Decision("published", "verbatim")


def select_media(media: list[TelegramMedia]) -> rules.MediaSelection:
    """Every photo and video in Telegram order; cover = first photo (else the first video)."""
    stored = (MediaStatus.DOWNLOADED, MediaStatus.READY)
    usable = [
        m
        for m in sorted(media, key=lambda m: m.order)
        if m.status in stored and m.original and m.kind in rules.VISUAL_KINDS
    ]
    cover = next((m for m in usable if m.kind == "photo"), None) or (usable[0] if usable else None)
    documents = [m for m in media if m.kind == "document" and m.error != "deleted_in_telegram"]
    gallery = [m for m in usable if m is not cover]
    return rules.MediaSelection(cover=cover, gallery=gallery, documents=documents)
