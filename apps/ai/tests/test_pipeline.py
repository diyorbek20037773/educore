"""End-to-end pipeline (mock provider): publish, dedupe, edit, delete, skip, review, budget, failures."""

from __future__ import annotations

import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any
from unittest import mock

import pytest
from celery.exceptions import Retry

from apps.ai.models import AIBudgetDay, AIRun, EventCluster
from apps.ai.tasks import process_post
from apps.ai.tests.conftest import NEWS, outbox_for
from apps.content.models import Article, Event
from apps.ops.models import AlertEvent
from apps.telegram.ingestor.repository import mark_deleted
from apps.telegram.models import IngestionOutbox, TelegramPost

pytestmark = pytest.mark.django_db
MakePost = Callable[..., TelegramPost]


def _run(post: TelegramPost, event: str = "telegram.post.created") -> dict[str, Any]:
    outbox = outbox_for(post)
    return process_post.delay(post.pk, event, str(outbox.pk) if outbox else None).get()


def test_fixture_post_becomes_published_article_quickly(make_post: MakePost) -> None:
    post = make_post()
    started = time.monotonic()
    result = _run(post)
    elapsed = time.monotonic() - started
    assert result["status"] == "published", result
    assert elapsed < 5
    article = Article.objects.get(pk=result["article_id"])
    assert article.title_uz and article.body_uz.startswith("<p>")
    assert article.primary_institution.abbreviation == "IIV"
    assert article.category.slug == "qabul"
    assert article.cover_media is not None and article.gallery.count() == 1
    assert article.sources.get().post == post
    assert article.title_uz_cyrl and article.title_uz_cyrl != article.title_uz  # uz-cyrl by transliteration
    assert article.translation_status["uz-cyrl"] == "done"
    assert article.tags.exists() and article.search_vector is not None
    assert article.published_at == post.published_at
    post.refresh_from_db()
    assert post.processing_status == "processed" and post.embedding is not None
    assert outbox_for(post).processed_at is not None
    stages = set(AIRun.objects.filter(post=post).values_list("stage", flat=True))
    assert {
        "triage",
        "normalize",
        "extract",
        "embed",
        "dedupe",
        "generate",
        "fact_guard",
        "media_select",
        "publish_policy",
        "structured_upsert",
        "post_publish",
    } <= stages
    assert AIRun.objects.filter(post=post, provider="mock").exclude(cost_usd=0).count() == 0


def test_redelivery_is_idempotent(make_post: MakePost) -> None:
    post = make_post()
    first = _run(post)
    runs = AIRun.objects.count()
    IngestionOutbox.objects.filter(post=post).update(processed_at=None)
    second = _run(post)
    assert second == {"status": "noop", "article_id": first["article_id"], "detail": ""}
    assert Article.objects.count() == 1
    assert AIRun.objects.count() == runs


def test_same_news_from_two_institutions_is_one_article_with_two_sources(make_post: MakePost) -> None:
    first = make_post(NEWS, "IIV", minutes_ago=50)
    _run(first)
    second = make_post(NEWS.replace("IIV Akademiyasida", "IIV Akademiyasida ham"), "JXU", minutes_ago=10)
    result = _run(second)
    assert result["status"] == "merged"
    article = Article.objects.get()
    assert {s.institution.abbreviation for s in article.sources.all()} == {"IIV", "JXU"}
    assert set(article.institutions.values_list("abbreviation", flat=True)) == {"IIV", "JXU"}
    cluster = EventCluster.objects.get()
    assert cluster.canonical_article == article and cluster.sources_count == 2
    assert AIRun.objects.filter(post=second, stage="dedupe", provider="mock").exists()


def test_unrelated_news_creates_separate_articles(make_post: MakePost) -> None:
    _run(make_post(NEWS, "IIV"))
    other = (
        "Bojxona instituti futbol jamoasi respublika chempionatida birinchi oʻrinni egallab, "
        "oltin medalni qoʻlga kiritdi."
    )
    _run(make_post(other * 2, "DBQ"))
    assert Article.objects.count() == 2
    assert EventCluster.objects.count() == 2


def test_edit_regenerates_with_history(make_post: MakePost) -> None:
    post = make_post()
    article_id = _run(post)["article_id"]
    TelegramPost.objects.filter(pk=post.pk).update(
        text=NEWS + " Tadbirda 300 dan ortiq abituriyent qatnashdi."
    )
    from apps.telegram.ingestor.repository import finalize_post

    assert finalize_post(post.pk) == "telegram.post.edited"
    result = _run(post, "telegram.post.edited")
    article = Article.objects.get(pk=article_id)
    assert result["article_id"] == article_id
    assert article.edited_at is not None
    assert article.history.count() >= 2
    assert Article.objects.count() == 1


def test_delete_archives_article(make_post: MakePost) -> None:
    post = make_post()
    article_id = _run(post)["article_id"]
    mark_deleted(post.source_id, [post.telegram_message_id])
    assert _run(post, "telegram.post.deleted")["status"] == "archived"
    assert Article.objects.get(pk=article_id).status == "archived"


def test_greeting_with_sticker_is_skipped(make_post: MakePost) -> None:
    post = make_post("Assalomu alaykum!", photos=0)
    result = _run(post)
    post.refresh_from_db()
    assert result["status"] == "skipped" and post.skip_reason == "short_text"
    assert not Article.objects.exists()


def test_fact_guard_failure_goes_to_review_after_one_regeneration(make_post: MakePost) -> None:
    post = make_post(NEWS + " [[mock:fail]]")
    result = _run(post)
    assert result["status"] == "review"
    assert Article.objects.get().review_reason == "fact_guard_failed"
    assert AIRun.objects.filter(post=post, stage="regenerate").count() == 1
    assert AIRun.objects.filter(post=post, stage="fact_guard").count() == 2  # second check may hit the cache


def test_risk_flags_and_low_confidence_go_to_review(make_post: MakePost) -> None:
    assert _run(make_post(NEWS + " [[mock:risk]]"))["status"] == "review"
    assert Article.objects.get().review_reason.startswith("risk:unverified_number")
    other = (
        "Bojxona institutida kiberxavfsizlik boʻyicha ilmiy seminar tashkil etildi va unda "
        "mutaxassislar maʼruza qildi."
    )
    assert _run(make_post(other * 2 + " [[mock:lowconf]]", "DBQ"))["status"] == "review"


def test_review_mode_sends_everything_to_review(make_post: MakePost) -> None:
    from apps.core.models import SiteSetting

    SiteSetting.objects.filter(pk=1).update(publish_mode="review")
    from django.core.cache import cache

    cache.clear()
    assert _run(make_post())["status"] == "review"
    assert Article.objects.get().review_reason == "publish_mode_review"


def test_event_post_creates_event_object(make_post: MakePost) -> None:
    text = (
        "FVV Akademiyasida yongʻin xavfsizligi boʻyicha xalqaro seminar boʻlib oʻtadi. Seminarda "
        "mutaxassislar tajriba almashadi va zamonaviy texnologiyalar namoyish etiladi. Tadbir ochiq."
    )
    result = _run(make_post(text, "FVV"))
    event = Event.objects.get()
    assert event.article_id == result["article_id"] and event.needs_verification


def test_budget_exhaustion_parks_the_post(make_post: MakePost, settings: Any) -> None:
    post = make_post()
    AIBudgetDay.objects.create(
        date=__import__("django.utils.timezone", fromlist=["x"]).localdate(), usd_spent=Decimal("5")
    )
    with mock.patch("apps.ai.runs.get_provider") as provider:
        provider.return_value = mock.Mock(name="anthropic")
        provider.return_value.name = "anthropic"
        result = _run(post)
    assert result == {"status": "budget_exhausted"}
    post.refresh_from_db()
    outbox = outbox_for(post)
    assert post.processing_status == "queued"
    assert outbox.processed_at is None and outbox.attempts == 0 and outbox.locked_until is not None
    assert AlertEvent.objects.filter(kind="ai_budget_exhausted").count() == 1


def test_provider_500_retries_then_terminal_then_dead(make_post: MakePost) -> None:
    """AS-7: five retries with backoff, then a terminal failure; three terminal failures → dead outbox row."""
    post = make_post(NEWS + " [[mock:500]]")
    outbox_id = str(outbox_for(post).pk)
    args = [post.pk, "telegram.post.created", outbox_id]
    for terminal in (1, 2, 3):
        for retries in range(5):
            with pytest.raises(Retry):
                process_post.apply(args, retries=retries)
        final = process_post.apply(args, retries=5, throw=False)
        assert final.get()["status"] == "failed"
        assert outbox_for(post).attempts == terminal
    assert outbox_for(post).is_dead
    post.refresh_from_db()
    assert post.processing_status == "failed"
    assert AIRun.objects.filter(post=post, stage="extract", status="failed").count() == 3 * 6
    assert AlertEvent.objects.filter(kind="outbox_dead").count() == 1


def test_backoff_is_exponential_and_capped() -> None:
    from apps.ai.tasks import backoff_seconds

    assert 30 <= backoff_seconds(0) <= 45
    assert 60 <= backoff_seconds(1) <= 75
    assert backoff_seconds(10) == 600


def test_permanent_error_fails_fast(make_post: MakePost) -> None:
    post = make_post(NEWS + " [[mock:400]]")
    assert _run(post)["status"] == "failed"
    assert AIRun.objects.filter(post=post, stage="extract", status="failed").count() == 1
    assert outbox_for(post).attempts == 1


def test_invalid_json_is_retried_once_with_feedback(make_post: MakePost) -> None:
    result = _run(make_post(NEWS + " [[mock:invalid]]"))
    assert result["status"] == "published"
