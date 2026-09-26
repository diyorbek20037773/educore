"""Write pipeline results into `content.Article` (+ sources, media, tags, uz-cyrl) — AI_PIPELINE §2.9–2.10."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any

import structlog
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.ai.pipeline.context import SKIP_TRANSLATIONS, PostContext
from apps.ai.pipeline.rules import Decision, MediaSelection, article_content_type
from apps.ai.schemas import Draft, Extraction, FactCheck
from apps.content.models import Article, ArticleMedia, ArticleSource, ArticleStatus, Category, Tag
from apps.core.cache import bump_content_version
from apps.core.sanitize import sanitize_html, strip_tags
from apps.core.services.settings import get_setting
from apps.core.text import slugify_uz
from apps.core.translit import html_to_cyrillic, to_cyrillic
from apps.telegram.models import TelegramPost

log = structlog.get_logger(__name__)
TRANSLATED_FIELDS = ("title", "lead", "seo_title", "seo_description")


def make_slug(title: str, seed: str) -> str:
    """`<uz title slug>-<6-char hash>` (SPEC §2.6), unique."""
    base = slugify_uz(title, max_length=100) or "maqola"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    for i in range(0, 58, 6):
        slug = f"{base}-{digest[i : i + 6]}"
        if not Article.objects.filter(slug=slug).exists():
            return slug
    return f"{base}-{digest[:12]}"


def unique_title(title: str, institution_name: str, exclude_pk: int | None = None) -> str:
    """Duplicate titles within 7 days get the institution as a suffix (AI_PIPELINE §4)."""
    recent = Article.objects.filter(title_uz=title, created_at__gte=timezone.now() - timedelta(days=7))
    if exclude_pk:
        recent = recent.exclude(pk=exclude_pk)
    if recent.exists() and institution_name and institution_name not in title:
        return f"{title} ({institution_name})"[:200]
    return title


def set_tags(article: Article, names: list[str]) -> None:
    tags = []
    for name in names[:6]:
        slug = slugify_uz(name, max_length=80)
        if not slug:
            continue
        tag, created = Tag.objects.get_or_create(slug=slug, defaults={"name": name.strip()[:100]})
        if created or not article.tags.filter(pk=tag.pk).exists():
            Tag.objects.filter(pk=tag.pk).update(usage_count=F("usage_count") + 1)
        tags.append(tag)
    article.tags.set(tags)


def transliterate(article: Article) -> None:
    """uz-cyrl copy by deterministic transliteration — never AI (FR-AI-6)."""
    for name in TRANSLATED_FIELDS:
        setattr(article, f"{name}_uz_cyrl", to_cyrillic(getattr(article, f"{name}_uz") or ""))
    article.body_uz_cyrl = html_to_cyrillic(article.body_uz or "")
    status = dict(article.translation_status or {})
    status["uz-cyrl"] = "done"
    article.translation_status = status


def attach_media(article: Article, selection: MediaSelection, alt: str) -> None:
    article.gallery.all().delete()
    rows = [
        ArticleMedia(article=article, media=m, order=i, caption=alt, is_cover=m is selection.cover)
        for i, m in enumerate([m for m in [selection.cover, *selection.gallery] if m is not None])
    ]
    ArticleMedia.objects.bulk_create(rows)


def add_source(article: Article, post: TelegramPost, *, primary: bool) -> None:
    ArticleSource.objects.update_or_create(
        post=post,
        defaults={"article": article, "institution": post.source.institution, "is_primary": primary},
    )
    if post.source.institution_id:
        article.institutions.add(post.source.institution_id)


@transaction.atomic
def write_article(
    ctx: PostContext,
    *,
    article: Article | None,
    extraction: Extraction,
    draft: Draft,
    factcheck: FactCheck,
    decision: Decision,
    selection: MediaSelection,
    cluster_id: int | None,
    extra_meta: dict[str, Any],
    ai_generated: bool = True,
) -> Article:
    """Create the article for a post or update (regenerate) an existing one; history records every save."""
    created = article is None
    institution_name = ctx.institution.short_name if ctx.institution else ""
    category = Category.objects.get(slug=extraction.category_slug)
    article = article or Article(cluster_id=cluster_id)
    article.ai_generated = ai_generated
    title = unique_title(draft.title, institution_name, exclude_pk=article.pk)
    article.title_uz = title
    article.lead_uz = draft.lead
    article.body_uz = sanitize_html(draft.body_html)
    article.seo_title_uz = draft.seo_title
    article.seo_description_uz = draft.seo_description
    article.content_type = article_content_type(extraction.content_type)
    article.importance = extraction.importance
    article.category = category
    article.primary_institution = article.primary_institution or ctx.institution
    article.reading_time_min = draft.reading_time_min
    article.ai_confidence = draft.confidence
    article.source_published_at = article.source_published_at or ctx.post.published_at
    meta = dict(article.ai_meta or {})
    hashes = dict(meta.get("source_hashes", {}))
    hashes[str(ctx.post.pk)] = ctx.post.content_hash
    meta.update(
        extra_meta,
        source_hashes=hashes,
        extracted_content_type=extraction.content_type,
        notes=draft.notes,
        risk_flags=list(factcheck.risk_flags),
        unsupported_claims=list(factcheck.unsupported_claims),
    )
    article.ai_meta = meta
    if created:
        article.slug = make_slug(title, f"{ctx.post.pk}:{ctx.post.content_hash}")
    else:
        article.edited_at = timezone.now()
        article.needs_refresh = False
    # A regenerated text is re-gated like a new one; archived/rejected articles keep the editor's decision.
    if created or article.status not in (ArticleStatus.ARCHIVED, ArticleStatus.REJECTED):
        article.status = decision.status
        article.review_reason = "" if decision.status == ArticleStatus.PUBLISHED else decision.reason
        if decision.status == ArticleStatus.PUBLISHED:
            article.published_at = article.published_at or ctx.post.published_at
    article.cover_media = selection.cover
    transliterate(article)
    article.save()
    set_tags(article, [*draft.tags, *extraction.tags][:6])
    attach_media(article, selection, alt=f"{institution_name}: {title}".strip(": "))
    add_source(article, ctx.post, primary=created or not article.sources.filter(is_primary=True).exists())
    transaction.on_commit(lambda: after_save(article.pk))
    log.info(
        "article_written",
        article_id=article.pk,
        post_id=ctx.post.pk,
        created=created,
        status=article.status,
        reason=decision.reason,
    )
    return article


def after_save(article_id: int) -> None:
    """Post-publish side effects: cache/sitemap bump, ru/en translations, review alert (§2 stage 12)."""
    bump_content_version()
    article = Article.objects.filter(pk=article_id).first()
    if article is None:
        return
    ai_mode = settings.CONTENT_MODE == "ai"
    if article.status == ArticleStatus.PUBLISHED and ai_mode and not SKIP_TRANSLATIONS.get():
        from config.celery import app

        status = article.translation_status or {}
        for lang in get_setting("ai_translate_to") or []:
            if status.get(lang) == "manual":
                continue
            try:
                app.send_task("ai.translate_article", args=[article_id, lang], queue="ai")
            except Exception:
                log.warning("translate_enqueue_failed", article_id=article_id, lang=lang)
    elif article.status == ArticleStatus.REVIEW and article.importance >= 4:
        from apps.ops.services.alerts import send_alert

        send_alert(
            "article_review_important",
            f"review:{article_id}",
            f"Muhim maqola koʻrikda: «{article.title_uz}» ({article.review_reason}).",
        )


@transaction.atomic
def archive_for_deleted_post(post: TelegramPost) -> Article | None:
    """Source deletion archives the article when `on_source_delete=archive` and no live source remains."""
    source = ArticleSource.objects.select_related("article").filter(post=post).first()
    if source is None:
        return None
    article = source.article
    live = article.sources.exclude(post__is_deleted=True).exists()
    if get_setting("on_source_delete") == "archive" and not live:
        article.status = ArticleStatus.ARCHIVED
        article.save(update_fields=["status", "updated_at"])
        transaction.on_commit(bump_content_version)
    return article


def source_texts(article: Article) -> list[tuple[str, str]]:
    """(institution name, plain text) of every live source — for multi-source regeneration."""
    rows = article.sources.select_related("post__source__institution").exclude(post__is_deleted=True)
    return [
        (
            s.post.source.institution.short_name if s.post.source.institution else s.post.source.username,
            strip_tags(s.post.text),
        )
        for s in rows
    ]
