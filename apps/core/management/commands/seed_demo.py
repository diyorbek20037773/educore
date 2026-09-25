"""Demo content (SPEC §12): ~40 sample Telegram posts with generated images, run through the mock pipeline.

Create-only: demo posts use message ids 900000+ and are never duplicated; demo posts without a published
article are (re)processed. The run forces `AI_PROVIDER=mock`, fake embeddings, `auto` publishing and no AI
translations — the owner's settings stay untouched. Works offline; outbox rows are closed so live workers
ignore them.
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.test.utils import override_settings
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from apps.ai.pipeline.context import PUBLISH_MODE_OVERRIDE, SKIP_TRANSLATIONS
from apps.ai.providers import reset_provider_cache
from apps.content.models import Article, ArticleStatus
from apps.telegram.derivatives import process_media
from apps.telegram.ingestor.normalize import extract_hashtags
from apps.telegram.ingestor.repository import finalize_post
from apps.telegram.models import IngestionOutbox, MediaStatus, TelegramMedia, TelegramPost, TelegramSource
from apps.telegram.storage import media_storage, original_path

FIXTURE = Path(settings.BASE_DIR) / "fixtures" / "telegram_posts.json"
MESSAGE_ID_BASE = 900_000


def placeholder_photo(color: str, label: str, index: int, size: tuple[int, int] = (1280, 853)) -> bytes:
    """A branded gradient image with the institution abbreviation (no external assets needed)."""
    base = tuple(int(color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    image = Image.new("RGB", size, base)
    draw = ImageDraw.Draw(image)
    for y in range(size[1]):
        shade = 0.55 + 0.45 * (1 - y / size[1]) - 0.08 * (index % 3)
        draw.line([(0, y), (size[0], y)], fill=tuple(max(0, min(255, int(c * shade))) for c in base))
    font = ImageFont.load_default(size=140)
    draw.text((80, size[1] - 260), label, fill=(255, 255, 255), font=font)
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", quality=85)
    return buffer.getvalue()


class Command(BaseCommand):
    help = "Create ~40 demo posts and run the mock AI pipeline so every page has data (offline)."

    def handle(self, *args: Any, **options: Any) -> None:
        call_command("seed_all", stdout=self.stdout)
        items = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for index, item in enumerate(items):
            self._post(index, item)
        pending = list(
            TelegramPost.objects.filter(telegram_message_id__gte=MESSAGE_ID_BASE)
            .filter(
                Q(
                    article_source__isnull=True,
                    processing_status__in=["pending", "queued", "processing", "failed"],
                )
                | Q(article_source__article__review_reason="publish_mode_review")
            )
            .values_list("pk", flat=True)
        )
        outcomes: dict[str, int] = {}
        token_mode = PUBLISH_MODE_OVERRIDE.set("auto")
        token_translate = SKIP_TRANSLATIONS.set(True)
        try:
            with override_settings(AI_PROVIDER="mock", EMBEDDING_BACKEND="fake"):
                reset_provider_cache()
                from apps.ai.pipeline.runner import process

                for post_id in pending:
                    outcome = process(post_id, force=True)
                    outcomes[outcome.status] = outcomes.get(outcome.status, 0) + 1
                    IngestionOutbox.objects.filter(post_id=post_id, processed_at__isnull=True).update(
                        processed_at=timezone.now()
                    )
        finally:
            PUBLISH_MODE_OVERRIDE.reset(token_mode)
            SKIP_TRANSLATIONS.reset(token_translate)
            reset_provider_cache()
        for article in Article.objects.filter(status=ArticleStatus.PUBLISHED, view_count=0):
            views = article.sources.values_list("post__views", flat=True).first() or 0
            Article.objects.filter(pk=article.pk).update(view_count=views // 8)
        published = Article.objects.filter(status=ArticleStatus.PUBLISHED).count()
        self.stdout.write(
            f"seed_demo: processed {len(pending)} demo posts {outcomes}; published articles: {published}"
        )

    @transaction.atomic
    def _post(self, index: int, item: dict[str, Any]) -> TelegramPost | None:
        source = TelegramSource.objects.select_related("institution").get(username=item["source"])
        message_id = MESSAGE_ID_BASE + index * 10
        if TelegramPost.objects.filter(source=source, telegram_message_id=message_id).exists():
            return None
        published = (timezone.now() - timedelta(days=item["days_ago"])).replace(
            hour=item["hour"], minute=(index * 7) % 60, second=0, microsecond=0
        )
        published = min(published, timezone.now() - timedelta(minutes=5))
        post = TelegramPost.objects.create(
            source=source,
            telegram_message_id=message_id,
            text=item["text"],
            hashtags=extract_hashtags(item["text"]),
            published_at=published,
            telegram_url=f"https://t.me/{source.username}/{message_id}",
            views=item.get("views"),
            forwards=item.get("views", 0) // 40,
            raw_json={"_": "Message", "id": message_id, "demo": True},
        )
        institution = source.institution
        color = institution.color if institution else "#1B3A6B"
        label = institution.abbreviation if institution else "EDUCORE"
        for n in range(item.get("photos", 0)):
            data = placeholder_photo(color, label, index + n)
            key = original_path(source.username, published, message_id, n, "jpg")
            saved = media_storage().save(key, ContentFile(data))
            media = TelegramMedia.objects.create(
                post=post,
                telegram_message_id=message_id + n,
                order=n,
                kind="photo",
                telegram_file_id=int(hashlib.sha256(f"{message_id}:{n}".encode()).hexdigest()[:12], 16),
                mime_type="image/jpeg",
                size_bytes=len(data),
                width=1280,
                height=853,
                original=saved,
                status=MediaStatus.DOWNLOADED,
            )
            process_media(media.pk)
        post.media_count = item.get("photos", 0)
        post.has_media = post.media_count > 0
        post.save(update_fields=["media_count", "has_media"])
        finalize_post(post.pk)
        # Close the outbox row in the same transaction so live workers never race the demo run.
        IngestionOutbox.objects.filter(post=post).update(processed_at=timezone.now())
        return post
