"""Global template context: site settings, institutions (footer/nav), live badge, languages."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest

from apps.core.cache import content_version
from apps.core.models import Page, SiteSetting
from apps.institutions.models import Institution
from apps.telegram.models import TelegramPost

GLOBAL_CACHE_SECONDS = 60


def _globals() -> dict[str, Any]:
    key = f"web:globals:{content_version()}"
    data = cache.get(key)
    if data is None:
        data = {
            "institutions": list(Institution.objects.filter(is_active=True).order_by("order")),
            "footer_pages": list(
                Page.objects.filter(is_published=True, show_in_footer=True).order_by("order")
            ),
            "last_post_at": TelegramPost.objects.filter(is_deleted=False)
            .order_by("-published_at")
            .values_list("published_at", flat=True)
            .first(),
        }
        cache.set(key, data, GLOBAL_CACHE_SECONDS)
    return data


def site(request: HttpRequest) -> dict[str, Any]:
    if request.path_info.startswith(f"/{settings.ADMIN_URL_PATH}/"):
        return {}
    data = _globals()
    return {
        "site_setting": SiteSetting.get(),
        "nav_institutions": data["institutions"],
        "footer_pages": data["footer_pages"],
        "live_last_post_at": data["last_post_at"],
        "site_url": settings.SITE_URL,
        "content_version": content_version(),
        "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
    }
