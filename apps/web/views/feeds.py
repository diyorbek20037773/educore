"""RSS 2.0 feeds: all news, per institution, per category (SPEC §6.12)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.contrib.syndication.views import Feed
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.content import selectors as content
from apps.content.models import Article, Category
from apps.institutions.models import Institution

FEED_SIZE = 30


class LatestArticlesFeed(Feed):
    def title(self) -> str:
        return _("EDUCORE — soʻnggi yangiliklar")

    def link(self) -> str:
        return reverse("web:news_list")

    def description(self) -> str:
        return _("Huquqni muhofaza qilish taʼlim muassasalarining rasmiy yangiliklari")

    def articles(self, obj: Any = None) -> Any:
        return content.published_articles().order_by("-published_at")

    def items(self, obj: Any = None) -> list[Article]:
        return list(self.articles(obj)[:FEED_SIZE])

    def item_title(self, item: Article) -> str:
        return item.title

    def item_description(self, item: Article) -> str:
        return item.lead

    def item_pubdate(self, item: Article) -> datetime | None:
        return item.published_at

    def item_updateddate(self, item: Article) -> datetime | None:
        return item.updated_at

    def item_categories(self, item: Article) -> list[str]:
        return [item.category.name] if item.category else []


class InstitutionFeed(LatestArticlesFeed):
    def get_object(self, request: HttpRequest, slug: str) -> Institution:  # type: ignore[override]
        return get_object_or_404(Institution, slug=slug, is_active=True)

    def title(self, obj: Institution) -> str:  # type: ignore[override]
        return f"EDUCORE — {obj.short_name}"

    def link(self, obj: Institution) -> str:  # type: ignore[override]
        return reverse("web:institution_news", kwargs={"slug": obj.slug})

    def articles(self, obj: Any = None) -> Any:
        return super().articles().filter(institutions=obj).distinct()


class CategoryFeed(LatestArticlesFeed):
    def get_object(self, request: HttpRequest, slug: str) -> Category:  # type: ignore[override]
        return get_object_or_404(Category, slug=slug, is_active=True)

    def title(self, obj: Category) -> str:  # type: ignore[override]
        return f"EDUCORE — {obj.name}"

    def link(self, obj: Category) -> str:  # type: ignore[override]
        return f"{reverse('web:news_list')}?category={obj.slug}"

    def articles(self, obj: Any = None) -> Any:
        return super().articles().filter(category=obj)
