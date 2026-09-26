"""Moderator workflow: status changes, replies, SLA, CSV export, anonymization (SPEC §8, NFR-SEC-5)."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import date, datetime, timedelta

import structlog
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.appeals.models import Appeal, AppealMessage, AppealStatus

log = structlog.get_logger(__name__)

SLA_WORKING_DAYS = 15
OPEN_STATUSES = (AppealStatus.NEW, AppealStatus.IN_PROGRESS)
FINAL_STATUSES = (AppealStatus.CLOSED, AppealStatus.REJECTED)
ANONYMIZED_NAME = "Anonimlashtirilgan"
ANONYMIZED_TEXT = "[anonimlashtirilgan]"


def apply_status(appeal: Appeal, status: str, *, now: datetime | None = None) -> None:
    """Set `status` and stamp `answered_at` / `closed_at` the first time they are reached (no save)."""
    now = now or timezone.now()
    appeal.status = status
    if status == AppealStatus.ANSWERED and appeal.answered_at is None:
        appeal.answered_at = now
    if status in FINAL_STATUSES and appeal.closed_at is None:
        appeal.closed_at = now
    if status in OPEN_STATUSES:
        appeal.closed_at = None


def change_status(appeals: Iterable[Appeal], status: str) -> int:
    """Bulk status change through `save()` so history records who changed what."""
    changed = 0
    for appeal in appeals:
        if appeal.status == status:
            continue
        apply_status(appeal, status)
        appeal.save(update_fields=["status", "answered_at", "closed_at", "updated_at"])
        changed += 1
    return changed


def after_message_saved(message: AppealMessage) -> None:
    """A public staff reply marks the appeal answered and e-mails the applicant after commit."""
    if message.author_id is None or not message.is_public:
        return
    appeal = message.appeal
    if appeal.status in OPEN_STATUSES:
        apply_status(appeal, AppealStatus.ANSWERED)
        appeal.save(update_fields=["status", "answered_at", "closed_at", "updated_at"])
    if message.notified_at is None:
        from apps.appeals.tasks import notify_reply

        transaction.on_commit(lambda: notify_reply.delay(message.pk))


def add_reply(appeal: Appeal, author: User, body: str, *, is_public: bool = True) -> AppealMessage:
    """Create a staff message (public reply or internal note) and run the reply side effects."""
    with transaction.atomic():
        message = AppealMessage.objects.create(appeal=appeal, author=author, body=body, is_public=is_public)
        after_message_saved(message)
    return message


def working_days_ago(days: int, today: date | None = None) -> date:
    """The date `days` working days (Mon–Fri) before `today`."""
    current = today or timezone.localdate()
    remaining = days
    while remaining > 0:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def overdue(queryset: QuerySet[Appeal], today: date | None = None) -> QuerySet[Appeal]:
    """Open appeals submitted more than 15 working days ago."""
    cutoff = working_days_ago(SLA_WORKING_DAYS, today)
    return queryset.filter(status__in=OPEN_STATUSES, created_at__date__lt=cutoff)


CSV_COLUMNS = (
    "tracking_code",
    "created_at",
    "status",
    "priority",
    "institution",
    "topic",
    "full_name",
    "phone",
    "email",
    "assigned_to",
    "answered_at",
    "closed_at",
    "message",
)


def export_csv(queryset: QuerySet[Appeal]) -> str:
    """CSV (UTF-8 with BOM for Excel) of the selected appeals."""
    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for appeal in queryset.select_related("institution", "assigned_to"):
        writer.writerow(
            [
                appeal.tracking_code,
                timezone.localtime(appeal.created_at).strftime("%Y-%m-%d %H:%M"),
                appeal.get_status_display(),
                appeal.get_priority_display(),
                appeal.institution.short_name if appeal.institution else "",
                appeal.get_topic_display(),
                appeal.full_name,
                appeal.phone,
                appeal.email,
                appeal.assigned_to.email if appeal.assigned_to else "",
                timezone.localtime(appeal.answered_at).strftime("%Y-%m-%d %H:%M")
                if appeal.answered_at
                else "",
                timezone.localtime(appeal.closed_at).strftime("%Y-%m-%d %H:%M") if appeal.closed_at else "",
                _csv_safe(appeal.message),
            ]
        )
    return buffer.getvalue()


def _csv_safe(value: str) -> str:
    """Neutralize spreadsheet formula injection in applicant-supplied text."""
    return f"'{value}" if value[:1] in ("=", "+", "-", "@") else value


def anonymization_candidates(months: int = 24, now: datetime | None = None) -> QuerySet[Appeal]:
    """Closed/rejected appeals whose closing is older than `months` and not yet anonymized."""
    cutoff = (now or timezone.now()) - timedelta(days=round(months * 30.44))
    return Appeal.objects.filter(status__in=FINAL_STATUSES, closed_at__lt=cutoff, anonymized_at__isnull=True)


def anonymize(appeal: Appeal) -> None:
    """Remove personal data from the appeal, its applicant messages, attachments and its history rows."""
    with transaction.atomic():
        for attachment in appeal.attachments.all():
            attachment.file.delete(save=False)
            attachment.delete()
        AppealMessage.objects.filter(appeal=appeal, author__isnull=True).update(body=ANONYMIZED_TEXT)
        pii = {
            "full_name": ANONYMIZED_NAME,
            "phone": "",
            "email": "",
            "message": ANONYMIZED_TEXT,
            "ip_hash": "",
            "user_agent": "",
            "internal_note": "",
        }
        for field, value in pii.items():
            setattr(appeal, field, value)
        appeal.anonymized_at = timezone.now()
        appeal.save_without_historical_record()  # type: ignore[attr-defined]
        appeal.history.all().update(**pii)  # type: ignore[attr-defined]
    log.info("appeal_anonymized", appeal_id=appeal.pk)
