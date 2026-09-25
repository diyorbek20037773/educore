"""Ops alerts with throttling (SPEC §2.9): same `dedupe_key` at most once per 30 minutes.

Delivered to the ops Telegram bot when `OPS_TELEGRAM_BOT_TOKEN`/`OPS_TELEGRAM_CHAT_ID` are set
(HA7), otherwise to the structured log. Never raises — alerting must not break the caller.
"""

from __future__ import annotations

from datetime import timedelta

import httpx
import structlog
from django.conf import settings
from django.utils import timezone

from apps.ops.models import AlertChannel, AlertEvent

log = structlog.get_logger(__name__)
THROTTLE = timedelta(minutes=30)


def _send_telegram(text: str) -> bool:
    url = f"https://api.telegram.org/bot{settings.OPS_TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        response = httpx.post(
            url,
            json={"chat_id": settings.OPS_TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
        return response.status_code == 200
    except httpx.HTTPError as exc:
        log.warning("ops_alert_telegram_failed", error=str(exc))
        return False


def send_alert(kind: str, dedupe_key: str, message: str, *, force: bool = False) -> AlertEvent | None:
    """Record and deliver an alert unless one with the same key was sent in the last 30 minutes."""
    try:
        now = timezone.now()
        recent = AlertEvent.objects.filter(dedupe_key=dedupe_key, sent_at__gte=now - THROTTLE).exists()
        if recent and not force:
            log.info("ops_alert_throttled", kind=kind, dedupe_key=dedupe_key)
            return None
        channel = AlertChannel.LOG
        if settings.OPS_TELEGRAM_BOT_TOKEN and settings.OPS_TELEGRAM_CHAT_ID:
            channel = AlertChannel.TELEGRAM if _send_telegram(f"[EDUCORE] {message}") else AlertChannel.LOG
        log.warning("ops_alert", kind=kind, dedupe_key=dedupe_key, message=message, channel=channel)
        return AlertEvent.objects.create(
            kind=kind, dedupe_key=dedupe_key, message=message, sent_at=now, channel=channel
        )
    except Exception:
        log.exception("ops_alert_failed", kind=kind, dedupe_key=dedupe_key)
        return None
