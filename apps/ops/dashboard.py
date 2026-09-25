"""Admin dashboard data (Unfold `DASHBOARD_CALLBACK`). Phase 5 adds the 14-day chart and cost vs budget."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.appeals.models import Appeal, AppealStatus
from apps.content.models import Article, ArticleStatus
from apps.core.health import ingestor_heartbeat_age_seconds
from apps.telegram.models import IngestionOutbox, ProcessingStatus, TelegramPost, TelegramSource


def dashboard_callback(request: HttpRequest, context: dict[str, Any]) -> dict[str, Any]:
    """Today's editorial and ingestion numbers plus per-source status."""
    today_start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    posts_today = TelegramPost.objects.filter(created_at__gte=today_start)
    heartbeat = ingestor_heartbeat_age_seconds()
    context["kpis"] = [
        {
            "title": _("Bugun kelgan postlar"),
            "value": posts_today.count(),
            "href": reverse("admin:telegram_telegrampost_changelist"),
        },
        {
            "title": _("Qayta ishlangan"),
            "value": posts_today.filter(processing_status=ProcessingStatus.PROCESSED).count(),
            "href": reverse("admin:telegram_telegrampost_changelist") + "?processing_status__exact=processed",
        },
        {
            "title": _("Koʻrik kutmoqda"),
            "value": Article.objects.filter(status=ArticleStatus.REVIEW).count(),
            "href": reverse("admin:content_article_changelist") + "?status__exact=review",
        },
        {
            "title": _("Bugun eʼlon qilingan"),
            "value": Article.objects.filter(
                status=ArticleStatus.PUBLISHED, published_at__gte=today_start
            ).count(),
            "href": reverse("admin:content_article_changelist") + "?status__exact=published",
        },
        {
            "title": _("Xatolar"),
            "value": posts_today.filter(processing_status=ProcessingStatus.FAILED).count(),
            "href": reverse("admin:telegram_telegrampost_changelist") + "?processing_status__exact=failed",
        },
        {
            "title": _("Oʻlik outbox hodisalari"),
            "value": IngestionOutbox.objects.filter(is_dead=True).count(),
            "href": reverse("admin:telegram_ingestionoutbox_changelist") + "?is_dead__exact=1",
        },
        {
            "title": _("Ochiq murojaatlar"),
            "value": Appeal.objects.filter(status__in=[AppealStatus.NEW, AppealStatus.IN_PROGRESS]).count(),
            "href": reverse("admin:appeals_appeal_changelist"),
        },
        {
            "title": _("Ingestor heartbeat"),
            "value": f"{int(heartbeat)} s" if heartbeat is not None else "—",
            "href": reverse("admin:telegram_telegramsource_changelist"),
        },
    ]
    context["sources"] = list(
        TelegramSource.objects.select_related("institution").only(
            "username", "status", "last_message_at", "institution__short_name"
        )
    )
    return context
