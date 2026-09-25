"""Admin: institutions with contacts/metrics, programs, professions (SPEC §8 › Content)."""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from modeltranslation.admin import TranslationStackedInline, TranslationTabularInline
from unfold.admin import StackedInline, TabularInline

from apps.core.admin_base import TranslatedAdmin, mark_needs_verification, mark_verified
from apps.institutions.models import (
    Institution,
    InstitutionContact,
    InstitutionMetric,
    Profession,
    ProfessionInstitution,
    Program,
)


class ContactInline(TabularInline, TranslationTabularInline):  # type: ignore[misc]
    model = InstitutionContact
    extra = 0
    fields = ("kind", "title", "phone", "email", "hours", "order")


class MetricInline(TabularInline, TranslationTabularInline):  # type: ignore[misc]
    model = InstitutionMetric
    extra = 0
    fields = ("year", "key", "value", "unit", "source_url", "needs_verification")


@admin.register(Institution)
class InstitutionAdmin(TranslatedAdmin):
    list_display = (
        "color_dot",
        "short_name",
        "abbreviation",
        "kind",
        "order",
        "is_active",
        "needs_verification",
    )
    list_display_links = ("short_name",)
    list_filter = ("kind", "is_active", "needs_verification")
    search_fields = ("short_name", "full_name", "abbreviation", "slug")
    prepopulated_fields = {"slug": ("short_name",)}
    readonly_fields = ("stats_cache",)
    inlines = (ContactInline, MetricInline)
    actions = (mark_verified, mark_needs_verification)
    rich_text_fields = ("description", "mission")
    fieldsets = (
        (None, {"fields": ("slug", "short_name", "full_name", "abbreviation", "kind", "parent_body")}),
        (_("Tavsif"), {"fields": ("description", "mission", "founded_year")}),
        (
            _("Aloqa"),
            {
                "fields": (
                    "website_url",
                    "telegram_username",
                    "email",
                    "phone",
                    "address",
                    "city",
                    "latitude",
                    "longitude",
                )
            },
        ),
        (_("Brend"), {"fields": ("logo", "hero_image", "color", "color_text", "order")}),
        (_("Holat"), {"fields": ("is_active", "needs_verification", "stats_cache")}),
    )

    @admin.display(description=_("Rang"))
    def color_dot(self, obj: Institution) -> str:
        return format_html(
            '<span style="display:inline-block;width:12px;height:12px;border-radius:9999px;'
            'background:{}"></span>',
            obj.color,
        )


@admin.register(InstitutionMetric)
class InstitutionMetricAdmin(TranslatedAdmin):
    list_display = ("institution", "year", "key", "value", "unit", "needs_verification")
    list_filter = ("institution", "year", "key", "needs_verification")
    list_editable = ("value",)
    actions = (mark_verified, mark_needs_verification)


@admin.register(Program)
class ProgramAdmin(TranslatedAdmin):
    list_display = (
        "name",
        "institution",
        "level",
        "form",
        "duration_years",
        "is_active",
        "needs_verification",
    )
    list_filter = ("institution", "level", "form", "is_active", "needs_verification")
    search_fields = ("name", "code", "slug")
    autocomplete_fields = ("institution",)
    filter_horizontal = ("professions",)
    actions = (mark_verified, mark_needs_verification)
    rich_text_fields = ("description", "admission_requirements")


class ProfessionInstitutionInline(StackedInline, TranslationStackedInline):  # type: ignore[misc]
    model = ProfessionInstitution
    extra = 0
    autocomplete_fields = ("institution", "program")


@admin.register(Profession)
class ProfessionAdmin(TranslatedAdmin):
    list_display = ("name", "icon", "order", "is_published", "needs_verification")
    list_filter = ("is_published", "needs_verification", "institutions")
    search_fields = ("name", "summary", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ProfessionInstitutionInline,)
    actions = (mark_verified, mark_needs_verification)
    rich_text_fields = ("description",)
