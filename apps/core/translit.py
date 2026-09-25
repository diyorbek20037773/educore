"""Deterministic Uzbek Latin ↔ Cyrillic transliteration (SPEC FR-I18N-5, FR-AI-6).

Rules follow the official alphabets: digraphs `sh ch oʻ gʻ`, `ye yo yu ya`, word-initial `e → э`,
tutuq `ʼ ↔ ъ`,
`ц` as `s` word-initially/after consonants and `ts` after vowels (plus an exceptions list for loanwords).
URLs, e-mails, @mentions and #hashtags are left untouched. HTML-aware helpers change text nodes only.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from apps.core.text import OKINA, TUTUQ, normalize_uzbek_apostrophes

LATIN_VOWELS = set("aeiouAEIOU")
CYR_VOWELS = set("аэиоуеёюяўАЭИОУЕЁЮЯЎ")

# Loanwords that the letter rules cannot derive (`ц`, or `й`+vowel after a vowel); keys are lowercase Latin.
LOANWORDS_TO_CYR: dict[str, str] = {
    "sirk": "цирк",
    "sement": "цемент",
    "sex": "цех",
    "sentner": "центнер",
    "sentr": "центр",
    "stansiya": "станция",
    "konferensiya": "конференция",
    "aksiya": "акция",
    "aksiyadorlik": "акциядорлик",
    "militsiya": "милиция",
    "politsiya": "полиция",
    "prinsip": "принцип",
    "prinsipial": "принципиал",
    "konsert": "концерт",
    "konsepsiya": "концепция",
    "kvitansiya": "квитанция",
    "funksiya": "функция",
    "ofitser": "офицер",
    "litsey": "лицей",
    "tsenzura": "цензура",
    "infeksiya": "инфекция",
    "inspeksiya": "инспекция",
    "leksiya": "лекция",
    "seksiya": "секция",
    "fraksiya": "фракция",
    # `yo`/`ya` after a vowel that is й + vowel in Cyrillic
    "mayor": "майор",
    "rayon": "район",
}

_PROTECTED = re.compile(
    r"(https?://\S+|www\.\S+|[\w.+-]+@[\w-]+\.[\w.-]+|[@#][\wʻʼ]+)",
    re.UNICODE,
)
_LATIN_WORD = re.compile(r"[A-Za-zʻʼ]+")
_CYR_WORD = re.compile(r"[Ѐ-ӿ]+")
_HTML_SPLIT = re.compile(r"(<[^>]+>)")

_L2C_SINGLE = {
    "a": "а", "b": "б", "d": "д", "f": "ф", "g": "г", "h": "ҳ", "i": "и", "j": "ж", "k": "к", "l": "л",
    "m": "м", "n": "н", "o": "о", "p": "п", "q": "қ", "r": "р", "s": "с", "t": "т", "u": "у", "v": "в",
    "x": "х", "y": "й", "z": "з", "c": "с", "w": "в",
}  # fmt: skip
_C2L = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "x", "ш": "sh", "ч": "ch", "ў": "o" + OKINA, "қ": "q", "ғ": "g" + OKINA, "ҳ": "h", "ё": "yo",
    "ю": "yu", "я": "ya", "э": "e", "ъ": TUTUQ, "ь": "", "ы": "i", "щ": "sh",
}  # fmt: skip


def _apply_case(source: str, target: str, whole_word_upper: bool) -> str:
    if not target:
        return target
    if whole_word_upper:
        return target.upper()
    if source[:1].isupper():
        return target[:1].upper() + target[1:]
    return target


def _latin_word_to_cyr(word: str) -> str:
    lower = word.lower()
    upper_word = len(word) > 1 and word.isupper()
    if lower in LOANWORDS_TO_CYR:
        return _apply_case(word, LOANWORDS_TO_CYR[lower], upper_word)
    if lower.endswith("tsiya"):
        stem = _latin_word_to_cyr(word[: -len("tsiya")])
        return stem + _apply_case(word[-5:], "ция", upper_word)
    out: list[str] = []
    i = 0
    n = len(word)
    while i < n:
        ch, lo = word[i], lower[i]
        nxt = lower[i + 1] if i + 1 < n else ""
        prev = lower[i - 1] if i > 0 else ""
        pair = word[i : i + 2]
        if lo in "og" and nxt == OKINA:
            out.append(_apply_case(pair, "ў" if lo == "o" else "ғ", upper_word))
            i += 2
        elif lo == "s" and nxt == "h":
            out.append(_apply_case(pair, "ш", upper_word))
            i += 2
        elif lo == "c" and nxt == "h":
            out.append(_apply_case(pair, "ч", upper_word))
            i += 2
        elif lo == "y" and nxt and nxt in "eoua" and not (nxt == "o" and word[i + 2 : i + 3] == OKINA):
            out.append(_apply_case(pair, {"e": "е", "o": "ё", "u": "ю", "a": "я"}[nxt], upper_word))
            i += 2
        elif lo == "e":
            cyr = "э" if (i == 0 or prev in "aeiou") else "е"
            out.append(_apply_case(ch, cyr, upper_word))
            i += 1
        elif ch == TUTUQ:
            out.append("Ъ" if upper_word else "ъ")
            i += 1
        elif ch == OKINA:  # stray okina not after o/g — keep the sign
            out.append("ъ")
            i += 1
        else:
            out.append(_apply_case(ch, _L2C_SINGLE.get(lo, ch), upper_word))
            i += 1
    return "".join(out)


def _cyr_word_to_latin(word: str) -> str:
    lower = word.lower()
    upper_word = len(word) > 1 and word.isupper()
    out: list[str] = []
    for i, ch in enumerate(word):
        lo = lower[i]
        prev = lower[i - 1] if i > 0 else ""
        if lo == "е":
            lat = "ye" if (i == 0 or prev in CYR_VOWELS or prev in "ъь") else "e"
        elif lo == "ц":
            lat = "ts" if prev and prev in CYR_VOWELS else "s"
        else:
            lat = _C2L.get(lo, ch)
        out.append(_apply_case(ch, lat, upper_word))
    return "".join(out)


def _transliterate(text: str, word_re: re.Pattern[str], convert: Callable[[str], str]) -> str:
    parts = _PROTECTED.split(text)
    for idx, part in enumerate(parts):
        if idx % 2 == 1:  # protected token (URL, e-mail, mention, hashtag)
            continue
        parts[idx] = word_re.sub(lambda m: convert(m.group(0)), part)
    return "".join(parts)


def to_cyrillic(text: str) -> str:
    """Uzbek Latin → Cyrillic. Apostrophe variants are normalized first (oʻ, gʻ, tutuq)."""
    if not text:
        return text
    return _transliterate(normalize_uzbek_apostrophes(text), _LATIN_WORD, _latin_word_to_cyr)


def to_latin(text: str) -> str:
    """Uzbek Cyrillic → Latin (also used to normalize Cyrillic search queries)."""
    if not text:
        return text
    return _transliterate(text, _CYR_WORD, _cyr_word_to_latin)


def _html_text_nodes(html: str, convert: Callable[[str], str]) -> str:
    parts = _HTML_SPLIT.split(html)
    return "".join(part if part.startswith("<") else convert(part) for part in parts)


def html_to_cyrillic(html: str) -> str:
    """Transliterate the text nodes of an HTML fragment; tags and attributes stay unchanged."""
    return _html_text_nodes(html or "", to_cyrillic)


def html_to_latin(html: str) -> str:
    return _html_text_nodes(html or "", to_latin)


def is_mostly_cyrillic(text: str, threshold: float = 0.6) -> bool:
    """True when more than `threshold` of the letters are Cyrillic (script detection, AI_PIPELINE §2.2)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    cyr = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    return cyr / len(letters) > threshold
