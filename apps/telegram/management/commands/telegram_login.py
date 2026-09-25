"""Interactive first login of the Telegram user session (HA2). Refuses while an ingestor is running."""

from __future__ import annotations

import asyncio
import getpass
import os
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.redis import get_redis
from apps.telegram.ingestor.client import build_client, session_path
from apps.telegram.ingestor.leader import LeaderLock


class Command(BaseCommand):
    help = "Log the dedicated Telegram account in (phone → code → optional 2FA password)."

    def handle(self, *args: Any, **options: Any) -> None:
        held = LeaderLock(get_redis()).is_held_by_anyone()
        if held:
            raise CommandError(
                "An ingestor holds the leader lock — stop it first (`docker compose stop ingestor`)."
            )
        if held is None:
            self.stderr.write("Warning: Redis unreachable; make sure no ingestor is running.")
        me = asyncio.run(self._login())
        path = session_path().with_suffix(".session")
        if path.exists():
            os.chmod(path, 0o600)
        self.stdout.write(self.style.SUCCESS(f"Logged in as {me}. Session stored at {path}."))

    async def _login(self) -> str:
        client = build_client()
        await client.start(
            phone=lambda: settings.TELEGRAM_PHONE or input("Phone (+998…): "),
            code_callback=lambda: input("Login code from Telegram: "),
            password=lambda: getpass.getpass("2FA password (if enabled): "),
        )
        me = await client.get_me()
        await client.disconnect()
        return f"{getattr(me, 'first_name', '')} (id {getattr(me, 'id', '?')})"
