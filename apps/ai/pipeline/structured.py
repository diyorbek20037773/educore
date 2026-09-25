"""Structured upsert (AI_PIPELINE §2.8): Event, Admission, Story, Program, Profession from an extraction."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.postgres.search import TrigramSimilarity
from django.utils import timezone

from apps.ai.schemas import Extraction
from apps.content.models import Admission, AdmissionStatus, Article, Event, Story
from apps.core.text import slugify_uz
from apps.institutions.models import Institution, Profession, Program
from apps.telegram.models import TelegramPost

EVENT_TITLE_SIMILARITY = 0.9


def _unique_slug(model: Any, base: str) -> str:
    base = slugify_uz(base, max_length=120) or "item"
    slug, n = base, 2
    while model.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def _admission_status(starts: Any, ends: Any) -> str:
    today = timezone.localdate()
    if ends and ends < today:
        return AdmissionStatus.CLOSED
    if starts and starts <= today:
        return AdmissionStatus.OPEN
    return AdmissionStatus.ANNOUNCED


def upsert_structured(
    extraction: Extraction, *, institution: Institution | None, article: Article, post: TelegramPost
) -> dict[str, Any]:
    """Create/refresh the structured object matching the content type. Returns ids for the AIRun output."""
    result: dict[str, Any] = {}
    kind = extraction.content_type
    if kind == "event" and extraction.event and extraction.event.starts_at:
        data = extraction.event
        starts = data.starts_at if timezone.is_aware(data.starts_at) else timezone.make_aware(data.starts_at)
        existing = (
            Event.objects.filter(institution=institution, starts_at__date=starts.date())
            .annotate(similarity=TrigramSimilarity("title_uz", data.title))
            .filter(similarity__gte=EVENT_TITLE_SIMILARITY)
            .first()
        )
        event = existing or Event(slug=_unique_slug(Event, data.title), institution=institution)
        event.title_uz = data.title[:300]
        event.starts_at = starts
        event.ends_at = (
            data.ends_at
            if data.ends_at is None or timezone.is_aware(data.ends_at)
            else timezone.make_aware(data.ends_at)
        )
        event.location_uz = (data.location or "")[:300]
        event.is_online = data.is_online
        event.kind = data.kind
        event.article = article
        event.source_post = post
        event.description_uz = article.lead_uz or ""
        event.is_published = starts >= timezone.now() - timedelta(days=7)
        event.needs_verification = True
        event.save()
        result["event"] = event.pk
    elif kind == "admission" and extraction.admission and institution:
        data = extraction.admission
        admission, _ = Admission.objects.update_or_create(
            institution=institution,
            year=data.year,
            title_uz=data.title[:300],
            defaults={
                "title": data.title[:300],
                "starts_at": data.starts_at,
                "ends_at": data.ends_at,
                "requirements_uz": data.requirements or "",
                "documents_uz": data.documents or "",
                "quota": data.quota,
                "apply_url": data.apply_url or "",
                "status": _admission_status(data.starts_at, data.ends_at),
                "source_post": post,
                "article": article,
                "is_published": True,
            },
        )
        result["admission"] = admission.pk
    elif kind == "story" and extraction.story:
        data = extraction.story
        story = Story.objects.filter(source_post=post).first() or Story(
            slug=_unique_slug(Story, article.title_uz or data.person_name)
        )
        story.title_uz = article.title_uz
        story.person_name = data.person_name[:200]
        story.person_role_uz = (data.person_role or "")[:200]
        story.quote_uz = data.quote or ""
        story.body_uz = article.body_uz
        story.institution = institution
        story.article = article
        story.source_post = post
        story.cover_media = article.cover_media
        story.is_published = True
        story.published_at = story.published_at or post.published_at
        story.save()
        result["story"] = story.pk
    if extraction.program and institution:
        slug = slugify_uz(extraction.program.name, max_length=120)
        if slug:
            program, created = Program.objects.get_or_create(
                institution=institution,
                slug=slug,
                defaults={
                    "name": extraction.program.name[:300],
                    "level": extraction.program.level or "bakalavr",
                    "form": "kunduzgi",
                    "is_active": False,
                    "needs_verification": True,
                    "source_url": post.telegram_url,
                },
            )
            result["program"] = {"id": program.pk, "created": created}
    if extraction.profession:
        slug = slugify_uz(extraction.profession.name, max_length=120)
        if slug:
            profession, created = Profession.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": extraction.profession.name[:200],
                    "summary": extraction.profession.summary or "",
                    "is_published": False,
                    "needs_verification": True,
                },
            )
            result["profession"] = {"id": profession.pk, "created": created}
    return result
