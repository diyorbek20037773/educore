"""Deterministic offline provider (`AI_PROVIDER=mock`) for dev, tests and `seed_demo` (AI_PIPELINE §1).

Outputs are derived from the prompt text so every schema field is exercised. Test markers inside the source
text: `[[mock:500]]` → transient error, `[[mock:400]]` → permanent error, `[[mock:fail]]` → fact-guard fail,
`[[mock:risk]]` → risk flag, `[[mock:invalid]]` → invalid JSON once, `[[mock:lowconf]]` → confidence 0.4.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ValidationError

from apps.ai.providers.base import (
    JSONResult,
    ProviderPermanentError,
    ProviderTransientError,
    SchemaValidationError,
    TextResult,
)

_QUOTED = re.compile(r'"""(.*?)"""', re.S)
_DATE = re.compile(r"sana: (\d{4}-\d{2}-\d{2})")
_LANG = re.compile(r"TIL: (\w+)")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_HASHTAG = re.compile(r"#([\wʻʼ]+)")
_URL = re.compile(r"https?://\S+")

CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("qabul", ("qabul", "abituriyent", "kvota")),
    ("tadbirlar", ("tadbir", "konferensiya", "seminar", "ochiq eshiklar", "uchrashuv")),
    ("sport", ("sport", "musobaqa", "chempionat", "turnir")),
    ("xalqaro-hamkorlik", ("xalqaro", "hamkorlik", "delegatsiya", "memorandum")),
    ("ilm-fan", ("ilmiy", "dissertatsiya", "tadqiqot", "monografiya")),
    ("tabriklar", ("tabrik", "bayram", "muborak")),
    ("elonlar", ("eʼlon", "e'lon", "diqqat")),
    ("rahbariyat", ("rahbar", "tashrif", "vazir")),
    ("manaviyat", ("maʼnaviy", "madaniy", "adabiy")),
    ("motivatsiya", ("ilhom", "orzu", "muvaffaqiyat hikoyasi")),
    ("kursantlar", ("kursant",)),
    ("talabalar", ("talaba",)),
    ("kasblar", ("kasb",)),
    ("talim", ("taʼlim", "dars", "oʻquv", "mashgʻulot")),
]


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _first(text: str, n: int = 1) -> str:
    parts = [p.strip() for p in _SENTENCE.split(_URL.sub("", text).strip()) if p.strip()]
    return " ".join(parts[:n]) if parts else text.strip()


def _category(text: str) -> str:
    low = text.lower()
    for slug, words in CATEGORY_KEYWORDS:
        if any(w in low for w in words):
            return slug
    return "yangiliklar"


def _content_type(text: str, category: str) -> str:
    low = text.lower()
    if category == "tabriklar":
        return "congratulation"
    if "reklama" in low or "chegirma" in low:
        return "advertisement"
    return {
        "qabul": "admission",
        "tadbirlar": "event",
        "motivatsiya": "story",
        "elonlar": "announcement",
    }.get(category, "news")


def _post_date(prompt: str) -> date:
    match = _DATE.search(prompt)
    return date.fromisoformat(match.group(1)) if match else date(2026, 9, 1)


def _source(prompt: str, index: int = 0) -> str:
    blocks = _QUOTED.findall(prompt)
    return blocks[index].strip() if len(blocks) > index else prompt


def _paragraphs(text: str) -> str:
    sentences = [s.strip() for s in _SENTENCE.split(_URL.sub("", text).strip()) if s.strip()]
    chunks = [" ".join(sentences[i : i + 2]) for i in range(0, len(sentences), 2)] or [text.strip()]
    return "".join(f"<p>{c}</p>" for c in chunks)


def _translate_html(html: str, lang: str) -> str:
    return re.sub(r">([^<>]+)<", lambda m: f">[{lang}] {m.group(1)}<", html)


class MockProvider:
    name = "mock"

    def __init__(self) -> None:
        self.invalid_served: set[str] = set()

    # --- builders per schema ---------------------------------------------------------------------
    def _extraction(self, prompt: str) -> dict[str, Any]:
        text = _source(prompt)
        category = _category(text)
        content_type = _content_type(text, category)
        words = len(text.split())
        post_day = _post_date(prompt)
        data: dict[str, Any] = {
            "language": "uz-cyrl" if sum("Ѐ" <= c <= "ӿ" for c in text) > len(text) / 3 else "uz",
            "content_type": content_type,
            "category_slug": category,
            "audience": ["applicants", "public"] if category == "qabul" else ["public"],
            "importance": 1 if content_type == "congratulation" else 4 if category == "qabul" else 3,
            "is_low_value": words < 12 or content_type == "advertisement",
            "low_value_reason": "short" if words < 12 else None,
            "summary_uz": _first(text),
            "tags": [t.lower() for t in _HASHTAG.findall(text)][:5] + [category],
            "persons": [{"name": "Mock Shaxs", "role": "rahbar"}] if "rahbar" in text.lower() else [],
            "organizations": ["EDUCORE"],
            "places": ["Toshkent"] if "toshkent" in text.lower() else [],
            "dates": [post_day.isoformat()],
            "event": None,
            "admission": None,
            "story": None,
            "program": None,
            "profession": None,
        }
        if content_type == "event":
            start = datetime.combine(post_day + timedelta(days=5), datetime.min.time()).replace(hour=10)
            data["event"] = {
                "title": _first(text)[:120],
                "starts_at": start.isoformat(),
                "ends_at": None,
                "location": "Toshkent",
                "is_online": False,
                "kind": "ochiq_eshiklar" if "ochiq eshiklar" in text.lower() else "seminar",
            }
        if content_type == "admission":
            data["admission"] = {
                "year": post_day.year,
                "title": _first(text)[:120],
                "starts_at": post_day.isoformat(),
                "ends_at": (post_day + timedelta(days=30)).isoformat(),
                "programs": [],
                "requirements": None,
                "documents": None,
                "quota": None,
                "apply_url": None,
            }
        if content_type == "story":
            data["story"] = {"person_name": "Mock Qahramon", "person_role": "kursant", "quote": _first(text)}
        return data

    def _draft(self, prompt: str) -> dict[str, Any]:
        text = _source(prompt)
        title = _first(text)
        confidence = 0.4 if "[[mock:lowconf]]" in prompt else 0.9
        body = _paragraphs(text.replace("[[mock:fail]]", "").replace("[[mock:risk]]", ""))
        return {
            "title": title,
            "lead": _first(text, 2),
            "body_html": body,
            "seo_title": title,
            "seo_description": _first(text, 2),
            "tags": [t.lower() for t in _HASHTAG.findall(text)][:6],
            "reading_time_min": max(1, len(text.split()) // 180 + 1),
            "confidence": confidence,
            "notes": None,
        }

    def _fact_check(self, prompt: str) -> dict[str, Any]:
        fail = "[[mock:fail]]" in prompt and "QAYTA" not in prompt  # regeneration feedback clears the failure
        return {
            "verdict": "fail" if fail else "pass",
            "unsupported_claims": ["Manbada yoʻq raqam."] if fail else [],
            "risk_flags": ["unverified_number"] if "[[mock:risk]]" in prompt else [],
            "suggested_fixes": None,
        }

    def _dedupe(self, prompt: str) -> dict[str, Any]:
        a, b = set(_source(prompt, 0).lower().split()), set(_source(prompt, 1).lower().split())
        jaccard = len(a & b) / max(1, len(a | b))
        return {
            "same_event": jaccard >= 0.5,
            "confidence": round(min(1.0, 0.5 + jaccard / 2), 2),
            "adds_new_info": 0.5 <= jaccard < 0.95,
            "reason": f"mock jaccard {jaccard:.2f}",
        }

    def _translation(self, prompt: str) -> dict[str, Any]:
        match = _LANG.search(prompt)
        lang = match.group(1) if match else "en"
        title, lead, body = (_source(prompt, i) for i in range(3))
        return {
            "title": f"[{lang}] {title}",
            "lead": f"[{lang}] {lead}",
            "body_html": _translate_html(body, lang),
            "seo_title": f"[{lang}] {title}"[:70],
            "seo_description": f"[{lang}] {lead}"[:170],
        }

    def _digest(self, prompt: str) -> dict[str, Any]:
        blocks = [b.strip() for b in _QUOTED.findall(prompt)]
        sections = [
            {"institution": b.splitlines()[0][:80], "body_html": _paragraphs(" ".join(b.splitlines()[1:]))}
            for b in blocks
            if b
        ]
        return {
            "title": "Haftalik sharh",
            "lead": "Muassasalar faoliyatining haftalik sharhi.",
            "sections": sections or [{"institution": "EDUCORE", "body_html": "<p>—</p>"}],
            "seo_description": "Haftalik sharh",
        }

    # --- protocol --------------------------------------------------------------------------------
    def _guard(self, prompt: str) -> None:
        if "[[mock:500]]" in prompt:
            raise ProviderTransientError("mock 500")
        if "[[mock:400]]" in prompt:
            raise ProviderPermanentError("mock 400")

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[BaseModel],
        max_tokens: int,
        timeout: float = 60.0,
    ) -> JSONResult:
        self._guard(user)
        builders = {
            "Extraction": self._extraction,
            "Draft": self._draft,
            "FactCheck": self._fact_check,
            "DedupeVerdict": self._dedupe,
            "Translation": self._translation,
            "Digest": self._digest,
        }
        builder = builders.get(schema.__name__)
        if builder is None:
            raise ProviderPermanentError(f"mock has no builder for {schema.__name__}")
        key = hashlib.sha256(user.encode()).hexdigest()
        if "[[mock:invalid]]" in user and key not in self.invalid_served and "XATO" not in user:
            self.invalid_served.add(key)
            raise SchemaValidationError("mock invalid JSON", "{not json", _tokens(system + user), 5)
        data = builder(user)
        raw = json.dumps(data, ensure_ascii=False, default=str)
        try:
            parsed = schema.model_validate(data)
        except ValidationError as exc:  # pragma: no cover - builders must produce valid data
            raise SchemaValidationError(str(exc), raw) from exc
        return JSONResult(
            parsed.model_dump(mode="json"),
            parsed,
            _tokens(system + user),
            _tokens(raw),
            f"mock-{key[:12]}",
            raw,
        )

    def complete_text(
        self, *, model: str, system: str, user: str, max_tokens: int, timeout: float = 60.0
    ) -> TextResult:
        self._guard(user)
        text = _first(_source(user), 3)
        return TextResult(text, _tokens(system + user), _tokens(text), "mock-text")
