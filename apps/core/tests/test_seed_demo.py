"""`seed_demo` produces a browsable demo offline (AC3.2) and is idempotent."""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command

from apps.content.models import Article
from apps.core.models import SiteSetting
from apps.telegram.models import IngestionOutbox, TelegramPost


@pytest.mark.django_db
def test_seed_demo_publishes_at_least_30_articles_and_is_idempotent(settings: Any, tmp_path: Any) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.PUBLISH_MODE = "review"  # owner's setting must not block (or be changed by) the demo
    from django.core.files.storage import storages

    storages._storages.pop("default", None)
    call_command("seed_demo", stdout=StringIO())
    published = Article.objects.filter(status="published")
    assert published.count() >= 30
    assert not published.filter(cover_media=None).exists()
    assert not published.filter(sources=None).exists()
    assert not published.filter(title_uz_cyrl="").exists()
    assert published.values("category").distinct().count() >= 6
    assert published.values("primary_institution").distinct().count() == 5
    assert not IngestionOutbox.objects.filter(processed_at__isnull=True).exists()
    assert SiteSetting.objects.get().publish_mode == "review"

    posts = TelegramPost.objects.count()
    out = StringIO()
    call_command("seed_demo", stdout=out)
    assert TelegramPost.objects.count() == posts
    assert "processed 0 demo posts" in out.getvalue()
    storages._storages.pop("default", None)
