"""Container health check for the ingestor: exit 0 when the heartbeat is fresh (< 180 s)."""

from __future__ import annotations

import json
import sys
from typing import Any

from django.core.management.base import BaseCommand

from apps.core.health import ingestor_heartbeat_age_seconds

MAX_AGE_SECONDS = 180


class Command(BaseCommand):
    help = "Report the ingestor heartbeat age; non-zero exit when stale or missing."

    def handle(self, *args: Any, **options: Any) -> None:
        age = ingestor_heartbeat_age_seconds()
        healthy = age is not None and age < MAX_AGE_SECONDS
        self.stdout.write(json.dumps({"healthy": healthy, "heartbeat_age_seconds": age}))
        if not healthy:
            sys.exit(1)
