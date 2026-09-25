"""Deterministic stages: triage, normalize, length policy, media select, publish policy (AI_PIPELINE §2)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from django.db.models import QuerySet

from apps.ai.schemas import Draft, Extraction, FactCheck
from apps.core.translit import is_mostly_cyrillic
from apps.telegram.models import MediaStatus, TelegramMedia, TelegramPost

VISUAL_KINDS = frozenset({"photo", "video", "animation"})
GENERIC_SIGNATURES = [
    r"(?im)^\s*@\w+\s*$",
    r"(?im)^.*(rasmiy telegram kanal|rasmiy kanal|obuna boʻling|obuna bo'ling|подписывайтесь).*$",
    r"(?im)^\s*(👉|➡️|🔗|✅)\s*(t\.me/|https?://)\S+\s*$",
]
_EMOJI_ONLY = re.compile(r"^[\W_\d]*$", re.UNICODE)
_URL = re.compile(r"https?://\S+|t\.me/\S+", re.IGNORECASE)


# --- triage ---------------------------------------------------------------------------------------


def word_count(text: str) -> int:
    return len(re.findall(r"[^\W\d_]+", _URL.sub(" ", text or ""), re.UNICODE))


def _is_emoji_only(text: str) -> bool:
    stripped = "".join(ch for ch in (text or "") if not unicodedata.category(ch).startswith(("Z", "C")))
    return (
        bool(stripped) and _EMOJI_ONLY.match(stripped) is not None and not any(c.isalpha() for c in stripped)
    )


def triage(post: TelegramPost, media: list[TelegramMedia], institution_usernames: set[str]) -> str | None:
    """Return a skip reason (`skipped:<reason>` minus the prefix) or None to continue (AI_PIPELINE §2.1)."""
    text = post.text or ""
    words = word_count(text)
    live_media = [m for m in media if m.error != "deleted_in_telegram"]
    kinds = {m.kind for m in live_media}
    has_visual = bool(kinds & VISUAL_KINDS)
    if post.is_deleted:
        return "deleted"
    if isinstance(post.raw_json, dict) and post.raw_json.get("_") == "MessageService":
        return "service"
    if not text.strip() and not live_media:
        return "empty"
    if (not text.strip() or _is_emoji_only(text)) and kinds <= {"sticker", "animation"} and live_media:
        return "sticker_only"
    if _is_emoji_only(text) and not has_visual:
        return "sticker_only"
    if words < 12 and not has_visual:
        return "link_only" if post.links else "short_text"
    if (
        post.is_forwarded
        and words < 30
        and not _forward_is_institution(post.forward_from, institution_usernames)
    ):
        return "forward_short"
    if post.content_hash and (
        TelegramPost.objects.filter(
            source_id=post.source_id,
            content_hash=post.content_hash,
            published_at__gte=post.published_at - timedelta(days=7),
            published_at__lt=post.published_at,
        )
        .exclude(pk=post.pk)
        .exists()
    ):
        return "duplicate_hash"
    return None


def _forward_is_institution(forward_from: str, usernames: set[str]) -> bool:
    low = (forward_from or "").lower()
    return any(u in low for u in usernames)


# --- normalize ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Normalized:
    text: str
    script: str  # "latin" | "cyrillic"
    hashtags: list[str]
    links: list[str]
    media_descriptors: str
    source_text: str
    word_count: int


def _descriptors(media: list[TelegramMedia]) -> str:
    live = [m for m in media if m.error != "deleted_in_telegram"]
    total = len(live)
    parts = []
    for index, m in enumerate(live, start=1):
        if m.kind == "video" and m.duration_seconds:
            parts.append(f"[video {m.duration_seconds} s]")
        else:
            parts.append(f"[{m.kind} {index}/{total}]")
    return " ".join(parts) or "—"


def normalize(post: TelegramPost, media: list[TelegramMedia], signature_patterns: list[str]) -> Normalized:
    """Strip channel signatures, keep hashtags/links, flag the script, build the prompt source text."""
    text = post.text or ""
    for pattern in [*signature_patterns, *GENERIC_SIGNATURES]:
        try:
            text = re.sub(pattern, "", text)
        except re.error:
            continue
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    descriptors = _descriptors(media)
    return Normalized(
        text=text,
        script="cyrillic" if is_mostly_cyrillic(text) else "latin",
        hashtags=list(post.hashtags or []),
        links=list(post.links or []),
        media_descriptors=descriptors,
        source_text=text,
        word_count=word_count(text),
    )


def length_policy(words: int) -> str:
    """AI_PIPELINE §2.5: never pad."""
    if words < 60:
        return "120–200 soʻz"
    if words <= 200:
        return "200–400 soʻz"
    return "300–600 soʻz"


# --- media select ---------------------------------------------------------------------------------


@dataclass
class MediaSelection:
    cover: TelegramMedia | None
    gallery: list[TelegramMedia] = field(default_factory=list)
    documents: list[TelegramMedia] = field(default_factory=list)

    def as_output(self) -> dict[str, Any]:
        return {
            "cover": self.cover.pk if self.cover else None,
            "gallery": [m.pk for m in self.gallery],
            "documents": [m.pk for m in self.documents],
        }


def select_media(media: list[TelegramMedia] | QuerySet[TelegramMedia]) -> MediaSelection:
    """Cover = widest photo; gallery = the other photos in order; video poster as fallback cover (§2.7)."""
    usable = [m for m in media if m.status in (MediaStatus.DOWNLOADED, MediaStatus.READY) and m.original]
    photos = [m for m in usable if m.kind == "photo"]
    cover: TelegramMedia | None = max(photos, key=lambda m: (m.width or 0, -m.order)) if photos else None
    if cover is None:
        cover = next((m for m in usable if m.kind in ("video", "animation")), None)
    gallery = [m for m in sorted(photos, key=lambda m: m.order) if m is not cover]
    documents = [m for m in media if m.kind == "document" and m.error != "deleted_in_telegram"]
    return MediaSelection(cover=cover, gallery=gallery, documents=documents)


# --- publish policy -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str


def decide(
    draft: Draft,
    extraction: Extraction,
    factcheck: FactCheck,
    *,
    publish_mode: str,
    threshold: float,
) -> Decision:
    """The only gate to public (AI_PIPELINE §2.9)."""
    if publish_mode == "off":
        return Decision("draft", "publish_mode_off")
    if publish_mode == "review":
        return Decision("review", "publish_mode_review")
    if factcheck.verdict != "pass":
        return Decision("review", "fact_guard_failed")
    if factcheck.risk_flags:
        return Decision("review", "risk:" + ",".join(factcheck.risk_flags))
    if extraction.is_low_value:
        return Decision("review", "low_value")
    if extraction.content_type in {"advertisement", "service"}:
        return Decision("review", "content_type")
    if extraction.importance < 2:
        return Decision("review", "importance")
    if draft.confidence < threshold:
        return Decision("review", "confidence")
    return Decision("published", "auto")


def article_content_type(extracted: str) -> str:
    """Map the extraction content type onto `Article.content_type` (§2.2)."""
    if extracted in {"congratulation", "advertisement", "service"}:
        return "announcement"
    return extracted if extracted != "other" else "other"
