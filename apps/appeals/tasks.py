"""Appeal notification tasks (CLAUDE.md §11: `appeals.notify_new`, queue default)."""

from __future__ import annotations

import structlog
from celery import shared_task

from apps.appeals.models import Appeal, AppealMessage
from apps.appeals.services import notifications

log = structlog.get_logger(__name__)


@shared_task(name="appeals.notify_new", ignore_result=True)
def notify_new(appeal_id: int) -> None:
    """Confirmation e-mail to the applicant and alert to moderators for a new appeal."""
    appeal = Appeal.objects.select_related("institution").filter(pk=appeal_id).first()
    if appeal is None:
        log.warning("appeal_notify_missing", appeal_id=appeal_id)
        return
    notifications.send_confirmation(appeal)
    notifications.notify_moderators(appeal)


@shared_task(name="appeals.notify_reply", ignore_result=True)
def notify_reply(message_id: int) -> None:
    """E-mail a public staff reply to the applicant (idempotent via `notified_at`)."""
    message = AppealMessage.objects.select_related("appeal").filter(pk=message_id).first()
    if message is not None:
        notifications.send_reply(message)
