"""Deterministic stages: triage, normalize, length policy, media select, publish policy, eval command."""

from __future__ import annotations

from datetime import timedelta
from io import StringIO
from typing import Any

import pytest
from django.core.management import CommandError, call_command

from apps.ai.pipeline import rules
from apps.ai.schemas import Draft, Extraction, FactCheck
from apps.telegram.tests.factories import TelegramMediaFactory, TelegramPostFactory

pytestmark = pytest.mark.django_db
LONG = (
    "Akademiyada kursantlar uchun kasbiy tayyorgarlik boʻyicha amaliy mashgʻulotlar oʻtkazildi "
    "va natijalar tahlil qilindi."
)


def _triage(**kwargs: Any) -> str | None:
    media = kwargs.pop("media", [])
    post = TelegramPostFactory(**kwargs)
    rows = [
        TelegramMediaFactory(post=post, telegram_message_id=post.telegram_message_id + i, kind=k)
        for i, k in enumerate(media)
    ]
    return rules.triage(post, rows, {"akadmvduz"})


def test_triage_reasons() -> None:
    assert _triage(text=LONG) is None
    assert _triage(text=LONG, is_deleted=True) == "deleted"
    assert _triage(text="", raw_json={"_": "MessageService"}) == "service"
    assert _triage(text="") == "empty"
    assert _triage(text="👍🎉", media=["sticker"]) == "sticker_only"
    assert _triage(text="🔥🔥") == "sticker_only"
    assert _triage(text="Assalomu alaykum!", media=["sticker"]) == "short_text"
    assert _triage(text="Batafsil: https://kun.uz/x", links=["https://kun.uz/x"]) == "link_only"
    assert _triage(text="Qisqa xabar, rasm bilan.", media=["photo"]) is None
    assert (
        _triage(text="Qisqa forward matn " * 5, is_forwarded=True, forward_from="Kun.uz") == "forward_short"
    )
    assert _triage(text="Qisqa forward matn " * 5, is_forwarded=True, forward_from="IIV @akadmvduz") is None


def test_duplicate_hash_within_7_days() -> None:
    first = TelegramPostFactory(text=LONG, content_hash="h" * 64)
    dup = TelegramPostFactory(
        source=first.source,
        text=LONG,
        content_hash="h" * 64,
        published_at=first.published_at + timedelta(hours=1),
    )
    assert rules.triage(dup, [], set()) == "duplicate_hash"


def test_normalize_strips_signatures_and_describes_media() -> None:
    post = TelegramPostFactory(text=f"{LONG}\n\n@akadmvduz\nRasmiy kanalimizga obuna boʻling")
    media = [
        TelegramMediaFactory(post=post, kind="photo", telegram_message_id=post.telegram_message_id),
        TelegramMediaFactory(
            post=post, kind="video", duration_seconds=45, telegram_message_id=post.telegram_message_id + 1
        ),
    ]
    norm = rules.normalize(post, media, [])
    assert norm.text == LONG
    assert norm.media_descriptors == "[photo 1/2] [video 45 s]"
    assert norm.script == "latin"


def test_length_policy() -> None:
    assert rules.length_policy(20) == "120–200 soʻz"
    assert rules.length_policy(100) == "200–400 soʻz"
    assert rules.length_policy(400) == "300–600 soʻz"


def test_media_select_prefers_widest_photo_then_video() -> None:
    post = TelegramPostFactory()
    narrow = TelegramMediaFactory(post=post, telegram_message_id=1, order=0, width=800, original="a.jpg")
    wide = TelegramMediaFactory(post=post, telegram_message_id=2, order=1, width=1600, original="b.jpg")
    video = TelegramMediaFactory(post=post, telegram_message_id=3, order=2, kind="video", original="c.mp4")
    selection = rules.select_media([narrow, wide, video])
    assert selection.cover == wide and selection.gallery == [narrow]
    assert rules.select_media([video]).cover == video
    assert rules.select_media([]).cover is None


def _decide(**overrides: Any) -> rules.Decision:
    extraction = Extraction(
        language="uz",
        content_type=overrides.pop("content_type", "news"),
        category_slug="yangiliklar",
        importance=overrides.pop("importance", 3),
        is_low_value=overrides.pop("low", False),
        summary_uz="x",
    )
    draft = Draft(
        title="t",
        lead="l",
        body_html="<p>b</p>",
        seo_title="t",
        seo_description="d",
        reading_time_min=1,
        confidence=overrides.pop("confidence", 0.9),
    )
    check = FactCheck(verdict=overrides.pop("verdict", "pass"), risk_flags=overrides.pop("flags", []))
    return rules.decide(draft, extraction, check, publish_mode=overrides.pop("mode", "auto"), threshold=0.75)


def test_publish_policy_matrix() -> None:
    assert _decide() == rules.Decision("published", "auto")
    assert _decide(mode="off").status == "draft"
    assert _decide(mode="review").reason == "publish_mode_review"
    assert _decide(verdict="fail").reason == "fact_guard_failed"
    assert _decide(flags=["minor"]).reason == "risk:minor"
    assert _decide(low=True).reason == "low_value"
    assert _decide(content_type="advertisement").reason == "content_type"
    assert _decide(importance=1).reason == "importance"
    assert _decide(confidence=0.5).reason == "confidence"
    assert rules.article_content_type("congratulation") == "announcement"


def test_ai_eval_requires_real_provider_or_flag(seeded: None) -> None:
    with pytest.raises(CommandError, match="HA3"):
        call_command("ai_eval")
    out = StringIO()
    call_command("ai_eval", "--allow-mock", stdout=out)
    assert "accuracy: category" in out.getvalue() and "errors 0" in out.getvalue()
