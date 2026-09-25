"""Re-run the AI pipeline for posts or articles (FR-AI-9, AS-7 recovery)."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.ai.pipeline.runner import process, regenerate_article
from apps.ai.providers import ProviderError
from apps.ai.translation import LANGUAGE_NAMES, translate_article
from apps.content.models import Article
from apps.core.services.settings import get_setting
from apps.telegram.models import IngestionOutbox, ProcessingStatus, TelegramPost


class Command(BaseCommand):
    help = "Reprocess posts (--post/--failed), regenerate (--article) or re-translate (--stage translate)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--post", type=int, nargs="*", default=[], help="TelegramPost ids")
        parser.add_argument("--article", type=int, nargs="*", default=[], help="Article ids")
        parser.add_argument("--failed", action="store_true", help="every post in status failed")
        parser.add_argument("--force", action="store_true", help="ignore triage skips and the stage cache")
        parser.add_argument("--stage", choices=["all", "translate"], default="all")
        parser.add_argument("--lang", choices=sorted(LANGUAGE_NAMES), help="with --stage translate")

    def handle(self, *args: Any, **options: Any) -> None:
        post_ids = list(options["post"])
        if options["failed"]:
            post_ids += list(
                TelegramPost.objects.filter(processing_status=ProcessingStatus.FAILED).values_list(
                    "pk", flat=True
                )
            )
        if not post_ids and not options["article"]:
            raise CommandError("Nothing to do: pass --post, --article or --failed.")
        for post_id in post_ids:
            self._post(post_id, force=options["force"])
        for article_id in options["article"]:
            if options["stage"] == "translate":
                langs = [options["lang"]] if options["lang"] else list(get_setting("ai_translate_to") or [])
                for lang in langs:
                    self.stdout.write(f"article {article_id} [{lang}]: {translate_article(article_id, lang)}")
            else:
                if not Article.objects.filter(pk=article_id).exists():
                    raise CommandError(f"Unknown article {article_id}")
                self.stdout.write(f"article {article_id}: {regenerate_article(article_id).as_dict()}")

    def _post(self, post_id: int, *, force: bool) -> None:
        if not TelegramPost.objects.filter(pk=post_id).exists():
            raise CommandError(f"Unknown post {post_id}")
        try:
            outcome = process(post_id, force=force)
        except ProviderError as exc:
            self.stderr.write(f"post {post_id}: failed — {exc}")
            return
        # A successful manual run closes whatever the relay could not deliver (dead/unprocessed rows).
        IngestionOutbox.objects.filter(post_id=post_id, processed_at__isnull=True).update(
            processed_at=timezone.now(), is_dead=False, last_error=""
        )
        self.stdout.write(f"post {post_id}: {outcome.as_dict()}")
