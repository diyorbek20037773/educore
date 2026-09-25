"""`ai.process_post` stage orchestration (AI_PIPELINE §2); each stage writes an `AIRun`."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import structlog
from django.db import transaction
from django.utils import timezone

from apps.ai.embeddings import get_embedder
from apps.ai.models import EventCluster, Provider
from apps.ai.pipeline import articles, dedupe, rules
from apps.ai.pipeline.context import PostContext, base_prompt_context, load_context, models, system_prompt
from apps.ai.pipeline.structured import upsert_structured
from apps.ai.prompts import prompt_version, render
from apps.ai.runs import call_llm, log_rule_run
from apps.ai.schemas import DedupeVerdict, Draft, Extraction, FactCheck
from apps.content.models import Article, ArticleSource, Category
from apps.core.sanitize import strip_tags
from apps.telegram.models import OutboxEventType, ProcessingStatus, TelegramPost, TelegramSource

log = structlog.get_logger(__name__)

MAX_TOKENS = {"extract": 6000, "generate": 16000, "fact_guard": 6000, "dedupe": 3000}


@dataclass(frozen=True)
class Outcome:
    status: str  # published | review | draft | skipped | merged | archived | noop
    article_id: int | None = None
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "article_id": self.article_id, "detail": self.detail}


def _set_status(post: TelegramPost, status: str, **extra: Any) -> None:
    fields = {"processing_status": status, "updated_at": timezone.now(), **extra}
    if status in (ProcessingStatus.PROCESSED, ProcessingStatus.SKIPPED):
        fields["processed_at"] = timezone.now()
    TelegramPost.objects.filter(pk=post.pk).update(**fields)


def _institution_usernames() -> set[str]:
    return {u.lower() for u in TelegramSource.objects.values_list("username", flat=True)}


def _already_done(article: Article | None, post: TelegramPost) -> bool:
    if article is None:
        return False
    meta = article.ai_meta or {}
    return (
        meta.get("source_hashes", {}).get(str(post.pk)) == post.content_hash
        and meta.get("prompt_version") == prompt_version()
    )


def _additional_sources_block(article: Article | None, post: TelegramPost) -> str:
    if article is None:
        return ""
    others = [
        (name, text)
        for name, text in articles.source_texts(article)
        if text and text != strip_tags(post.text)
    ]
    if not others:
        return ""
    blocks = "\n".join(f'QOʻSHIMCHA MANBA — {name}:\n"""\n{text}\n"""' for name, text in others)
    return (
        "Bu voqea haqida boshqa muassasalar ham xabar bergan. Barcha manbalarni birlashtirib, "
        f"xabar bergan har bir muassasani tilga olgan bitta maqola yozing.\n{blocks}"
    )


def generate_and_check(
    ctx: PostContext,
    system: str,
    base: dict[str, Any],
    extraction: Extraction,
    norm: rules.Normalized,
    *,
    additional_block: str = "",
    stage: str = "generate",
    article_id: int | None = None,
) -> tuple[Draft, FactCheck]:
    """Generate → fact-guard; one regeneration with the unsupported claims fed back (AI_PIPELINE §2.6)."""
    main, fast = models()
    category_name = (
        Category.objects.filter(slug=extraction.category_slug).values_list("name", flat=True).first()
    )
    entities = extraction.model_dump(
        mode="json", include={"persons", "organizations", "places", "dates", "event", "admission", "story"}
    )
    regen = ""
    draft: Draft | None = None
    factcheck: FactCheck | None = None
    for round_no in (1, 2):
        draft, _ = call_llm(
            stage=stage if round_no == 1 else "regenerate",
            model=main,
            system=system,
            render_user=lambda fb, regen=regen: render(
                "generate",
                **base,
                category_name=category_name or extraction.category_slug,
                content_type=extraction.content_type,
                audience=", ".join(extraction.audience) or "public",
                entities_json=json.dumps(entities, ensure_ascii=False),
                length_policy=rules.length_policy(norm.word_count),
                regeneration_feedback=regen,
                validation_feedback=fb,
                additional_sources_block=additional_block,
            ),
            schema=Draft,
            max_tokens=MAX_TOKENS["generate"],
            post_id=ctx.post.pk,
            article_id=article_id,
        )
        draft_text = f"{draft.title}\n{draft.lead}\n{strip_tags(draft.body_html)}"
        factcheck, _ = call_llm(
            stage="fact_guard",
            model=fast,
            system=system,
            render_user=lambda fb, draft_text=draft_text: render(
                "fact_guard", source_text=base["source_text"], draft_text=draft_text, validation_feedback=fb
            ),
            schema=FactCheck,
            max_tokens=MAX_TOKENS["fact_guard"],
            post_id=ctx.post.pk,
            article_id=article_id,
        )
        if factcheck.verdict == "pass" or round_no == 2:
            break
        regen = (
            "QAYTA YOZING: fakt tekshiruvi quyidagi daʼvolarni manbada topmadi — ularni olib tashlang yoki "
            "manbadagi shaklga keltiring: " + "; ".join(factcheck.unsupported_claims)
        )
    assert draft is not None and factcheck is not None
    return draft, factcheck


def _extract(ctx: PostContext, system: str, base: dict[str, Any]) -> Extraction:
    _, fast = models()
    extraction, _ = call_llm(
        stage="extract",
        model=fast,
        system=system,
        render_user=lambda fb: render("extract", **base, validation_feedback=fb),
        schema=Extraction,
        max_tokens=MAX_TOKENS["extract"],
        post_id=ctx.post.pk,
    )
    return extraction


def _confirm_duplicate(ctx: PostContext, system: str, candidate: dedupe.Candidate) -> DedupeVerdict | None:
    canonical = Article.objects.filter(pk=candidate.article_id).first()
    other = TelegramPost.objects.select_related("source__institution").filter(pk=candidate.post_id).first()
    if canonical is None or other is None:
        return None
    _, fast = models()
    verdict, _ = call_llm(
        stage="dedupe",
        model=fast,
        system=system,
        render_user=lambda fb: render(
            "dedupe_confirm",
            existing_source=other.source.institution.short_name
            if other.source.institution
            else other.source.username,
            existing_text=strip_tags(other.text),
            new_source=ctx.source_name,
            new_text=strip_tags(ctx.post.text),
            validation_feedback=fb,
        ),
        schema=DedupeVerdict,
        max_tokens=MAX_TOKENS["dedupe"],
        post_id=ctx.post.pk,
    )
    return verdict


def process(post_id: int, event_type: str = OutboxEventType.CREATED, *, force: bool = False) -> Outcome:
    """Run the pipeline for one post. Raises provider/budget errors for the task layer to handle."""
    ctx = load_context(post_id)
    post = ctx.post
    if event_type == OutboxEventType.DELETED or post.is_deleted:
        article = articles.archive_for_deleted_post(post)
        _set_status(post, ProcessingStatus.PROCESSED)
        return Outcome("archived", article.pk if article else None)

    source_row = ArticleSource.objects.select_related("article").filter(post=post).first()
    article = source_row.article if source_row else None
    if not force and _already_done(article, post):
        _set_status(post, ProcessingStatus.PROCESSED)
        return Outcome("noop", article.pk if article else None)
    _set_status(post, ProcessingStatus.PROCESSING)

    started = time.monotonic()
    reason = rules.triage(post, ctx.media, _institution_usernames())
    log_rule_run("triage", {"skip": reason}, post_id=post.pk, started=started)
    if reason and not force:
        _set_status(post, ProcessingStatus.SKIPPED, skip_reason=reason)
        return Outcome("skipped", None, reason)

    started = time.monotonic()
    norm = rules.normalize(post, ctx.media, list(ctx.source.signature_patterns or []))
    log_rule_run(
        "normalize",
        {"script": norm.script, "words": norm.word_count, "media": norm.media_descriptors},
        post_id=post.pk,
        started=started,
    )
    system = system_prompt(ctx)
    base = base_prompt_context(ctx, norm.source_text, norm.media_descriptors)
    extraction = _extract(ctx, system, base)

    started = time.monotonic()
    vector = get_embedder().embed(norm.source_text)
    TelegramPost.objects.filter(pk=post.pk).update(
        embedding=vector, language=extraction.language, importance=extraction.importance
    )
    log_rule_run(
        "embed",
        {"dimensions": len(vector), "backend": get_embedder().name},
        post_id=post.pk,
        provider=Provider.LOCAL,
        started=started,
    )

    cluster_id = post.cluster_id
    if article is None:
        candidates = dedupe.find_candidates(post, vector)
        for candidate in candidates:
            if candidate.article_id is None or candidate.cluster_id is None:
                continue
            verdict = _confirm_duplicate(ctx, system, candidate)
            if verdict and verdict.same_event and verdict.confidence >= dedupe.CONFIRM_MIN_CONFIDENCE:
                return _merge(ctx, system, extraction, norm, candidate, verdict)
        log_rule_run(
            "dedupe", {"candidates": [c.__dict__ for c in candidates], "merged": False}, post_id=post.pk
        )
        cluster = dedupe.new_cluster(post, vector, extraction.summary_uz)
        cluster_id = cluster.pk

    additional = _additional_sources_block(article, post)
    draft, factcheck = generate_and_check(
        ctx,
        system,
        base,
        extraction,
        norm,
        additional_block=additional,
        article_id=article.pk if article else None,
    )
    return _finish(ctx, extraction, draft, factcheck, article, cluster_id)


def _finish(
    ctx: PostContext,
    extraction: Extraction,
    draft: Draft,
    factcheck: FactCheck,
    article: Article | None,
    cluster_id: int | None,
) -> Outcome:
    post = ctx.post
    selection = rules.select_media(ctx.media)
    log_rule_run("media_select", selection.as_output(), post_id=post.pk)
    decision = rules.decide(
        draft, extraction, factcheck, publish_mode=ctx.publish_mode, threshold=ctx.threshold
    )
    log_rule_run("publish_policy", {"status": decision.status, "reason": decision.reason}, post_id=post.pk)
    with transaction.atomic():
        article = articles.write_article(
            ctx,
            article=article,
            extraction=extraction,
            draft=draft,
            factcheck=factcheck,
            decision=decision,
            selection=selection,
            cluster_id=cluster_id,
            extra_meta={"prompt_version": prompt_version()},
        )
        if cluster_id:
            EventCluster.objects.filter(pk=cluster_id, canonical_article__isnull=True).update(
                canonical_article=article, title=article.title_uz[:300]
            )
        structured = upsert_structured(extraction, institution=ctx.institution, article=article, post=post)
        log_rule_run("structured_upsert", structured, post_id=post.pk, article_id=article.pk)
        log_rule_run(
            "post_publish",
            {"status": article.status, "translit": "uz-cyrl"},
            post_id=post.pk,
            article_id=article.pk,
        )
        _set_status(post, ProcessingStatus.PROCESSED, processing_error="")
    return Outcome(article.status, article.pk, decision.reason)


def _merge(
    ctx: PostContext,
    system: str,
    extraction: Extraction,
    norm: rules.Normalized,
    candidate: dedupe.Candidate,
    verdict: DedupeVerdict,
) -> Outcome:
    """Attach the post to an existing event's article; regenerate it when the new source adds information."""
    post = ctx.post
    assert candidate.cluster_id is not None and candidate.article_id is not None
    canonical = Article.objects.get(pk=candidate.article_id)
    with transaction.atomic():
        dedupe.attach_to_cluster(post, candidate.cluster_id)
        articles.add_source(canonical, post, primary=False)
        log_rule_run(
            "dedupe",
            {"merged_into": canonical.pk, "verdict": verdict.model_dump()},
            post_id=post.pk,
            article_id=canonical.pk,
        )
    if verdict.adds_new_info:
        Article.objects.filter(pk=canonical.pk).update(needs_refresh=True)
        regenerate_article(canonical.pk)
    _set_status(post, ProcessingStatus.PROCESSED)
    return Outcome("merged", canonical.pk, verdict.reason)


def regenerate_article(article_id: int) -> Outcome:
    """Rewrite an article from all of its live sources (dedupe refresh, `ai_reprocess --article`)."""
    article = Article.objects.get(pk=article_id)
    primary = (
        article.sources.filter(is_primary=True).select_related("post").first() or article.sources.first()
    )
    if primary is None:
        return Outcome("noop", article_id, "no sources")
    ctx = load_context(primary.post_id)
    norm = rules.normalize(ctx.post, ctx.media, list(ctx.source.signature_patterns or []))
    system = system_prompt(ctx)
    base = base_prompt_context(ctx, norm.source_text, norm.media_descriptors)
    extraction = _extract(ctx, system, base)
    draft, factcheck = generate_and_check(
        ctx,
        system,
        base,
        extraction,
        norm,
        additional_block=_additional_sources_block(article, ctx.post),
        stage="regenerate",
        article_id=article.pk,
    )
    return _finish(ctx, extraction, draft, factcheck, article, article.cluster_id)
