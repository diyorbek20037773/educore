"""Provider protocol and result types (AI_PIPELINE §1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class ProviderError(Exception):
    """Base class for provider failures."""


class ProviderTransientError(ProviderError):
    """Rate limit, connection error, timeout, 5xx — safe to retry with backoff."""


class ProviderPermanentError(ProviderError):
    """4xx (except 429) or a refusal — fail fast, the item goes to review."""


class SchemaValidationError(ProviderError):
    """The model answered, but the JSON does not validate; retried once with the error appended."""

    def __init__(self, message: str, raw: str = "", input_tokens: int = 0, output_tokens: int = 0) -> None:
        super().__init__(message)
        self.raw = raw
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


@dataclass(frozen=True)
class JSONResult:
    data: dict[str, Any]
    parsed: BaseModel
    input_tokens: int
    output_tokens: int
    request_id: str | None
    raw: str


@dataclass(frozen=True)
class TextResult:
    text: str
    input_tokens: int
    output_tokens: int
    request_id: str | None


class AIProvider(Protocol):
    name: str

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: type[BaseModel],
        max_tokens: int,
        timeout: float = 60.0,
    ) -> JSONResult: ...

    def complete_text(
        self, *, model: str, system: str, user: str, max_tokens: int, timeout: float = 60.0
    ) -> TextResult: ...
