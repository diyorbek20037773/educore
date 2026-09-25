"""Versioned Markdown prompts (AI_PIPELINE §3). `{{name}}` placeholders, filled by one regex substitution.

Never use `str.format`/`string.Template` — prompts contain JSON braces. Changing any prompt text
requires a new `PROMPT_VERSION` (new AIRun cache keys).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.conf import settings

PROMPTS_DIR = Path(__file__).resolve().parent
DEFAULT_VERSION = "v1"
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def prompt_version() -> str:
    return settings.PROMPT_VERSION_OVERRIDE or DEFAULT_VERSION


@lru_cache(maxsize=64)
def load(name: str, version: str | None = None) -> str:
    """Raw template text of `prompts/{version}/{name}.md`."""
    path = PROMPTS_DIR / (version or prompt_version()) / f"{name}.md"
    return path.read_text(encoding="utf-8")


def render(name: str, version: str | None = None, **context: Any) -> str:
    """Fill every `{{placeholder}}`; missing keys become empty strings (optional blocks)."""
    template = load(name, version)
    return _PLACEHOLDER.sub(lambda m: str(context.get(m.group(1), "") or ""), template).strip() + "\n"


def placeholders(name: str, version: str | None = None) -> set[str]:
    return set(_PLACEHOLDER.findall(load(name, version)))
