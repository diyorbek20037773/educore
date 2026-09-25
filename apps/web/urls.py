"""Public website URLs."""

from __future__ import annotations

from django.urls import path

from apps.web import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
]
