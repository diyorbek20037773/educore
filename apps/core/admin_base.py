"""Shared admin building blocks: Unfold styling, translation tabs, rich-text fields, bulk "mark verified"."""

from __future__ import annotations

from typing import Any

from django.contrib import admin, messages
from django.db import models
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _
from modeltranslation.admin import TranslationAdmin
from unfold.admin import ModelAdmin
from unfold.contrib.forms.widgets import WysiwygWidget

LANG_SUFFIXES = ("", "_uz", "_uz_cyrl", "_ru", "_en")


class EducoreAdmin(ModelAdmin):
    """Base admin: Unfold look, pagination, WYSIWYG for fields listed in `rich_text_fields`."""

    list_per_page = 50
    rich_text_fields: tuple[str, ...] = ()
    warn_unsaved_form = True

    def formfield_for_dbfield(
        self, db_field: models.Field[Any, Any], request: HttpRequest, **kwargs: Any
    ) -> Any:
        if isinstance(db_field, models.TextField) and any(
            db_field.name == f"{name}{suffix}" for name in self.rich_text_fields for suffix in LANG_SUFFIXES
        ):
            kwargs["widget"] = WysiwygWidget
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class TranslatedAdmin(EducoreAdmin, TranslationAdmin):  # type: ignore[misc]
    """Admin for models registered with modeltranslation (per-language fields grouped per field)."""


class ReadOnlyAdmin(EducoreAdmin):
    """Audit/log models: viewable, never editable from the admin."""

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False


@admin.action(description=_("Tasdiqlangan deb belgilash"))
def mark_verified(modeladmin: ModelAdmin, request: HttpRequest, queryset: QuerySet[Any]) -> None:
    """Bulk action for models with `needs_verification` (owner verification, HA9)."""
    updated = queryset.update(needs_verification=False)
    modeladmin.message_user(request, _("%(n)d ta yozuv tasdiqlandi.") % {"n": updated}, messages.SUCCESS)


@admin.action(description=_("Tekshirish talab qilinadi deb belgilash"))
def mark_needs_verification(modeladmin: ModelAdmin, request: HttpRequest, queryset: QuerySet[Any]) -> None:
    updated = queryset.update(needs_verification=True)
    modeladmin.message_user(request, _("%(n)d ta yozuv belgilandi.") % {"n": updated}, messages.INFO)
