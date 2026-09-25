"""Translations (tag structure, manual lock), weekly digest, ai_reprocess, prune (T3.3)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from io import StringIO
from typing import Any
from unittest import mock

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.ai.models import AIRun
from apps.ai.tasks import prune_runs, translate_article, weekly_digest
from apps.ai.tests.conftest import NEWS, outbox_for
from apps.ai.translation import tag_sequence
from apps.content.models import Article
from apps.telegram.models import IngestionOutbox, TelegramPost

pytestmark = pytest.mark.django_db
MakePost = Callable[..., TelegramPost]


def _published(make_post: MakePost) -> Article:
    from apps.ai.tasks import process_post

    post = make_post()
    result = process_post.delay(post.pk, "telegram.post.created", str(outbox_for(post).pk)).get()
    return Article.objects.get(pk=result["article_id"])


def test_translate_article_preserves_html_structure(make_post: MakePost) -> None:
    article = _published(make_post)
    assert translate_article.delay(article.pk, "ru").get() == "done"
    article.refresh_from_db()
    assert article.title_ru.startswith("[ru] ")
    assert tag_sequence(article.body_ru) == tag_sequence(article.body_uz)
    assert article.translation_status["ru"] == "done"


def test_structure_mismatch_twice_marks_failed(make_post: MakePost) -> None:
    article = _published(make_post)
    with mock.patch("apps.ai.translation.tag_sequence", side_effect=lambda html: [html]):
        assert translate_article.delay(article.pk, "en").get() == "failed"
    article.refresh_from_db()
    assert article.translation_status["en"] == "failed"


def test_manual_translation_is_never_overwritten(make_post: MakePost) -> None:
    article = _published(make_post)
    Article.objects.filter(pk=article.pk).update(translation_status={"ru": "manual"}, title_ru="Qoʻlda")
    assert translate_article.delay(article.pk, "ru").get() == "manual"
    assert Article.objects.get(pk=article.pk).title_ru == "Qoʻlda"


def test_publish_queues_configured_translations(make_post: MakePost, settings: Any) -> None:
    from apps.core.models import SiteSetting

    SiteSetting.objects.filter(pk=1).update(ai_translate_to=["ru", "en"])
    from django.core.cache import cache

    cache.clear()
    with (
        mock.patch("config.celery.app.send_task") as send,
        mock.patch("django.db.transaction.on_commit", side_effect=lambda fn, *a, **k: fn()),
    ):
        _published(make_post)
    queued = [c.kwargs["args"] for c in send.call_args_list if c.args[0] == "ai.translate_article"]
    assert sorted(lang for _, lang in queued) == ["en", "ru"]


def test_weekly_digest_goes_to_review(make_post: MakePost) -> None:
    article = _published(make_post)
    last_week = timezone.now() - timedelta(days=timezone.localdate().weekday() + 3)
    Article.objects.filter(pk=article.pk).update(published_at=last_week)
    digest_id = weekly_digest.delay().get()
    digest = Article.objects.get(pk=digest_id)
    assert digest.status == "review" and digest.content_type == "digest"
    assert digest.title_uz.startswith("Haftalik sharh") and "<h2>" in digest.body_uz
    assert digest.title_uz_cyrl


def test_weekly_digest_skips_empty_week(seeded: None) -> None:
    assert weekly_digest.delay().get() is None


def test_ai_reprocess_recovers_dead_post(make_post: MakePost) -> None:
    post = make_post(NEWS + " [[mock:400]]")
    from apps.ai.tasks import process_post

    process_post.delay(post.pk, "telegram.post.created", str(outbox_for(post).pk)).get()
    IngestionOutbox.objects.filter(post=post).update(is_dead=True)
    TelegramPost.objects.filter(pk=post.pk).update(text=NEWS)  # the cause is fixed
    out = StringIO()
    call_command("ai_reprocess", "--failed", "--force", stdout=out)
    assert "'status': 'published'" in out.getvalue()
    outbox = outbox_for(post)
    assert outbox.processed_at is not None and not outbox.is_dead


def test_ai_reprocess_article_regenerate_and_translate(make_post: MakePost) -> None:
    article = _published(make_post)
    out = StringIO()
    call_command("ai_reprocess", "--article", str(article.pk), stdout=out)
    call_command(
        "ai_reprocess", "--article", str(article.pk), "--stage", "translate", "--lang", "en", stdout=out
    )
    assert "published" in out.getvalue() and "[en]: done" in out.getvalue()


def test_prune_runs_drops_old_payloads(make_post: MakePost) -> None:
    _published(make_post)
    AIRun.objects.update(created_at=timezone.now() - timedelta(days=200))
    assert prune_runs.delay().get() > 0
    assert not AIRun.objects.exclude(output=None).exists()
