"""LLM and rule-stage execution with AIRun logging, input-hash caching, budget guard and one schema retry."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import structlog
from pydantic import BaseModel

from apps.ai import budget
from apps.ai.models import AIRun, Provider, RunStatus
from apps.ai.pricing import cost_usd
from apps.ai.prompts import prompt_version
from apps.ai.providers import (
    ProviderPermanentError,
    ProviderTransientError,
    SchemaValidationError,
    get_provider,
)

log = structlog.get_logger(__name__)
VALIDATION_FEEDBACK = (
    "XATO: oldingi javob JSON sxemaga mos kelmadi. Faqat sxemaga mos JSON qaytaring. Xato matni: {error}"
)


def input_hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _cached(stage: str, digest: str) -> AIRun | None:
    return (
        AIRun.objects.filter(
            stage=stage, input_hash=digest, prompt_version=prompt_version(), status__in=[RunStatus.OK]
        )
        .exclude(output=None)
        .order_by("-created_at")
        .first()
    )


def _estimate(model: str, system: str, user: str, max_tokens: int) -> Decimal:
    return cost_usd(model, (len(system) + len(user)) // 3, max_tokens // 3)


def call_llm[SchemaT: BaseModel](
    *,
    stage: str,
    model: str,
    system: str,
    render_user: Callable[[str], str],
    schema: type[SchemaT],
    max_tokens: int,
    post_id: int | None = None,
    article_id: int | None = None,
    use_cache: bool = True,
) -> tuple[SchemaT, AIRun]:
    """Run one structured LLM stage. `render_user(feedback)` renders the user prompt (feedback is "" first).

    Raises `budget.BudgetExhaustedError`, `ProviderTransientError` (retryable) or `ProviderPermanentError`.
    """
    provider = get_provider()
    user = render_user("")
    digest = input_hash(stage, model, schema.__name__, system, user)
    if use_cache and (hit := _cached(stage, digest)) is not None:
        run = AIRun.objects.create(
            post_id=post_id,
            article_id=article_id,
            stage=stage,
            provider=hit.provider,
            model=model,
            prompt_version=prompt_version(),
            input_hash=digest,
            status=RunStatus.CACHED,
            output=hit.output,
        )
        return schema.model_validate(hit.output), run

    paid = provider.name != Provider.MOCK
    if paid:
        budget.ensure_budget(_estimate(model, system, user, max_tokens))

    started = time.monotonic()
    tokens_in = tokens_out = 0
    feedback = ""
    for attempt in (1, 2):
        try:
            result = provider.complete_json(
                model=model, system=system, user=render_user(feedback), schema=schema, max_tokens=max_tokens
            )
            break
        except SchemaValidationError as exc:
            tokens_in, tokens_out = tokens_in + exc.input_tokens, tokens_out + exc.output_tokens
            if attempt == 2:
                _fail(
                    stage,
                    model,
                    digest,
                    post_id,
                    article_id,
                    provider.name,
                    started,
                    tokens_in,
                    tokens_out,
                    exc,
                )
                raise ProviderPermanentError(f"schema validation failed twice: {exc}") from exc
            feedback = VALIDATION_FEEDBACK.format(error=str(exc)[:800])
        except (ProviderTransientError, ProviderPermanentError) as exc:
            _fail(
                stage, model, digest, post_id, article_id, provider.name, started, tokens_in, tokens_out, exc
            )
            raise
    tokens_in += result.input_tokens
    tokens_out += result.output_tokens
    cost = cost_usd(model, tokens_in, tokens_out) if paid else Decimal("0")
    run = AIRun.objects.create(
        post_id=post_id,
        article_id=article_id,
        stage=stage,
        provider=provider.name,
        model=model,
        prompt_version=prompt_version(),
        input_hash=digest,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cost_usd=cost,
        duration_ms=int((time.monotonic() - started) * 1000),
        status=RunStatus.OK,
        request_id=result.request_id or "",
        output=result.data,
    )
    budget.record_spend(cost, tokens_in, tokens_out)
    log.info(
        "ai_stage_done", stage=stage, post_id=post_id, article_id=article_id, cost_usd=str(cost), model=model
    )
    return result.parsed, run  # type: ignore[return-value]


def _fail(
    stage: str,
    model: str,
    digest: str,
    post_id: int | None,
    article_id: int | None,
    provider: str,
    started: float,
    tokens_in: int,
    tokens_out: int,
    exc: Exception,
) -> None:
    cost = cost_usd(model, tokens_in, tokens_out) if provider != Provider.MOCK else Decimal("0")
    AIRun.objects.create(
        post_id=post_id,
        article_id=article_id,
        stage=stage,
        provider=provider,
        model=model,
        prompt_version=prompt_version(),
        input_hash=digest,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cost_usd=cost,
        duration_ms=int((time.monotonic() - started) * 1000),
        status=RunStatus.FAILED,
        error=f"{type(exc).__name__}: {exc}"[:4000],
    )
    if tokens_in or tokens_out:
        budget.record_spend(cost, tokens_in, tokens_out)
    log.warning("ai_stage_failed", stage=stage, post_id=post_id, article_id=article_id, error=str(exc))


def log_rule_run(
    stage: str,
    output: dict[str, Any] | None,
    *,
    post_id: int | None = None,
    article_id: int | None = None,
    status: str = RunStatus.OK,
    provider: str = Provider.RULES,
    error: str = "",
    started: float | None = None,
) -> AIRun:
    """AIRun for a deterministic stage (triage, normalize, embed, dedupe search, media select, policy, …)."""
    payload = json.loads(json.dumps(output, default=str)) if output is not None else None
    return AIRun.objects.create(
        post_id=post_id,
        article_id=article_id,
        stage=stage,
        provider=provider,
        prompt_version=prompt_version(),
        input_hash="",
        status=status,
        error=error,
        output=payload,
        duration_ms=int((time.monotonic() - started) * 1000) if started else 0,
    )
