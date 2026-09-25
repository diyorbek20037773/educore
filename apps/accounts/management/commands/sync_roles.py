"""Create/update the staff groups and their permissions (idempotent)."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.accounts.roles import sync_roles


class Command(BaseCommand):
    help = "Create or update the admin/editor/moderator/analyst groups and their permissions."

    def handle(self, *args: Any, **options: Any) -> None:
        for group, count in sync_roles().items():
            self.stdout.write(f"{group}: {count} permissions")
