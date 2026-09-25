"""AI pipeline bookkeeping: per-stage runs, daily budget, event clusters (SPEC §2.5)."""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from django.db import models
from django.utils.translation import gettext_lazy as _
from pgvector.django import HnswIndex, VectorField

from apps.core.models import TimeStampedModel
from apps.telegram.models import EMBEDDING_DIMENSIONS


class Stage(models.TextChoices):
    TRIAGE = "triage", "triage"
    NORMALIZE = "normalize", "normalize"
    EXTRACT = "extract", "extract"
    EMBED = "embed", "embed"
    DEDUPE = "dedupe", "dedupe"
    GENERATE = "generate", "generate"
    FACT_GUARD = "fact_guard", "fact_guard"
    MEDIA_SELECT = "media_select", "media_select"
    STRUCTURED_UPSERT = "structured_upsert", "structured_upsert"
    PUBLISH_POLICY = "publish_policy", "publish_policy"
    POST_PUBLISH = "post_publish", "post_publish"
    TRANSLATE = "translate", "translate"
    REGENERATE = "regenerate", "regenerate"
    DIGEST = "digest", "digest"


class Provider(models.TextChoices):
    ANTHROPIC = "anthropic", "anthropic"
    MOCK = "mock", "mock"
    RULES = "rules", "rules"
    LOCAL = "local", "local"


class RunStatus(models.TextChoices):
    OK = "ok", _("OK")
    FAILED = "failed", _("Xato")
    SKIPPED = "skipped", _("Oʻtkazildi")
    CACHED = "cached", _("Keshdan")


class AIRun(TimeStampedModel):
    """One pipeline stage execution with tokens, cost and the validated output."""

    post = models.ForeignKey(
        "telegram.TelegramPost",
        verbose_name=_("post"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_runs",
    )
    article = models.ForeignKey(
        "content.Article",
        verbose_name=_("article"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ai_runs",
    )
    stage = models.CharField(_("stage"), max_length=20, choices=Stage.choices)
    provider = models.CharField(_("provider"), max_length=10, choices=Provider.choices)
    model = models.CharField(_("model"), max_length=80, blank=True)
    prompt_version = models.CharField(_("prompt version"), max_length=20, blank=True)
    input_hash = models.CharField(_("input hash"), max_length=64, blank=True, db_index=True)
    input_tokens = models.PositiveIntegerField(_("input tokens"), default=0)
    output_tokens = models.PositiveIntegerField(_("output tokens"), default=0)
    cost_usd = models.DecimalField(_("cost (USD)"), max_digits=10, decimal_places=6, default=Decimal("0"))
    duration_ms = models.PositiveIntegerField(_("duration (ms)"), default=0)
    status = models.CharField(_("status"), max_length=10, choices=RunStatus.choices)
    error = models.TextField(_("error"), blank=True)
    request_id = models.CharField(_("request id"), max_length=100, blank=True)
    output = models.JSONField(_("output"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("AI run")
        verbose_name_plural = _("AI runs")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["post", "stage"], name="ai_run_post_stage_idx"),
            models.Index(fields=["created_at"], name="ai_run_created_idx"),
            models.Index(fields=["stage", "input_hash", "prompt_version"], name="ai_run_cache_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.stage} {self.status} post={self.post_id}"


class AIBudgetDay(TimeStampedModel):
    """Daily AI spend counters (Asia/Tashkent date), updated atomically with F() expressions."""

    date = models.DateField(_("date"), unique=True)
    usd_spent = models.DecimalField(_("spent (USD)"), max_digits=10, decimal_places=6, default=Decimal("0"))
    input_tokens = models.PositiveBigIntegerField(_("input tokens"), default=0)
    output_tokens = models.PositiveBigIntegerField(_("output tokens"), default=0)
    runs = models.PositiveIntegerField(_("runs"), default=0)
    is_exhausted = models.BooleanField(_("exhausted"), default=False)

    class Meta:
        ordering = ("-date",)
        verbose_name = _("AI budget day")
        verbose_name_plural = _("AI budget days")

    def __str__(self) -> str:
        return f"{self.date}: ${self.usd_spent}"


class EventCluster(TimeStampedModel):
    """Posts from several sources about the same real-world event (cross-source dedupe)."""

    title = models.CharField(_("title"), max_length=300, blank=True)
    first_seen_at = models.DateTimeField(_("first seen"))
    last_seen_at = models.DateTimeField(_("last seen"))
    embedding = VectorField(_("embedding"), dimensions=EMBEDDING_DIMENSIONS, null=True, blank=True)
    canonical_article = models.ForeignKey(
        "content.Article",
        verbose_name=_("canonical article"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    posts_count = models.PositiveIntegerField(_("posts"), default=0)
    sources_count = models.PositiveIntegerField(_("sources"), default=0)

    class Meta:
        ordering = ("-last_seen_at",)
        verbose_name = _("event cluster")
        verbose_name_plural = _("event clusters")
        indexes: ClassVar[list[models.Index]] = [
            HnswIndex(
                name="ai_cluster_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self) -> str:
        return self.title or f"cluster {self.pk}"
