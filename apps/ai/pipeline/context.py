"""Everything a pipeline run needs about one post, plus prompt-rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings

from apps.ai.prompts import render
from apps.content.models import Category
from apps.core.sanitize import strip_tags
from apps.core.services.settings import get_setting
from apps.institutions.models import Institution
from apps.telegram.models import TelegramMedia, TelegramPost, TelegramSource


@dataclass
class PostContext:
    post: TelegramPost
    source: TelegramSource
    institution: Institution | None
    media: list[TelegramMedia]
    publish_mode: str
    threshold: float

    @property
    def source_name(self) -> str:
        return self.institution.short_name if self.institution else self.source.title or self.source.username

    @property
    def post_date(self) -> str:
        return self.post.published_at.date().isoformat()


def load_context(post_id: int) -> PostContext:
    post = TelegramPost.objects.select_related("source__institution").get(pk=post_id)
    return PostContext(
        post=post,
        source=post.source,
        institution=post.source.institution,
        media=list(post.media.order_by("order")),
        publish_mode=str(get_setting("publish_mode")),
        threshold=float(get_setting("publish_confidence_threshold")),
    )


def institution_profile(institution: Institution | None) -> str:
    """Trusted context for the system prompt (official names, parent body, short description)."""
    if institution is None:
        return "—"
    lines = [
        f"Qisqa nomi: {institution.short_name}",
        f"Toʻliq rasmiy nomi: {institution.full_name}",
        f"Tasarrufi: {institution.parent_body or '—'}",
        f"Veb-sayt: {institution.website_url or '—'}",
        f"Tavsif: {strip_tags(institution.description)[:600] or '—'}",
    ]
    return "\n".join(lines)


def categories_line() -> str:
    return "; ".join(f"{c.slug}: {c.name}" for c in Category.objects.filter(is_active=True).order_by("order"))


def system_prompt(ctx: PostContext) -> str:
    full_name = ctx.institution.full_name if ctx.institution else ctx.source_name
    return render(
        "system_editor",
        institution_full_name=full_name,
        institution_profile=institution_profile(ctx.institution),
        categories=categories_line(),
    )


def base_prompt_context(ctx: PostContext, source_text: str, media_descriptors: str) -> dict[str, Any]:
    return {
        "source_name": ctx.source_name,
        "source_username": f"@{ctx.source.username}",
        "post_date": ctx.post_date,
        "telegram_url": ctx.post.telegram_url,
        "source_text": source_text,
        "media_descriptors": media_descriptors,
    }


def models() -> tuple[str, str]:
    """(MAIN, FAST) model ids — only ever from settings/env (AI_PIPELINE §1)."""
    return settings.AI_MODEL, settings.AI_MODEL_FAST
