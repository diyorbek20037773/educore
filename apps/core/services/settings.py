"""Runtime settings: `SiteSetting` value when set in admin, otherwise the env default (SPEC §2.1)."""

from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.core.models import SiteSetting

# SiteSetting field → Django settings name holding the env default.
ENV_DEFAULTS: dict[str, str] = {
    "publish_mode": "PUBLISH_MODE",
    "publish_confidence_threshold": "PUBLISH_CONFIDENCE_THRESHOLD",
    "on_source_delete": "ON_SOURCE_DELETE",
    "ai_daily_usd_budget": "AI_DAILY_USD_BUDGET",
    "ai_translate_to": "AI_TRANSLATE_TO",
}


def get_setting(name: str) -> Any:
    """DB value if set (non-blank), else the env default; unknown names raise `KeyError`."""
    value = getattr(SiteSetting.get(), name, None)
    if value not in (None, "", []):
        return value
    if name in ENV_DEFAULTS:
        return getattr(settings, ENV_DEFAULTS[name])
    if value is None and not hasattr(SiteSetting, name):
        raise KeyError(name)
    return value
