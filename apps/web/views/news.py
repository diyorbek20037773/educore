"""News list/detail and long-reads (SPEC §6.4)."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from apps.analytics.services.pageviews import record_article_view
from apps.content import selectors as content
from apps.content.models import Article, ArticleStatus, Category, ContentType
from apps.institutions.selectors import active_institutions
from apps.web.views._helpers import breadcrumbs, is_htmx, paginate
from apps.web.views.pages import gone

LONGREAD_TYPES = (ContentType.ANALYSIS, ContentType.DIGEST)
HEADING_RE = re.compile(r"<h([23])>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
SORTS = ("new", "old", "popular")


def _parse_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _filters(request: HttpRequest) -> dict[str, Any]:
    sort = request.GET.get("sort", "new")
    return {
        "institution_slug": request.GET.get("inst") or None,
        "category_slug": request.GET.get("category") or None,
        "date_from": _parse_date(request.GET.get("from")),
        "date_to": _parse_date(request.GET.get("to")),
        "sort": sort if sort in SORTS else "new",
    }


def _list_context(request: HttpRequest, queryset: Any, filters: dict[str, Any]) -> dict[str, Any]:
    query = request.GET.copy()
    query.pop("page", None)
    return {
        "page_obj": paginate(request, queryset, per_page=24),
        "filters": filters,
        "querystring": query.urlencode(),
        "institutions": active_institutions(),
        "category_options": list(
            Category.objects.filter(is_active=True).order_by("order").values_list("slug", "name")
        ),
        # "new" is the select's empty option.
        "sorts": [("old", _("Eng eski")), ("popular", _("Koʻp oʻqilgan"))],
    }


@require_GET
def news_list(request: HttpRequest) -> HttpResponse:
    filters = _filters(request)
    queryset = content.article_list(**filters).exclude(content_type__in=LONGREAD_TYPES)
    context = _list_context(request, queryset, filters)
    if is_htmx(request) and request.GET.get("page"):
        return render(request, "partials/article_grid_page.html", context)
    if is_htmx(request):
        return render(request, "partials/news_results.html", context)
    context.update(breadcrumbs(request, (_("Yangiliklar"), request.path)))
    return render(request, "pages/news/list.html", context)


@require_GET
def longread_list(request: HttpRequest) -> HttpResponse:
    filters = _filters(request)
    queryset = content.article_list(**filters).filter(content_type__in=LONGREAD_TYPES)
    context = _list_context(request, queryset, filters)
    if is_htmx(request) and request.GET.get("page"):
        return render(request, "partials/article_grid_page.html", context)
    context.update(breadcrumbs(request, (_("Maqolalar"), request.path)))
    return render(request, "pages/news/longread_list.html", context)


def with_toc(html: str) -> tuple[str, list[dict[str, Any]]]:
    """Give every h2/h3 a stable id and return the table of contents."""
    toc: list[dict[str, Any]] = []
    used: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        level, inner = match.group(1), match.group(2)
        text = strip_tags(inner).strip()
        anchor = slugify(text) or f"bolim-{len(toc) + 1}"
        while anchor in used:
            anchor += "-1"
        used.add(anchor)
        toc.append({"id": anchor, "text": text, "level": int(level)})
        return f'<h{level} id="{anchor}">{inner}</h{level}>'

    return HEADING_RE.sub(replace, html), toc


def _visible_article(request: HttpRequest, slug: str) -> tuple[Article | None, HttpResponse | None]:
    article = content.article_detail(slug)
    if article is None:
        raise Http404
    if article.status == ArticleStatus.ARCHIVED:
        institution = article.primary_institution
        back = (
            reverse("web:institution_news", kwargs={"slug": institution.slug})
            if institution
            else reverse("web:news_list")
        )
        label = institution.short_name if institution else _("Yangiliklar")
        return None, gone(request, back_url=back, back_label=label)
    is_public = article.status == ArticleStatus.PUBLISHED and article.published_at is not None
    if not is_public and not (request.user.is_staff and request.GET.get("preview") == "1"):
        raise Http404
    return article, None


def _related(article: Article) -> list[Article]:
    qs = content.published_articles().exclude(pk=article.pk)
    condition = Q(category=article.category_id)
    if article.cluster_id:
        condition |= Q(cluster=article.cluster_id)
    if article.primary_institution_id:
        condition |= Q(primary_institution=article.primary_institution_id)
    return list(qs.filter(condition).order_by("-published_at")[:3])


def _neighbours(article: Article) -> tuple[Article | None, Article | None]:
    if article.published_at is None:
        return None, None
    qs = content.published_articles().exclude(pk=article.pk)
    newer = qs.filter(published_at__gt=article.published_at).order_by("published_at").first()
    older = qs.filter(published_at__lt=article.published_at).order_by("-published_at").first()
    return older, newer


def _detail(request: HttpRequest, slug: str, *, longread: bool) -> HttpResponse:
    article, response = _visible_article(request, slug)
    if response is not None:
        return response
    assert article is not None
    if (article.content_type in LONGREAD_TYPES) != longread:
        return HttpResponsePermanentRedirect(article.get_absolute_url())
    if not request.user.is_staff:
        record_article_view(article.pk)  # flushed hourly into view_count
    body, toc = with_toc(article.body) if longread else (article.body, [])
    older, newer = _neighbours(article)
    section = (
        (_("Maqolalar"), reverse("web:longread_list"))
        if longread
        else (_("Yangiliklar"), reverse("web:news_list"))
    )
    context = {
        "article": article,
        "body": body,
        "toc": toc,
        "sources": list(article.sources.all()),
        "gallery": [item for item in article.gallery.all() if not item.is_cover],
        "related": _related(article),
        "older": older,
        "newer": newer,
        "is_preview": article.status != ArticleStatus.PUBLISHED,
        **breadcrumbs(request, section, (article.title, request.path)),
    }
    return render(request, "pages/news/detail.html", context)


@require_GET
def news_detail(request: HttpRequest, slug: str) -> HttpResponse:
    return _detail(request, slug, longread=False)


@require_GET
def longread_detail(request: HttpRequest, slug: str) -> HttpResponse:
    return _detail(request, slug, longread=True)
