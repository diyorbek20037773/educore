"""Admin: site settings singleton, pages, FAQ."""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.core.admin_base import TranslatedAdmin
from apps.core.models import FAQ, Page, SiteSetting


@admin.register(SiteSetting)
class SiteSettingAdmin(TranslatedAdmin):
    fieldsets = (
        (_("Sayt"), {"fields": ("site_name", "tagline", "maintenance_mode", "live_panel_refresh_seconds")}),
        (
            _("Nashr siyosati"),
            {
                "fields": ("publish_mode", "publish_confidence_threshold", "on_source_delete"),
                "description": _("Boʻsh qiymat .env dagi standart qiymatni bildiradi."),
            },
        ),
        (_("AI"), {"fields": ("ai_daily_usd_budget", "ai_translate_to")}),
        (
            _("Aloqa"),
            {"fields": ("contact_email", "contact_phone", "address", "footer_text", "social_links")},
        ),
        (_("Analitika"), {"fields": ("ga_measurement_id",)}),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return not SiteSetting.objects.exists()

    def has_delete_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False


@admin.register(Page)
class PageAdmin(TranslatedAdmin):
    list_display = ("title", "slug", "is_published", "show_in_footer", "order", "updated_at")
    list_filter = ("is_published", "show_in_footer")
    list_editable = ("is_published", "order")
    search_fields = ("title", "slug", "body")
    prepopulated_fields = {"slug": ("title",)}
    rich_text_fields = ("body",)


@admin.register(FAQ)
class FAQAdmin(TranslatedAdmin):
    list_display = ("question", "topic", "institution", "is_published", "order")
    list_filter = ("topic", "institution", "is_published")
    list_editable = ("is_published", "order")
    search_fields = ("question", "answer")
    autocomplete_fields = ("institution",)
    rich_text_fields = ("answer",)
