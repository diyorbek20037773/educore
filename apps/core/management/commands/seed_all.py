"""Create-only seed of reference data (SPEC §12). Filled in Phase 1 (T1.3); safe to run repeatedly."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create-only seed of reference data; never overwrites existing rows."

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write("seed_all: nothing to seed yet (reference data arrives in Phase 1).")
