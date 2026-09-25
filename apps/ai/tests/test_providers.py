"""Provider layer: Anthropic adapter (no network), mock, schemas, pricing, prompts, embeddings."""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from apps.ai.embeddings import FakeEmbedding, cosine, get_embedder
from apps.ai.pricing import cost_usd
from apps.ai.prompts import placeholders, render
from apps.ai.providers import get_provider
from apps.ai.providers.anthropic_provider import AnthropicProvider
from apps.ai.providers.base import ProviderPermanentError, ProviderTransientError, SchemaValidationError
from apps.ai.providers.mock import MockProvider
from apps.ai.schemas import Draft, Extraction, FactCheck, truncate_words

REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


class FakeMessages:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeClient:
    def __init__(self, outcome: Any) -> None:
        self.messages = FakeMessages(outcome)

    def with_options(self, **_: Any) -> FakeClient:
        return self


def _response(payload: Any, stop_reason: str = "end_turn") -> Any:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=1200, output_tokens=300),
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        id="msg_1",
        _request_id="req_1",
    )


FACT = {"verdict": "pass", "unsupported_claims": [], "risk_flags": [], "suggested_fixes": None}


def test_anthropic_structured_output_request_shape_and_parse() -> None:
    client = FakeClient(_response(FACT))
    result = AnthropicProvider("", client=client).complete_json(
        model="claude-haiku-4-5-20251001", system="SYS", user="USER", schema=FactCheck, max_tokens=800
    )
    call = client.messages.calls[0]
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["format"]["schema"]["additionalProperties"] is False
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "temperature" not in call
    assert isinstance(result.parsed, FactCheck) and result.request_id == "req_1"
    assert (result.input_tokens, result.output_tokens) == (1200, 300)


def test_anthropic_invalid_json_refusal_and_truncation() -> None:
    kwargs = {"model": "m", "system": "s", "user": "u", "schema": FactCheck, "max_tokens": 10}
    with pytest.raises(SchemaValidationError):
        AnthropicProvider("", client=FakeClient(_response("{nope"))).complete_json(**kwargs)
    with pytest.raises(SchemaValidationError):
        AnthropicProvider("", client=FakeClient(_response({"verdict": "maybe"}))).complete_json(**kwargs)
    with pytest.raises(ProviderPermanentError, match="refusal:cyber"):
        AnthropicProvider("", client=FakeClient(_response(FACT, "refusal"))).complete_json(**kwargs)
    with pytest.raises(SchemaValidationError, match="max_tokens"):
        AnthropicProvider("", client=FakeClient(_response(FACT, "max_tokens"))).complete_json(**kwargs)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            anthropic.RateLimitError("slow", response=httpx2.Response(429, request=REQUEST), body=None),
            ProviderTransientError,
        ),
        (anthropic.APIConnectionError(request=REQUEST), ProviderTransientError),
        (
            anthropic.InternalServerError("boom", response=httpx2.Response(500, request=REQUEST), body=None),
            ProviderTransientError,
        ),
        (
            anthropic.APIStatusError("overloaded", response=httpx2.Response(529, request=REQUEST), body=None),
            ProviderTransientError,
        ),
        (
            anthropic.BadRequestError("bad", response=httpx2.Response(400, request=REQUEST), body=None),
            ProviderPermanentError,
        ),
    ],
)
def test_anthropic_error_mapping(error: Exception, expected: type[Exception]) -> None:
    with pytest.raises(expected):
        AnthropicProvider("", client=FakeClient(error)).complete_text(
            model="m", system="s", user="u", max_tokens=5
        )


def test_anthropic_requires_key() -> None:
    with pytest.raises(ProviderPermanentError, match="HA3"):
        AnthropicProvider("")


def test_mock_is_the_provider_in_tests_and_fills_every_schema() -> None:
    provider = get_provider()
    assert isinstance(provider, MockProvider)
    prompt = render(
        "extract",
        source_text="IIV Akademiyasida qabul boshlandi. Hujjatlar 1-iyuldan qabul qilinadi.",
        post_date="2026-06-20",
        source_name="IIV",
        source_username="akadmvduz",
    )
    extraction = provider.complete_json(
        model="x", system="s", user=prompt, schema=Extraction, max_tokens=1
    ).parsed
    assert extraction.category_slug == "qabul" and extraction.content_type == "admission"
    assert extraction.admission is not None and extraction.admission.year == 2026
    draft = provider.complete_json(model="x", system="s", user=prompt, schema=Draft, max_tokens=1).parsed
    assert draft.title and draft.body_html.startswith("<p>") and 0 < draft.confidence <= 1


def test_mock_markers() -> None:
    provider = MockProvider()
    with pytest.raises(ProviderTransientError):
        provider.complete_text(model="x", system="s", user='"""[[mock:500]]"""', max_tokens=1)
    with pytest.raises(ProviderPermanentError):
        provider.complete_json(model="x", system="s", user="[[mock:400]]", schema=FactCheck, max_tokens=1)
    with pytest.raises(SchemaValidationError):
        provider.complete_json(
            model="x", system="s", user='"""a [[mock:invalid]]"""', schema=FactCheck, max_tokens=1
        )
    assert (
        provider.complete_json(
            model="x", system="s", user='"""a [[mock:invalid]]"""', schema=FactCheck, max_tokens=1
        ).parsed.verdict
        == "pass"
    )


def test_truncation_at_word_boundary() -> None:
    assert truncate_words("bir ikki uch toʻrt", 12) == "bir ikki…"
    long_title = "Soʻz " * 40
    assert (
        len(
            Draft(
                title=long_title,
                lead="l",
                body_html="<p>x</p>",
                seo_title=long_title,
                seo_description="d",
                reading_time_min=1,
                confidence=0.8,
            ).title
        )
        <= 90
    )


def test_unknown_category_is_rejected() -> None:
    with pytest.raises(ValueError, match="category_slug"):
        Extraction(
            language="uz",
            content_type="news",
            category_slug="nope",
            importance=3,
            is_low_value=False,
            summary_uz="x",
        )


def test_pricing(settings: Any) -> None:
    assert cost_usd("claude-sonnet-5", 3000, 900) == Decimal("0.015000")
    assert cost_usd("claude-haiku-4-5-20251001", 2500, 400) == Decimal("0.004500")
    assert cost_usd("unknown-model", 10, 10) == Decimal("0")


def test_every_placeholder_is_rendered() -> None:
    for name in (
        "system_editor",
        "extract",
        "generate",
        "fact_guard",
        "dedupe_confirm",
        "translate",
        "digest",
    ):
        text = render(name, **{p: f"<{p}>" for p in placeholders(name)})
        assert "{{" not in text
    assert '{"a": 1}' in render("extract", source_text='{"a": 1}')  # JSON braces survive


def test_fake_embeddings_similarity() -> None:
    embedder = get_embedder()
    assert isinstance(embedder, FakeEmbedding)
    a = embedder.embed("IIV Akademiyasida ochiq eshiklar kuni boʻlib oʻtdi, abituriyentlar ishtirok etdi.")
    b = embedder.embed("IIV Akademiyasida ochiq eshiklar kuni boʻlib oʻtdi va abituriyentlar ishtirok etdi.")
    c = embedder.embed("Bojxona instituti futbol jamoasi respublika chempionatida gʻolib chiqdi.")
    assert len(a) == 384 and abs(cosine(a, a) - 1) < 1e-9
    assert cosine(a, b) >= 0.9
    assert cosine(a, c) < 0.5
