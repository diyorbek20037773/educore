"""Editorial admin (T3.4): review queue, source panel, regenerate/re-translate/merge, post reprocess."""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from apps.content.models import Article
from apps.content.services.editorial import merge_articles
from apps.content.tests.factories import ArticleFactory, ArticleSourceFactory
from apps.telegram.tests.factories import TelegramPostFactory

pytestmark = pytest.mark.django_db


def test_review_queue_lists_only_review_items(verified_admin_client: Client) -> None:
    waiting = ArticleFactory(review=True, title="Koʻrik kutayotgan maqola")
    ArticleFactory(title="Eʼlon qilingan maqola")
    response = verified_admin_client.get(reverse("admin:content_reviewarticle_changelist"))
    assert response.status_code == 200
    body = response.content.decode()
    assert waiting.title in body and "Eʼlon qilingan maqola" not in body


def test_article_change_page_shows_original_telegram_text(verified_admin_client: Client) -> None:
    source = ArticleSourceFactory(post=TelegramPostFactory(text="Asl xabar matni 12345"))
    response = verified_admin_client.get(reverse("admin:content_article_change", args=[source.article_id]))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Asl xabar matni 12345" in body
    assert f'href="{source.article.get_absolute_url()}?preview=1"' in body


def _action(client: Client, action: str, ids: list[int]) -> Any:
    return client.post(
        reverse("admin:content_article_changelist"),
        {"action": action, "_selected_action": [str(i) for i in ids]},
        follow=True,
    )


def test_regenerate_and_retranslate_actions_enqueue_tasks(verified_admin_client: Client) -> None:
    article = ArticleFactory()
    with mock.patch("config.celery.app.send_task") as send:
        _action(verified_admin_client, "regenerate", [article.pk])
        _action(verified_admin_client, "retranslate_ru", [article.pk])
        _action(verified_admin_client, "retranslate_en", [article.pk])
    calls = [(c.args[0], c.kwargs["args"]) for c in send.call_args_list]
    assert calls == [
        ("ai.regenerate_article", [article.pk]),
        ("ai.translate_article", [article.pk, "ru"]),
        ("ai.translate_article", [article.pk, "en"]),
    ]


def test_merge_duplicates_moves_sources_and_archives(verified_admin_client: Client) -> None:
    older = ArticleSourceFactory().article
    newer = ArticleSourceFactory().article
    Article.objects.filter(pk=newer.pk).update(source_published_at=older.published_at)
    Article.objects.filter(pk=older.pk).update(source_published_at=older.published_at.replace(year=2020))
    with mock.patch("config.celery.app.send_task") as send:
        _action(verified_admin_client, "merge_duplicates", [older.pk, newer.pk])
    older.refresh_from_db()
    newer.refresh_from_db()
    assert older.sources.count() == 2 and older.needs_refresh
    assert newer.status == "archived" and newer.review_reason == f"merged_into:{older.pk}"
    send.assert_called_once()


def test_merge_service_ignores_target_in_duplicates() -> None:
    target = ArticleSourceFactory().article
    assert merge_articles(target, [target]) == 0


def test_post_reprocess_action_enqueues_forced_run(verified_admin_client: Client) -> None:
    post = TelegramPostFactory()
    with mock.patch("config.celery.app.send_task") as send:
        verified_admin_client.post(
            reverse("admin:telegram_telegrampost_changelist"),
            {"action": "reprocess", "_selected_action": [str(post.pk)]},
        )
    assert send.call_args.kwargs["args"] == [post.pk, "telegram.post.edited", None, True]


def test_sidebar_starts_with_review_queue(verified_admin_client: Client) -> None:
    body = verified_admin_client.get(f"/{settings.ADMIN_URL_PATH}/").content.decode()
    assert reverse("admin:content_reviewarticle_changelist") in body
