"""Root URL configuration."""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from two_factor.urls import urlpatterns as two_factor_urls

from apps.ops import views as ops_views

ADMIN = settings.ADMIN_URL_PATH

urlpatterns = [
    path("metrics", ops_views.metrics, name="metrics"),
    # Two-factor login/setup live under the secret admin path; the admin's own login redirects there.
    path(f"{ADMIN}/", include(two_factor_urls)),
    path(f"{ADMIN}/login/", RedirectView.as_view(pattern_name="two_factor:login", query_string=True)),
    path(f"{ADMIN}/", admin.site.urls),
    path("", include("apps.web.urls")),
]
