"""Enqueue a gap-check request for the running ingestor (FR-TG-7)."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.telegram.ingestor.source_repository import enqueue_request
from apps.telegram.models import RequestKind, TelegramSource


class Command(BaseCommand):
    help = "Insert an IngestionRequest(kind=gapcheck); the ingestor executes it within 15 s."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--source", help="username without @ (default: all active sources)")

    def handle(self, *args: Any, **options: Any) -> None:
        source_id = None
        if options.get("source"):
            source = TelegramSource.objects.filter(username=options["source"].lstrip("@").lower()).first()
            if source is None:
                raise CommandError(f"Unknown source {options['source']!r}")
            source_id = source.pk
        request_id = enqueue_request(RequestKind.GAPCHECK, source_id)
        self.stdout.write(f"Queued gapcheck request #{request_id}")
