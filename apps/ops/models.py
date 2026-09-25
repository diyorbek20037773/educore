"""Ops: alert log with dedupe/throttling (SPEC §2.9)."""

from __future__ import annotations

from typing import ClassVar

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class AlertChannel(models.TextChoices):
    TELEGRAM = "telegram", "Telegram"
    EMAIL = "email", "E-mail"
    LOG = "log", "Log"


class AlertEvent(TimeStampedModel):
    """One alert; the same `dedupe_key` is sent at most once per 30 minutes."""

    kind = models.CharField(_("kind"), max_length=60)
    dedupe_key = models.CharField(_("dedupe key"), max_length=200)
    message = models.TextField(_("message"))
    sent_at = models.DateTimeField(_("sent at"), null=True, blank=True)
    channel = models.CharField(
        _("channel"), max_length=10, choices=AlertChannel.choices, default=AlertChannel.LOG
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("alert")
        verbose_name_plural = _("alerts")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["dedupe_key", "-sent_at"], name="ops_alert_dedupe_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.kind}: {self.dedupe_key}"
