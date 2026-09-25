"""Provider factory. Tests always get the mock (enforced in `config/settings/test.py`)."""

from __future__ import annotations

from functools import lru_cache

from django.conf import settings

from apps.ai.providers.base import (
    AIProvider,
    JSONResult,
    ProviderError,
    ProviderPermanentError,
    ProviderTransientError,
    SchemaValidationError,
    TextResult,
)

__all__ = [
    "AIProvider",
    "JSONResult",
    "ProviderError",
    "ProviderPermanentError",
    "ProviderTransientError",
    "SchemaValidationError",
    "TextResult",
    "get_provider",
]


@lru_cache(maxsize=2)
def _build(name: str) -> AIProvider:
    if name == "anthropic":
        from apps.ai.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings.ANTHROPIC_API_KEY)
    from apps.ai.providers.mock import MockProvider

    return MockProvider()


def get_provider() -> AIProvider:
    """The configured provider (`AI_PROVIDER=mock|anthropic`)."""
    return _build(settings.AI_PROVIDER)


def reset_provider_cache() -> None:
    _build.cache_clear()
