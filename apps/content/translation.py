"""Translated fields (`_uz`, `_uz_cyrl`, `_ru`, `_en`) for the content app (SPEC §2 fields marked *)."""

from __future__ import annotations

from modeltranslation.translator import TranslationOptions, register

from apps.content.models import Admission, Article, ArticleMedia, Category, Event, Story, Tag


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ("name", "description")


@register(Tag)
class TagTranslationOptions(TranslationOptions):
    fields = ("name",)


@register(Article)
class ArticleTranslationOptions(TranslationOptions):
    fields = ("title", "lead", "body", "seo_title", "seo_description")


@register(ArticleMedia)
class ArticleMediaTranslationOptions(TranslationOptions):
    fields = ("caption",)


@register(Event)
class EventTranslationOptions(TranslationOptions):
    fields = ("title", "description", "location")


@register(Admission)
class AdmissionTranslationOptions(TranslationOptions):
    fields = ("title", "description", "requirements", "documents", "contact")


@register(Story)
class StoryTranslationOptions(TranslationOptions):
    fields = ("title", "person_role", "quote", "body")
