"""Anthropic Messages API provider with native structured outputs (AI_PIPELINE §1, ADR-023).

- Structured output via `output_config.format` (JSON schema from the Pydantic model through
  `anthropic.transform_schema`); the response is always re-validated with Pydantic.
- The long, stable system prompt is a cacheable block (`cache_control: ephemeral`).
- No sampling parameters: current models (e.g. Sonnet 5) reject `temperature`.
- SDK retries are disabled; Celery owns retries/backoff so every attempt is visible in `AIRun`.
"""

from __future__ import annotations

import json
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

from apps.ai.providers.base import (
    JSONResult,
    ProviderPermanentError,
    ProviderTransientError,
    SchemaValidationError,
    TextResult,
)

_TRANSIENT = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,  # includes APITimeoutError
    anthropic.InternalServerError,
)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, client: Any | None = None) -> None:
        if client is None and not api_key:
            raise ProviderPermanentError("ANTHROPIC_API_KEY is not configured (HA3).")
        self.client = client or anthropic.Anthropic(api_key=api_key, max_retries=0, timeout=60.0)

    def _create(self, *, timeout: float, **kwargs: Any) -> Any:
        try:
            return self.client.with_options(timeout=timeout).messages.create(**kwargs)
        except _TRANSIENT as exc:
            raise ProviderTransientError(f"{type(exc).__name__}: {exc}") from exc
        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500 or exc.status_code in (408, 409, 429, 529):
                raise ProviderTransientError(f"HTTP {exc.status_code}: {exc.message}") from exc
            raise ProviderPermanentError(f"HTTP {exc.status_code}: {exc.message}") from exc

    @staticmethod
    def _system_blocks(system: str) -> list[dict[str, Any]]:
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    @staticmethod
    def _text_of(response: Any) -> str:
        return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")

    @staticmethod
    def _check_stop(response: Any, raw: str, tokens: tuple[int, int]) -> None:
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise ProviderPermanentError(f"refusal:{category or 'unspecified'}")
        if response.stop_reason == "max_tokens":
            raise SchemaValidationError("output truncated at max_tokens", raw, *tokens)

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[BaseModel],
        max_tokens: int,
        timeout: float = 60.0,
    ) -> JSONResult:
        response = self._create(
            timeout=timeout,
            model=model,
            max_tokens=max_tokens,
            system=self._system_blocks(system),
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": anthropic.transform_schema(schema)}},
        )
        raw = self._text_of(response)
        tokens = (response.usage.input_tokens, response.usage.output_tokens)
        self._check_stop(response, raw, tokens)
        try:
            data = json.loads(raw)
            parsed = schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise SchemaValidationError(str(exc), raw, *tokens) from exc
        return JSONResult(
            data=parsed.model_dump(mode="json"),
            parsed=parsed,
            input_tokens=tokens[0],
            output_tokens=tokens[1],
            request_id=getattr(response, "_request_id", None) or getattr(response, "id", None),
            raw=raw,
        )

    def complete_text(
        self, *, model: str, system: str, user: str, max_tokens: int, timeout: float = 60.0
    ) -> TextResult:
        response = self._create(
            timeout=timeout,
            model=model,
            max_tokens=max_tokens,
            system=self._system_blocks(system),
            messages=[{"role": "user", "content": user}],
        )
        raw = self._text_of(response)
        self._check_stop(response, raw, (response.usage.input_tokens, response.usage.output_tokens))
        return TextResult(
            text=raw,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            request_id=getattr(response, "_request_id", None) or getattr(response, "id", None),
        )
