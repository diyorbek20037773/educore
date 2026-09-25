"""Create-only seed of reference data (SPEC §12); safe to run on every deploy."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.accounts.roles import sync_roles
from apps.core.services.beat import sync_beat_schedule
from apps.core.services.seeding import seed_reference_data


class Command(BaseCommand):
    help = (
        "Create-only seed of reference data; never overwrites existing rows. Syncs roles and beat schedule."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        report = seed_reference_data()
        created = ", ".join(f"{name}={count}" for name, count in sorted(report.created.items()))
        self.stdout.write(f"seed_all: created {created}")
        roles = sync_roles()
        self.stdout.write("roles: " + ", ".join(f"{g}={n}" for g, n in roles.items()))
        beat = sync_beat_schedule()
        self.stdout.write(
            f"beat: {beat['enabled']} enabled, {beat['disabled_until_implemented']} waiting for tasks"
        )
