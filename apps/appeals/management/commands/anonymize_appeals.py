"""`manage.py anonymize_appeals` — strip personal data from appeals closed > 24 months ago (NFR-SEC-5)."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.appeals.services import workflow


class Command(BaseCommand):
    help = "Anonymize closed/rejected appeals whose closing is older than --months (default 24)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--months", type=int, default=24, help="age threshold in months (default 24)")
        parser.add_argument("--dry-run", action="store_true", help="only count the candidates")

    def handle(self, *args: Any, **options: Any) -> None:
        candidates = workflow.anonymization_candidates(months=options["months"])
        if options["dry_run"]:
            self.stdout.write(f"anonymize_appeals: {candidates.count()} appeals would be anonymized")
            return
        count = 0
        for appeal in candidates.iterator():
            workflow.anonymize(appeal)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"anonymize_appeals: {count} appeals anonymized"))
