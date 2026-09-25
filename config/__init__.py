"""EDUCORE Django project package; exposes the Celery app for `celery -A config`."""

from __future__ import annotations

from config.celery import app as celery_app

__all__ = ("celery_app",)
