"""Root URL configuration."""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.ops import views as ops_views

urlpatterns = [
    path("metrics", ops_views.metrics, name="metrics"),
    path(f"{settings.ADMIN_URL_PATH}/", admin.site.urls),
    path("", include("apps.web.urls")),
]
