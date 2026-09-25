from __future__ import annotations

from django.apps import AppConfig


class AppealsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.appeals"
    label = "appeals"

    def ready(self) -> None:
        from simple_history import register

        from apps.appeals.models import Appeal

        register(Appeal)
