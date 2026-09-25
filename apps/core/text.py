"""Uzbek text helpers: official apostrophes (SPEC §7.2), word counts, slugs."""

from __future__ import annotations

import re
import unicodedata

OKINA = "ʻ"  # ʻ — oʻ, gʻ
TUTUQ = "ʼ"  # ʼ — tutuq belgisi
_APOSTROPHES = "'‘’`ʻʼ´"

_OG_APOS = re.compile(rf"([OoGg])[{_APOSTROPHES}]")
# Any other in-word apostrophe (not right after o/g, which step 1 already fixed) is the tutuq.
_INWORD_APOS = re.compile(rf"(?<=[A-Za-z])(?<![OoGg])[{_APOSTROPHES}](?=[A-Za-z])")


def normalize_uzbek_apostrophes(text: str) -> str:
    """`o'`/`g'` (any apostrophe variant) → `oʻ`/`gʻ`; any other in-word apostrophe → tutuq `ʼ`."""
    if not text:
        return text
    text = _OG_APOS.sub(lambda m: m.group(1) + OKINA, text)
    return _INWORD_APOS.sub(TUTUQ, text)


_SLUG_KEEP = re.compile(r"[^a-z0-9]+")


def slugify_uz(value: str, max_length: int = 100) -> str:
    """ASCII slug for Uzbek text: drops ʻ/ʼ (oʻzbek → ozbek), transliterates Cyrillic first."""
    from apps.core.translit import to_latin

    text = to_latin(value or "")
    text = text.replace(OKINA, "").replace(TUTUQ, "")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_KEEP.sub("-", text).strip("-")
    return slug[:max_length].rstrip("-")


def word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))
