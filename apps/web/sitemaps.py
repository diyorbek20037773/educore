"""Sitemaps with language alternates for all four languages (SPEC §6.12, T4.5)."""

from __future__ import annotations

from typing import Any, ClassVar

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.content.models import Article, Event, Story
from apps.institutions.models import Institution, Profession, Program


class I18nSitemap(Sitemap):
    i18n = True
    alternates = True
    x_default = True


class SectionSitemap(I18nSitemap):
    priority = 0.8
    changefreq = "daily"
    names: ClassVar[list[str]] = [
        "home",
        "institution_list",
        "institution_compare",
        "news_list",
        "longread_list",
        "program_list",
        "admissions",
        "students_hub",
        "cadets_hub",
        "profession_list",
        "event_list",
        "story_list",
        "analytics",
        "appeal_form",
        "about",
        "contact",
        "privacy",
        "terms",
    ]

    def items(self) -> list[str]:
        return self.names

    def location(self, item: str) -> str:
        return reverse(f"web:{item}")


class InstitutionSitemap(I18nSitemap):
    priority = 0.9
    changefreq = "daily"
    tabs = (
        "institution_detail",
        "institution_programs",
        "institution_admissions",
        "institution_life",
        "institution_news",
        "institution_events",
        "institution_contacts",
    )

    def items(self) -> list[tuple[str, str]]:
        slugs = Institution.objects.filter(is_active=True).order_by("order").values_list("slug", flat=True)
        return [(tab, slug) for slug in slugs for tab in self.tabs]

    def location(self, item: tuple[str, str]) -> str:
        return reverse(f"web:{item[0]}", kwargs={"slug": item[1]})


class ArticleSitemap(I18nSitemap):
    priority = 0.7
    changefreq = "weekly"
    limit = 5000

    def items(self) -> Any:
        return (
            Article.objects.published().only("slug", "content_type", "updated_at").order_by("-published_at")
        )

    def lastmod(self, obj: Article) -> Any:
        return obj.updated_at


class ModelSitemap(I18nSitemap):
    priority = 0.6
    changefreq = "weekly"
    queryset: Any = None

    def items(self) -> Any:
        return self.queryset.all()

    def lastmod(self, obj: Any) -> Any:
        return obj.updated_at


class ProgramSitemap(ModelSitemap):
    queryset = Program.objects.filter(is_active=True, institution__is_active=True).select_related(
        "institution"
    )


class ProfessionSitemap(ModelSitemap):
    queryset = Profession.objects.filter(is_published=True).order_by("order")


class EventSitemap(ModelSitemap):
    queryset = Event.objects.filter(is_published=True).order_by("-starts_at")


class StorySitemap(ModelSitemap):
    queryset = Story.objects.filter(is_published=True).order_by("order")


SITEMAPS = {
    "sections": SectionSitemap,
    "institutions": InstitutionSitemap,
    "articles": ArticleSitemap,
    "programs": ProgramSitemap,
    "professions": ProfessionSitemap,
    "events": EventSitemap,
    "stories": StorySitemap,
}
