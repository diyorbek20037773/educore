"""Translated fields (`_uz`, `_uz_cyrl`, `_ru`, `_en`) for the core app (SPEC §2 fields marked *)."""

from __future__ import annotations

from modeltranslation.translator import TranslationOptions, register

from apps.core.models import FAQ, Page, SiteSetting


@register(SiteSetting)
class SiteSettingTranslationOptions(TranslationOptions):
    fields = ("tagline", "address", "footer_text")


@register(Page)
class PageTranslationOptions(TranslationOptions):
    fields = ("title", "body", "seo_title", "seo_description")


@register(FAQ)
class FAQTranslationOptions(TranslationOptions):
    fields = ("question", "answer")
