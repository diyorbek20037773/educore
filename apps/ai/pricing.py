"""USD cost per run from a pricing table (FR-AI-7). Env override: `AI_PRICING_JSON`."""

from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache

import structlog
from django.conf import settings

log = structlog.get_logger(__name__)
MILLION = Decimal(1_000_000)

# USD per 1M tokens (AI_PIPELINE §1).
DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-5": {"in": 2, "out": 10},
    "claude-haiku-4-5-20251001": {"in": 1, "out": 5},
    "claude-haiku-4-5": {"in": 1, "out": 5},
    "claude-opus-5-5": {"in": 4, "out": 20},
}


@lru_cache(maxsize=1)
def pricing_table() -> dict[str, dict[str, float]]:
    table = dict(DEFAULT_PRICING)
    if settings.AI_PRICING_JSON:
        try:
            table.update(json.loads(settings.AI_PRICING_JSON))
        except (TypeError, ValueError):
            log.warning("ai_pricing_json_invalid")
    return table


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Cost of one call; unknown models cost 0 with a warning (never crash)."""
    if not model:
        return Decimal("0")
    price = pricing_table().get(model)
    if price is None:
        log.warning("ai_pricing_unknown_model", model=model)
        return Decimal("0")
    total = (
        Decimal(str(price["in"])) * input_tokens / MILLION
        + Decimal(str(price["out"])) * output_tokens / MILLION
    )
    return total.quantize(Decimal("0.000001"))
