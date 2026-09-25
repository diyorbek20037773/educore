"""`manage.py stats_rebuild` — rebuild DailyStat/InstitutionDailyStat from history (T5.1)."""

from __future__ import annotations

from datetime import date
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.analytics.services import aggregation
from apps.core.cache import bump_content_version


class Command(BaseCommand):
    help = "Recompute daily statistics for every day with activity (or a given range)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--start", type=date.fromisoformat, help="first day (YYYY-MM-DD)")
        parser.add_argument("--end", type=date.fromisoformat, help="last day (YYYY-MM-DD), default today")

    def handle(self, *args: Any, **options: Any) -> None:
        days = aggregation.rebuild(start=options["start"], end=options["end"])
        updated = aggregation.refresh_institution_stats()
        bump_content_version()
        self.stdout.write(self.style.SUCCESS(f"stats_rebuild: {days} days, {updated} institutions refreshed"))
