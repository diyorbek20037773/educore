"""Core models: shared abstract bases (site-wide models are added in Phase 1)."""

from __future__ import annotations

from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base adding ``created_at`` / ``updated_at`` to every concrete model."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
