"""Long-running ingestor (`python manage.py telegram_ingest`). Never prompts; graceful on SIGTERM."""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import Any

from django.core.management.base import BaseCommand

from apps.core.redis import get_redis
from apps.telegram.ingestor.client import build_client
from apps.telegram.ingestor.runner import Ingestor


class Command(BaseCommand):
    help = "Run the Telegram ingestor (single leader; the only process that talks to Telegram)."

    def handle(self, *args: Any, **options: Any) -> None:
        sys.exit(asyncio.run(self._main()))

    async def _main(self) -> int:
        ingestor = Ingestor(build_client(), get_redis())
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, ingestor.stop)
            except (NotImplementedError, RuntimeError):  # Windows dev shells
                pass
        return await ingestor.run()
