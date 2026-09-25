"""Daily AI budget guard (FR-AI-7, AI_PIPELINE §4). Days are Asia/Tashkent calendar days."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.ai.models import AIBudgetDay
from apps.core.services.settings import get_setting


class BudgetExhaustedError(Exception):
    """Raised before a paid call when today's budget would be exceeded."""


def today() -> date:
    return timezone.localdate()


def daily_budget() -> Decimal:
    return Decimal(str(get_setting("ai_daily_usd_budget")))


def spent_today() -> Decimal:
    day = AIBudgetDay.objects.filter(date=today()).first()
    return day.usd_spent if day else Decimal("0")


def ensure_budget(estimated_usd: Decimal) -> None:
    """Raise `BudgetExhaustedError` (and mark the day) when spent + estimate exceeds the daily budget."""
    budget = daily_budget()
    if spent_today() + estimated_usd > budget:
        AIBudgetDay.objects.update_or_create(date=today(), defaults={"is_exhausted": True})
        raise BudgetExhaustedError(f"daily AI budget ${budget} exhausted")


def record_spend(cost: Decimal, input_tokens: int, output_tokens: int) -> None:
    """Atomically add one run to today's counters."""
    with transaction.atomic():
        day, _ = AIBudgetDay.objects.select_for_update().get_or_create(date=today())
        AIBudgetDay.objects.filter(pk=day.pk).update(
            usd_spent=F("usd_spent") + cost,
            input_tokens=F("input_tokens") + input_tokens,
            output_tokens=F("output_tokens") + output_tokens,
            runs=F("runs") + 1,
        )


def next_budget_reset() -> datetime:
    """Next 00:05 Asia/Tashkent — when a parked outbox row becomes eligible again (ADR-011)."""
    now = timezone.localtime()
    reset = timezone.make_aware(datetime.combine(now.date() + timedelta(days=1), time(0, 5)), now.tzinfo)
    return reset
