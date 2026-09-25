"""Pydantic v2 schemas for every AI input/output (AI_PIPELINE §2.3–2.11).

Length limits on free-text fields truncate at a word boundary (`mode="before"`) instead of rejecting —
LLMs often miss exact character counts. Enums and structure stay strict; a violation triggers one retry
with the error.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from apps.core.seeds.taxonomy import CATEGORIES

CATEGORY_SLUGS: frozenset[str] = frozenset(slug for slug, *_ in CATEGORIES)
ELLIPSIS = "…"


def truncate_words(value: Any, limit: int) -> Any:
    """Cut `value` to at most `limit` characters at a word boundary, appending an ellipsis."""
    if not isinstance(value, str):
        return value
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    cut = value[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,.;:—-") + ELLIPSIS


def _truncated(limit: int) -> Any:
    return Annotated[str, BeforeValidator(lambda v: truncate_words(v, limit)), Field(max_length=limit)]


def _capped_list(limit: int) -> Any:
    return Annotated[list[str], BeforeValidator(lambda v: list(v)[:limit] if isinstance(v, list) else v)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


EventKind = Literal[
    "seminar", "konferensiya", "ochiq_eshiklar", "tanlov", "sport", "madaniy", "uchrashuv", "boshqa"
]
ContentTypeLiteral = Literal[
    "news",
    "event",
    "admission",
    "program",
    "profession",
    "story",
    "announcement",
    "congratulation",
    "advertisement",
    "service",
    "other",
]
RiskFlag = Literal[
    "private_person_pii",
    "minor",
    "graphic",
    "legal_case_named_suspect",
    "political",
    "medical",
    "unverified_number",
    "other",
]


class Person(StrictModel):
    name: str
    role: str | None = None


class EventData(StrictModel):
    title: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    location: str | None = None
    is_online: bool = False
    kind: EventKind = "boshqa"


class AdmissionData(StrictModel):
    year: int
    title: str
    starts_at: date | None = None
    ends_at: date | None = None
    programs: list[str] = Field(default_factory=list)
    requirements: str | None = None
    documents: str | None = None
    quota: int | None = None
    apply_url: str | None = None


class StoryData(StrictModel):
    person_name: str
    person_role: str | None = None
    quote: str | None = None


class ProgramData(StrictModel):
    name: str
    level: str | None = None
    duration_years: float | None = None


class ProfessionData(StrictModel):
    name: str
    summary: str | None = None


class Extraction(StrictModel):
    """Stage 4 — classification and structured data (FAST model)."""

    language: Literal["uz", "uz-cyrl", "ru", "en", "mixed", "other"]
    content_type: ContentTypeLiteral
    category_slug: str
    audience: list[Literal["applicants", "students", "cadets", "staff", "public"]] = Field(
        default_factory=list
    )
    importance: int = Field(ge=1, le=5)
    is_low_value: bool
    low_value_reason: str | None = None
    summary_uz: _truncated(300)  # type: ignore[valid-type]
    tags: _capped_list(8) = Field(default_factory=list)  # type: ignore[valid-type]
    persons: list[Person] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    event: EventData | None = None
    admission: AdmissionData | None = None
    story: StoryData | None = None
    program: ProgramData | None = None
    profession: ProfessionData | None = None

    @field_validator("category_slug")
    @classmethod
    def _known_category(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in CATEGORY_SLUGS:
            raise ValueError(f"category_slug must be one of: {', '.join(sorted(CATEGORY_SLUGS))}")
        return value

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, tags: list[str]) -> list[str]:
        seen: list[str] = []
        for tag in tags:
            clean = tag.strip().lstrip("#").lower()
            if clean and clean not in seen:
                seen.append(clean)
        return seen


class Draft(StrictModel):
    """Stage 7 — the article (MAIN model)."""

    title: _truncated(90)  # type: ignore[valid-type]
    lead: _truncated(220)  # type: ignore[valid-type]
    body_html: str
    seo_title: _truncated(60)  # type: ignore[valid-type]
    seo_description: _truncated(160)  # type: ignore[valid-type]
    tags: _capped_list(6) = Field(default_factory=list)  # type: ignore[valid-type]
    reading_time_min: int = Field(ge=1, le=30)
    confidence: float = Field(ge=0, le=1)
    notes: str | None = None


class FactCheck(StrictModel):
    """Stage 8 — fact guard (FAST model)."""

    verdict: Literal["pass", "fail"]
    unsupported_claims: list[str] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    suggested_fixes: str | None = None


class DedupeVerdict(StrictModel):
    """Stage 6 — is the candidate the same real-world event? (FAST model)."""

    same_event: bool
    confidence: float = Field(ge=0, le=1)
    adds_new_info: bool
    reason: str


class Translation(StrictModel):
    """ru/en translation of a published article (MAIN model); HTML tag sequence must match the source."""

    title: _truncated(120)  # type: ignore[valid-type]
    lead: _truncated(300)  # type: ignore[valid-type]
    body_html: str
    seo_title: _truncated(70)  # type: ignore[valid-type]
    seo_description: _truncated(170)  # type: ignore[valid-type]


class DigestSection(StrictModel):
    institution: str
    body_html: str


class Digest(StrictModel):
    """Weekly "Haftalik sharh" (MAIN model), always sent to review."""

    title: _truncated(90)  # type: ignore[valid-type]
    lead: _truncated(220)  # type: ignore[valid-type]
    sections: list[DigestSection]
    seo_description: _truncated(160)  # type: ignore[valid-type]
