from __future__ import annotations

from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"
    label = "content"

    def ready(self) -> None:
        # Registered here, after modeltranslation patched the model in its own ready(), so the
        # history table carries the `_uz_cyrl/_ru/_en` columns too (SPEC §2.6).
        from simple_history import register

        from apps.content.models import Article

        register(Article, excluded_fields=["search_vector", "view_count"])
