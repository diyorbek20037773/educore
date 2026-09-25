"""ru/en AI translations (FR-AI-6, AI_PIPELINE §2.10) and the weekly digest (§2.11)."""

from __future__ import annotations

import re
from datetime import date, timedelta

import structlog
from django.db import transaction
from django.utils import timezone

from apps.ai.pipeline.articles import make_slug, transliterate
from apps.ai.pipeline.context import models
from apps.ai.prompts import prompt_version, render
from apps.ai.providers import ProviderPermanentError
from apps.ai.runs import call_llm
from apps.ai.schemas import Digest, Translation
from apps.content.models import Article, ArticleStatus, Category, ContentType
from apps.core.cache import bump_content_version
from apps.core.sanitize import sanitize_html
from apps.institutions.models import Institution

log = structlog.get_logger(__name__)
LANGUAGE_NAMES = {"ru": "rus", "en": "ingliz"}
_TAG = re.compile(r"</?([a-zA-Z0-9]+)")
DIGEST_MAX_ARTICLES = 60
TRANSLATE_MAX_TOKENS = 16000
DIGEST_SYSTEM = (
    "Siz EDUCORE platformasining tahliliy sharhlovchisisiz. Faqat berilgan maʼlumotlarga tayaning."
)


def tag_sequence(html: str) -> list[str]:
    """Opening/closing tag names in order — translations must preserve it exactly."""
    return [m.group(0).lower() for m in _TAG.finditer(html or "")]


def translate_article(article_id: int, lang: str) -> str:
    """Translate one published article into `lang`; returns the resulting translation status."""
    article = Article.objects.select_related("primary_institution").get(pk=article_id)
    status = dict(article.translation_status or {})
    if lang not in LANGUAGE_NAMES:
        raise ValueError(f"unsupported language {lang!r}")
    if status.get(lang) == "manual":
        return "manual"
    main, _ = models()
    names = ", ".join(Institution.objects.order_by("order").values_list("full_name", flat=True))
    feedback_extra = ""
    for attempt in (1, 2):
        translation, _ = call_llm(
            stage="translate",
            model=main,
            system="Siz rasmiy matnlarni aniq tarjima qiluvchi professional tarjimonsiz.",
            render_user=lambda fb, extra=feedback_extra: render(
                "translate",
                language=lang,
                language_name=LANGUAGE_NAMES[lang],
                institution_names=names,
                title=article.title_uz,
                lead=article.lead_uz,
                body_html=article.body_uz,
                validation_feedback=(fb + "\n" + extra).strip(),
            ),
            schema=Translation,
            max_tokens=TRANSLATE_MAX_TOKENS,
            article_id=article.pk,
        )
        if tag_sequence(translation.body_html) == tag_sequence(article.body_uz):
            break
        if attempt == 2:
            status[lang] = "failed"
            Article.objects.filter(pk=article.pk).update(translation_status=status)
            log.warning("translation_structure_mismatch", article_id=article_id, lang=lang)
            return "failed"
        feedback_extra = "XATO: HTML teglar ketma-ketligi asl matndagidan farq qildi. Teglarni aynan saqlang."
    suffix = lang.replace("-", "_")
    setattr(article, f"title_{suffix}", translation.title)
    setattr(article, f"lead_{suffix}", translation.lead)
    setattr(article, f"body_{suffix}", sanitize_html(translation.body_html))
    setattr(article, f"seo_title_{suffix}", translation.seo_title)
    setattr(article, f"seo_description_{suffix}", translation.seo_description)
    status[lang] = "done"
    article.translation_status = status
    article.save()
    transaction.on_commit(bump_content_version)
    return "done"


def mark_translation_failed(article_id: int, lang: str) -> None:
    article = Article.objects.filter(pk=article_id).first()
    if article is None:
        return
    status = dict(article.translation_status or {})
    if status.get(lang) != "manual":
        status[lang] = "failed"
        Article.objects.filter(pk=article_id).update(translation_status=status)


def _format_uz_date(value: date) -> str:
    months = [
        "yanvar",
        "fevral",
        "mart",
        "aprel",
        "may",
        "iyun",
        "iyul",
        "avgust",
        "sentabr",
        "oktabr",
        "noyabr",
        "dekabr",
    ]
    return f"{value.day}-{months[value.month - 1]}"


def weekly_digest(today: date | None = None) -> Article | None:
    """ "Haftalik sharh" for the previous Monday–Sunday, always to review (FR-AI-8)."""
    today = today or timezone.localdate()
    end = today - timedelta(days=today.weekday() + 1)  # last Sunday
    start = end - timedelta(days=6)
    date_range = f"{_format_uz_date(start)} – {_format_uz_date(end)}, {end.year}-yil"
    week = (
        Article.objects.published()
        .filter(published_at__date__gte=start, published_at__date__lte=end)
        .exclude(content_type__in=[ContentType.ANALYSIS, ContentType.DIGEST])
        .select_related("primary_institution")
        .order_by("primary_institution__order", "-published_at")[:DIGEST_MAX_ARTICLES]
    )
    grouped: dict[str, list[str]] = {}
    for a in week:
        name = a.primary_institution.short_name if a.primary_institution else "EDUCORE"
        grouped.setdefault(name, []).append(f"- {a.title_uz}: {a.lead_uz}")
    if not grouped:
        log.info("weekly_digest_skipped", reason="no articles", start=str(start), end=str(end))
        return None
    blocks = "\n".join(f'"""{name}\n' + "\n".join(lines) + '\n"""' for name, lines in grouped.items())
    main, _ = models()
    digest, _ = call_llm(
        stage="digest",
        model=main,
        system=DIGEST_SYSTEM,
        render_user=lambda fb: render(
            "digest", date_range=date_range, institution_blocks=blocks, validation_feedback=fb
        ),
        schema=Digest,
        max_tokens=TRANSLATE_MAX_TOKENS,
    )
    body = "".join(f"<h2>{s.institution}</h2>{s.body_html}" for s in digest.sections)
    title = f"Haftalik sharh: {date_range}"[:200]
    with transaction.atomic():
        article = Article(
            slug=make_slug(title, f"digest:{start.isoformat()}"),
            title_uz=title,
            lead_uz=digest.lead,
            body_uz=sanitize_html(body),
            seo_title_uz=title[:70],
            seo_description_uz=digest.seo_description,
            content_type=ContentType.DIGEST,
            category=Category.objects.get(slug="maqolalar"),
            status=ArticleStatus.REVIEW,
            review_reason="weekly_digest",
            ai_generated=True,
            importance=3,
            reading_time_min=max(1, len(body.split()) // 180 + 1),
            ai_meta={"prompt_version": prompt_version(), "week": [start.isoformat(), end.isoformat()]},
        )
        transliterate(article)
        article.save()
        article.institutions.set(Institution.objects.filter(short_name__in=list(grouped)))
    return article


def ensure_translatable(article: Article) -> None:
    if article.status != ArticleStatus.PUBLISHED:
        raise ProviderPermanentError("only published articles are translated")
