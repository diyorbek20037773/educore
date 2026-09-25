"""Golden-set evaluation of the extract stage (AI_PIPELINE §6, `make ai-eval`)."""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.ai.pipeline.context import categories_line, institution_profile
from apps.ai.pricing import cost_usd
from apps.ai.prompts import render
from apps.ai.providers import ProviderError, get_provider
from apps.ai.schemas import Extraction
from apps.telegram.models import TelegramSource

GOLDEN = Path(__file__).resolve().parents[2] / "tests" / "golden" / "golden.json"


class Command(BaseCommand):
    help = "Run the extract stage on the 20-post golden set and report accuracy (needs ANTHROPIC_API_KEY)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--allow-mock", action="store_true", help="run against the mock (schema coverage only)"
        )
        parser.add_argument(
            "--min-accuracy", type=float, default=0.0, help="fail when category accuracy is lower"
        )
        parser.add_argument("--output", help="write per-item results as JSON")

    def handle(self, *args: Any, **options: Any) -> None:
        provider = get_provider()
        if provider.name == "mock" and not options["allow_mock"]:
            raise CommandError(
                "AI_PROVIDER=mock — set AI_PROVIDER=anthropic and ANTHROPIC_API_KEY (HA3), "
                "or pass --allow-mock for schema coverage only."
            )
        items = json.loads(GOLDEN.read_text(encoding="utf-8"))
        results: list[dict[str, Any]] = []
        tokens_in = tokens_out = 0
        categories = categories_line()
        for item in items:
            source = (
                TelegramSource.objects.select_related("institution").filter(username=item["source"]).first()
            )
            institution = source.institution if source else None
            system = render(
                "system_editor",
                institution_full_name=institution.full_name if institution else "",
                institution_profile=institution_profile(institution),
                categories=categories,
            )
            user = render(
                "extract",
                source_name=institution.short_name if institution else item["source"],
                source_username=f"@{item['source']}",
                post_date=item["date"],
                source_text=item["text"],
                media_descriptors=item["media"],
            )
            try:
                result = provider.complete_json(
                    model=settings.AI_MODEL_FAST, system=system, user=user, schema=Extraction, max_tokens=6000
                )
            except ProviderError as exc:
                results.append({"id": item["id"], "error": str(exc)})
                continue
            tokens_in += result.input_tokens
            tokens_out += result.output_tokens
            got: Extraction = result.parsed  # type: ignore[assignment]
            expected = item["expected"]
            results.append(
                {
                    "id": item["id"],
                    "category": [got.category_slug, expected["category_slug"]],
                    "content_type": [got.content_type, expected["content_type"]],
                    "low_value": [got.is_low_value, expected["is_low_value"]],
                }
            )
        scored = [r for r in results if "error" not in r]
        accuracy = {
            key: (sum(1 for r in scored if r[key][0] == r[key][1]) / len(items))
            for key in ("category", "content_type", "low_value")
        }
        cost = (
            Decimal("0")
            if provider.name == "mock"
            else cost_usd(settings.AI_MODEL_FAST, tokens_in, tokens_out)
        )
        for r in results:
            if "error" in r:
                self.stdout.write(f"{r['id']}: ERROR {r['error']}")
            else:
                marks = " ".join(
                    f"{k}={'✓' if r[k][0] == r[k][1] else '✗ ' + str(r[k][0])}"
                    for k in ("category", "content_type", "low_value")
                )
                self.stdout.write(f"{r['id']}: {marks}")
        self.stdout.write(
            f"accuracy: category {accuracy['category']:.0%} · content_type {accuracy['content_type']:.0%} · "
            f"low_value {accuracy['low_value']:.0%} · errors {len(results) - len(scored)} · "
            f"tokens {tokens_in}/{tokens_out} · cost ${cost} · provider {provider.name}"
        )
        if options["output"]:
            Path(options["output"]).write_text(
                json.dumps({"accuracy": accuracy, "results": results}, indent=1), encoding="utf-8"
            )
        if accuracy["category"] < options["min_accuracy"]:
            self.stderr.write(f"category accuracy below {options['min_accuracy']:.0%}")
            sys.exit(1)
