"""Appeal e-mails and moderator alerts (SPEC §6.10, §8). Delivery failures are logged, never raised."""

from __future__ import annotations

import structlog
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone, translation

from apps.appeals.models import Appeal, AppealMessage
from apps.ops.services.alerts import send_alert

log = structlog.get_logger(__name__)


def tracking_url(appeal: Appeal) -> str:
    with translation.override(appeal.locale or "uz"):
        path = reverse("web:appeal_track")
    return f"{settings.SITE_URL}{path}?code={appeal.tracking_code}"


def _send(subject: str, template: str, context: dict[str, object], recipients: list[str]) -> bool:
    try:
        body = render_to_string(template, context)
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
        return True
    except Exception as exc:  # SMTP outages must not fail the task chain
        log.warning("appeal_email_failed", template=template, error=str(exc))
        return False


def send_confirmation(appeal: Appeal) -> bool:
    """Applicant confirmation with the tracking code (only when an e-mail was given)."""
    if not appeal.email:
        return False
    with translation.override(appeal.locale or "uz"):
        subject = translation.gettext("Murojaatingiz qabul qilindi: %(code)s") % {
            "code": appeal.tracking_code
        }
        return _send(
            subject,
            "emails/appeals/confirmation.txt",
            {"appeal": appeal, "tracking_url": tracking_url(appeal)},
            [appeal.email],
        )


def notify_moderators(appeal: Appeal) -> None:
    """Ops chat (or log) alert plus e-mail to `APPEALS_NOTIFY_EMAILS`; no personal data in the alert."""
    institution = appeal.institution.short_name if appeal.institution else "Umumiy"
    admin_path = reverse("admin:appeals_appeal_change", args=[appeal.pk])
    send_alert(
        "appeal_new",
        f"appeal_new:{appeal.tracking_code}",
        f"Yangi murojaat {appeal.tracking_code} ({institution}, {appeal.get_topic_display()}). "
        f"{settings.SITE_URL}{admin_path}",
    )
    if settings.APPEALS_NOTIFY_EMAILS:
        _send(
            f"[EDUCORE] Yangi murojaat {appeal.tracking_code}",
            "emails/appeals/moderator_new.txt",
            {"appeal": appeal, "institution": institution, "admin_url": f"{settings.SITE_URL}{admin_path}"},
            list(settings.APPEALS_NOTIFY_EMAILS),
        )


def send_reply(message: AppealMessage) -> bool:
    """E-mail a public staff reply to the applicant once; stamps `notified_at` on success."""
    appeal = message.appeal
    if message.notified_at is not None or not message.is_public or message.author_id is None:
        return False
    if not appeal.email:
        return False
    with translation.override(appeal.locale or "uz"):
        subject = translation.gettext("Murojaatingizga javob: %(code)s") % {"code": appeal.tracking_code}
        sent = _send(
            subject,
            "emails/appeals/reply.txt",
            {"appeal": appeal, "message": message, "tracking_url": tracking_url(appeal)},
            [appeal.email],
        )
    if sent:
        AppealMessage.objects.filter(pk=message.pk).update(notified_at=timezone.now())
    return sent
