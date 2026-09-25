"""Download and load the embedding model once (image build / first start of `worker-ai`)."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.ai.embeddings import get_embedder


class Command(BaseCommand):
    help = "Load the configured embedding model (downloads it into FASTEMBED_CACHE_DIR if missing)."

    def handle(self, *args: Any, **options: Any) -> None:
        embedder = get_embedder()
        vector = embedder.embed("EDUCORE")
        self.stdout.write(f"{embedder.name}: {len(vector)} dimensions")
