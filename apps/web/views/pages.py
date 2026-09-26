"""CMS pages, SEO text files, the web manifest and error pages (SPEC §6.12)."""

from __future__ import annotations

import json

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.template import loader
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from apps.core.models import Page
from apps.web.views._helpers import breadcrumbs


@require_GET
def page(request: HttpRequest, slug: str) -> HttpResponse:
    obj = Page.objects.filter(slug=slug, is_published=True).first()
    if obj is None:
        raise Http404
    context = {"page": obj, **breadcrumbs(request, (obj.title, request.path))}
    return render(request, "pages/static_page.html", context)


@require_GET
@cache_page(60 * 60)
def robots_txt(request: HttpRequest) -> HttpResponse:
    # The admin path is secret, so it is deliberately not listed here.
    lines = [
        "User-agent: *",
        "Disallow: /partials/",
        "Disallow: /*/partials/",
        "Disallow: /qidiruv/",
        "Disallow: /*/qidiruv/",
        "Disallow: /murojaat/kuzatish/",
        "Disallow: /analitika/data/",
        "Allow: /",
        "",
        f"Sitemap: {settings.SITE_URL}{reverse('sitemap')}",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


@require_GET
@cache_page(60 * 60)
def humans_txt(request: HttpRequest) -> HttpResponse:
    body = (
        "/* TEAM */\n"
        "Project: EDUCORE — information and analytics platform of law-enforcement education institutions\n"
        "Location: Tashkent, Uzbekistan\n\n"
        "/* SITE */\n"
        "Language: Uzbek (Latin, Cyrillic), Russian, English\n"
        "Standards: HTML5, CSS3, WCAG 2.1 AA\n"
        "Components: Django, PostgreSQL, HTMX, Alpine.js, Tailwind CSS, Apache ECharts\n"
        "Source of news: official Telegram channels of the institutions\n"
    )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


@require_GET
@cache_page(60 * 60)
def manifest(request: HttpRequest) -> HttpResponse:
    data = {
        "name": "EDUCORE",
        "short_name": "EDUCORE",
        "description": "Huquqni muhofaza qilish taʼlim muassasalari axborot-tahliliy platformasi",
        "lang": "uz",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#FFFFFF",
        "theme_color": "#09090B",
        "icons": [
            {"src": static("img/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("img/icon-512.png"), "sizes": "512x512", "type": "image/png"},
            {"src": static("img/favicon.svg"), "sizes": "any", "type": "image/svg+xml"},
        ],
    }
    return HttpResponse(json.dumps(data, ensure_ascii=False), content_type="application/manifest+json")


def gone(request: HttpRequest, *, back_url: str, back_label: str) -> HttpResponse:
    """410 page for archived content (SPEC §6.4)."""
    context = {"back_url": back_url, "back_label": back_label}
    return render(request, "errors/410.html", context, status=410)


def error_404(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return render(request, "errors/404.html", status=404)


def error_500(request: HttpRequest) -> HttpResponse:
    # No request context: the database or cache may be the reason we are here.
    return HttpResponse(loader.get_template("errors/500.html").render(), status=500)
