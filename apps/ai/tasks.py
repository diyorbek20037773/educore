"""AI Celery tasks (CLAUDE.md §11). `ai.process_post` implements the outbox semantics of ARCHITECTURE §3.4."""

from __future__ import annotations

import random
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

import structlog
from celery import shared_task
from django.db import connection
from django.db.models import F
from django.utils import timezone

from apps.ai.budget import BudgetExhaustedError, next_budget_reset
from apps.ai.pipeline import runner
from apps.ai.providers import ProviderPermanentError, ProviderTransientError
from apps.ops.services.alerts import send_alert
from apps.telegram.models import IngestionOutbox, ProcessingStatus, TelegramPost

log = structlog.get_logger(__name__)

MAX_RETRIES = 5
MAX_BACKOFF_SECONDS = 600
LOCK_RENEW_SECONDS = 120
TERMINAL_LOCK = timedelta(minutes=30)
DEAD_AFTER = 3


def backoff_seconds(retries: int) -> int:
    """Exponential backoff with jitter, capped at 10 minutes (NFR-REL-2)."""
    return min(MAX_BACKOFF_SECONDS, int(30 * 2**retries + random.uniform(0, 15)))  # noqa: S311


@contextmanager
def renewing_outbox_lock(outbox_id: str | None) -> Iterator[None]:
    """Keep `locked_until` in the future while the task runs so the relay never re-dispatches it (ADR-011)."""
    if not outbox_id:
        yield
        return
    from apps.telegram.tasks import renew_outbox_lock

    stop = threading.Event()

    def beat() -> None:
        try:
            while not stop.wait(LOCK_RENEW_SECONDS):
                renew_outbox_lock(outbox_id)
        finally:
            connection.close()

    thread = threading.Thread(target=beat, name=f"outbox-lock-{outbox_id}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=5)


def _mark_processed(outbox_id: str | None) -> None:
    if outbox_id:
        IngestionOutbox.objects.filter(pk=outbox_id).update(processed_at=timezone.now(), last_error="")


def _park_for_budget(outbox_id: str | None, post_id: int) -> None:
    TelegramPost.objects.filter(pk=post_id).update(processing_status=ProcessingStatus.QUEUED)
    if outbox_id:
        IngestionOutbox.objects.filter(pk=outbox_id).update(locked_until=next_budget_reset())
    day = timezone.localdate().isoformat()
    send_alert(
        "ai_budget_exhausted",
        f"ai_budget_exhausted:{day}",
        "AI kunlik byudjeti tugadi; postlar navbatda qoldi va ertaga 00:05 dan davom etadi.",
    )


def terminal_failure(outbox_id: str | None, post_id: int, error: Exception) -> None:
    """Count a terminal failure; the row is dead after 3 (NFR-REL-2)."""
    message = f"{type(error).__name__}: {error}"[:4000]
    TelegramPost.objects.filter(pk=post_id).update(
        processing_status=ProcessingStatus.FAILED, processing_error=message
    )
    if not outbox_id:
        return
    IngestionOutbox.objects.filter(pk=outbox_id).update(
        attempts=F("attempts") + 1, last_error=message, locked_until=timezone.now() + TERMINAL_LOCK
    )
    row = IngestionOutbox.objects.filter(pk=outbox_id).first()
    if row and row.attempts >= DEAD_AFTER and not row.is_dead:
        IngestionOutbox.objects.filter(pk=outbox_id).update(is_dead=True)
        send_alert(
            "outbox_dead",
            f"outbox_dead:{outbox_id}",
            f"Post #{post_id} AI qayta ishlashda {DEAD_AFTER} marta muvaffaqiyatsiz boʻldi: {message[:300]}",
        )


@shared_task(bind=True, name="ai.process_post", acks_late=True, max_retries=MAX_RETRIES)
def process_post(
    self: Any,
    post_id: int,
    event_type: str = "telegram.post.created",
    outbox_id: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Run the editorial pipeline for one outbox event (idempotent per post, content hash, prompt version)."""
    structlog.contextvars.bind_contextvars(post_id=post_id, outbox_id=outbox_id)
    with renewing_outbox_lock(outbox_id):
        try:
            outcome = runner.process(post_id, event_type, force=force)
        except BudgetExhaustedError:
            _park_for_budget(outbox_id, post_id)
            return {"status": "budget_exhausted"}
        except ProviderTransientError as exc:
            if self.request.retries < self.max_retries:
                raise self.retry(exc=exc, countdown=backoff_seconds(self.request.retries)) from exc
            terminal_failure(outbox_id, post_id, exc)
            return {"status": "failed", "error": str(exc)}
        except ProviderPermanentError as exc:
            terminal_failure(outbox_id, post_id, exc)
            return {"status": "failed", "error": str(exc)}
        except Exception as exc:
            log.exception("process_post_crashed")
            terminal_failure(outbox_id, post_id, exc)
            return {"status": "failed", "error": str(exc)}
    _mark_processed(outbox_id)
    return outcome.as_dict()
