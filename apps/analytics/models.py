"""Aggregated statistics (SPEC §2.8). Page views are counted in Redis and flushed hourly."""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class DailyStat(TimeStampedModel):
    date = models.DateField(_("date"), unique=True)
    posts_ingested = models.PositiveIntegerField(_("posts ingested"), default=0)
    articles_published = models.PositiveIntegerField(_("articles published"), default=0)
    articles_review = models.PositiveIntegerField(_("articles sent to review"), default=0)
    ai_runs = models.PositiveIntegerField(_("AI runs"), default=0)
    ai_cost_usd = models.DecimalField(
        _("AI cost (USD)"), max_digits=10, decimal_places=6, default=Decimal("0")
    )
    appeals_new = models.PositiveIntegerField(_("new appeals"), default=0)
    pageviews = models.PositiveIntegerField(_("page views"), default=0)
    unique_visitors = models.PositiveIntegerField(_("unique visitors"), default=0)
    search_queries = models.PositiveIntegerField(_("search queries"), default=0)

    class Meta:
        ordering = ("-date",)
        verbose_name = _("daily statistic")
        verbose_name_plural = _("daily statistics")

    def __str__(self) -> str:
        return str(self.date)


class InstitutionDailyStat(TimeStampedModel):
    date = models.DateField(_("date"))
    institution = models.ForeignKey(
        "institutions.Institution",
        verbose_name=_("institution"),
        on_delete=models.CASCADE,
        related_name="daily_stats",
    )
    posts = models.PositiveIntegerField(_("posts"), default=0)
    articles = models.PositiveIntegerField(_("articles"), default=0)
    tg_views_sum = models.PositiveBigIntegerField(_("Telegram views"), default=0)
    tg_forwards_sum = models.PositiveBigIntegerField(_("Telegram forwards"), default=0)
    by_category = models.JSONField(_("by category"), default=dict, blank=True)
    by_content_type = models.JSONField(_("by content type"), default=dict, blank=True)
    by_hour = models.JSONField(_("by hour"), default=list, blank=True)

    class Meta:
        ordering = ("-date", "institution__order")
        verbose_name = _("institution daily statistic")
        verbose_name_plural = _("institution daily statistics")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["date", "institution"], name="uniq_inst_daily_stat"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["institution", "date"], name="analytics_inst_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.date} {self.institution_id}"


class SearchLog(TimeStampedModel):
    """Normalized search query counter (named to avoid shadowing postgres `SearchQuery`)."""

    query_norm = models.CharField(_("normalized query"), max_length=200, unique=True)
    count = models.PositiveIntegerField(_("count"), default=0)
    last_searched_at = models.DateTimeField(_("last searched at"), db_index=True)

    class Meta:
        ordering = ("-count",)
        verbose_name = _("search query")
        verbose_name_plural = _("search queries")

    def __str__(self) -> str:
        return self.query_norm
