"""`CONTENT_MODE=verbatim`: posts are published as they are, with all media and without any LLM call."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from apps.ai.models import AIRun
from apps.ai.pipeline import verbatim
from apps.ai.tasks import process_post, weekly_digest
from apps.ai.tests.conftest import outbox_for
from apps.content.models import Article
from apps.telegram.ingestor.repository import finalize_post, mark_deleted
from apps.telegram.models import TelegramPost
from apps.telegram.tests.factories import TelegramMediaFactory

pytestmark = pytest.mark.django_db
MakePost = Callable[..., TelegramPost]

POST = "Akademiyada sport musobaqasi boʻlib oʻtdi\n\nMusobaqada 120 nafar kursant qatnashdi.\nBatafsil: https://t.me/x"


@pytest.fixture(autouse=True)
def _verbatim(settings: Any) -> None:
    settings.CONTENT_MODE = "verbatim"


def _run(post: TelegramPost, event: str = "telegram.post.created") -> dict[str, Any]:
    outbox = outbox_for(post)
    return process_post.delay(post.pk, event, str(outbox.pk) if outbox else None).get()


def test_post_is_published_unchanged_without_llm(make_post: MakePost) -> None:
    post = make_post(POST, photos=2)
    result = _run(post)
    article = Article.objects.get(pk=result["article_id"])
    assert result["status"] == "published"
    assert article.title_uz == "Akademiyada sport musobaqasi boʻlib oʻtdi"
    assert "Musobaqada 120 nafar kursant qatnashdi.<br>Batafsil" in article.body_uz
    assert article.ai_generated is False
    assert article.gallery.count() == 2
    assert article.sources.get().post_id == post.pk
    assert set(AIRun.objects.filter(post=post).values_list("stage", flat=True)) == {"triage"}


def test_short_posts_are_kept_and_empty_posts_skipped(make_post: MakePost) -> None:
    assert _run(make_post("Bayramingiz bilan!", photos=0))["status"] == "published"
    empty = make_post("", photos=0)
    assert _run(empty)["status"] == "skipped"


def test_media_only_post_gets_a_fallback_title(make_post: MakePost) -> None:
    result = _run(make_post("", photos=1))
    assert result["status"] == "published"
    assert "IIV" in Article.objects.get(pk=result["article_id"]).title_uz


def test_edit_updates_and_delete_archives(make_post: MakePost) -> None:
    post = make_post(POST)
    article_id = _run(post)["article_id"]
    TelegramPost.objects.filter(pk=post.pk).update(text=POST + "\nYangilangan.")
    assert finalize_post(post.pk) == "telegram.post.edited"
    _run(post, "telegram.post.edited")
    assert "Yangilangan." in Article.objects.get(pk=article_id).body_uz
    mark_deleted(post.source_id, [post.telegram_message_id])
    assert _run(post, "telegram.post.deleted")["status"] == "archived"


def test_videos_are_attached_with_photos(make_post: MakePost) -> None:
    post = make_post(POST, photos=1)
    TelegramMediaFactory(
        post=post,
        telegram_message_id=post.telegram_message_id + 5,
        order=5,
        kind="video",
        mime_type="video/mp4",
        original=f"telegram/x/{post.pk}/v.mp4",
    )
    article = Article.objects.get(pk=_run(post)["article_id"])
    assert article.cover_media.kind == "photo"
    assert [m.media.kind for m in article.gallery.order_by("order")] == ["photo", "video"]


def test_review_mode_does_not_hold_verbatim_posts_but_off_does() -> None:
    assert verbatim.decision("review").status == "published"
    assert verbatim.decision("off").status == "draft"


def test_text_to_html_keeps_telegram_formatting_with_utf16_offsets() -> None:
    text = "😀 Qabul boshlandi\nSayt"
    entities = [
        {"_": "MessageEntityBold", "offset": 3, "length": 5},
        {"_": "MessageEntityTextUrl", "offset": 19, "length": 4, "url": "https://example.uz"},
    ]
    html = verbatim.text_to_html(text, entities)
    assert html == '<p>😀 <strong>Qabul</strong> boshlandi<br><a href="https://example.uz">Sayt</a></p>'


def test_text_to_html_escapes_markup() -> None:
    assert verbatim.text_to_html("<script>x</script>") == "<p>&lt;script&gt;x&lt;/script&gt;</p>"


def test_title_drops_emoji_links_and_hashtags() -> None:
    assert (
        verbatim.make_title("🎉🎉 #tabrik https://t.me/a\n📌 Yangi oʻquv yili!", "fb") == "Yangi oʻquv yili!"
    )
    assert verbatim.make_title("👍", "fb") == "fb"


def test_no_translations_or_digest_in_verbatim_mode(make_post: MakePost, settings: Any) -> None:
    settings.AI_TRANSLATE_TO = ["ru", "en"]
    article = Article.objects.get(pk=_run(make_post(POST))["article_id"])
    assert (article.translation_status or {}).get("ru") is None
    assert weekly_digest() is None
