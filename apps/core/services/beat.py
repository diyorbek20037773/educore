"""Periodic task schedule (CLAUDE.md §11, authoritative) synced into django-celery-beat rows."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask

from config.celery import app as celery_app

TZ = "Asia/Tashkent"


@dataclass(frozen=True)
class BeatEntry:
    task: str
    queue: str
    every_seconds: int | None = None
    crontab: tuple[str, str, str, str, str] | None = None  # minute, hour, day_of_week, day_of_month, month


SCHEDULE: tuple[BeatEntry, ...] = (
    BeatEntry("telegram.relay_outbox", "ingest", every_seconds=10),
    BeatEntry("telegram.request_gapcheck", "ingest", every_seconds=10 * 60),
    BeatEntry("telegram.request_engagement_refresh", "ingest", every_seconds=6 * 3600),
    BeatEntry("telegram.request_media_retry", "ingest", every_seconds=6 * 3600),
    BeatEntry("telegram.cleanup_outbox", "default", crontab=("0", "4", "*", "*", "*")),
    BeatEntry("ai.weekly_digest", "ai", crontab=("0", "7", "1", "*", "*")),
    BeatEntry("ai.prune_runs", "default", crontab=("30", "4", "*", "1", "*")),
    BeatEntry("analytics.aggregate_daily", "default", crontab=("0", "2", "*", "*", "*")),
    BeatEntry("analytics.flush_pageviews", "default", crontab=("5", "*", "*", "*", "*")),
    BeatEntry("analytics.refresh_institution_stats", "default", crontab=("30", "2", "*", "*", "*")),
    BeatEntry("ops.check_heartbeat", "default", every_seconds=60),
    BeatEntry("ops.check_ai_failure_rate", "default", every_seconds=15 * 60),
    BeatEntry("ops.review_digest", "default", crontab=("0", "9", "*", "*", "*")),
)


def registered_tasks() -> set[str]:
    """Task names the Celery app knows about (autodiscovered from installed apps)."""
    celery_app.loader.import_default_modules()
    return set(celery_app.tasks.keys())


@transaction.atomic
def sync_beat_schedule() -> dict[str, int]:
    """Create/update one PeriodicTask per entry. Unregistered tasks are kept disabled until implemented."""
    known = registered_tasks()
    enabled = disabled = 0
    for entry in SCHEDULE:
        defaults: dict[str, object] = {
            "task": entry.task,
            "queue": entry.queue,
            "enabled": entry.task in known,
            "interval": None,
            "crontab": None,
        }
        if entry.every_seconds is not None:
            interval, _ = IntervalSchedule.objects.get_or_create(
                every=entry.every_seconds, period=IntervalSchedule.SECONDS
            )
            defaults["interval"] = interval
        elif entry.crontab is not None:
            minute, hour, dow, dom, month = entry.crontab
            crontab, _ = CrontabSchedule.objects.get_or_create(
                minute=minute, hour=hour, day_of_week=dow, day_of_month=dom, month_of_year=month, timezone=TZ
            )
            defaults["crontab"] = crontab
        PeriodicTask.objects.update_or_create(name=entry.task, defaults=defaults)
        if entry.task in known:
            enabled += 1
        else:
            disabled += 1
    return {"enabled": enabled, "disabled_until_implemented": disabled}
