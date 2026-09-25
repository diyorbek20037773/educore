"""Root URL configuration: admin + 2FA (secret path), metrics, SEO files, i18n public site (SPEC §6)."""

from __future__ import annotations

from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.i18n import set_language
from django.views.static import serve
from two_factor.urls import urlpatterns as two_factor_urls

from apps.ops import views as ops_views
from apps.web.sitemaps import SITEMAPS
from apps.web.views import pages

ADMIN = settings.ADMIN_URL_PATH

urlpatterns = [
    path("metrics", ops_views.metrics, name="metrics"),
    # Two-factor login/setup live under the secret admin path; the admin's own login redirects there.
    path(f"{ADMIN}/", include(two_factor_urls)),
    path(f"{ADMIN}/login/", RedirectView.as_view(pattern_name="two_factor:login", query_string=True)),
    path(f"{ADMIN}/", admin.site.urls),
    path("i18n/setlang/", set_language, name="set_language"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", pages.robots_txt, name="robots_txt"),
    path("humans.txt", pages.humans_txt, name="humans_txt"),
    path("manifest.webmanifest", pages.manifest, name="manifest"),
]

if settings.SERVE_MEDIA:  # dev and local prod-like checks; production serves /media/ from Caddy
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]

urlpatterns += i18n_patterns(path("", include("apps.web.urls")), prefix_default_language=False)

handler404 = "apps.web.views.pages.error_404"
handler500 = "apps.web.views.pages.error_500"
