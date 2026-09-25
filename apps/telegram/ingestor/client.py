"""TelegramClient factory (ARCHITECTURE §3.2). Only the ingestor and `telegram_login` ever build a client."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from telethon import TelegramClient


def session_path() -> Path:
    """Session file path without the `.session` suffix Telethon appends itself."""
    path = Path(settings.TELEGRAM_SESSION_PATH)
    return path.with_suffix("") if path.suffix == ".session" else path


def build_client() -> TelegramClient:
    """User-session client with catch-up, flood-wait auto-sleep ≤ 60 s and infinite reconnects."""
    if (
        not settings.TELEGRAM_API_ID
        or not settings.TELEGRAM_API_HASH
        or settings.TELEGRAM_API_HASH == "CHANGE_ME"
    ):
        raise ImproperlyConfigured("TELEGRAM_API_ID / TELEGRAM_API_HASH are not configured (HA2).")
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return TelegramClient(
        str(path),
        settings.TELEGRAM_API_ID,
        settings.TELEGRAM_API_HASH,
        catch_up=True,
        flood_sleep_threshold=60,
        request_retries=5,
        connection_retries=None,
        retry_delay=5,
        auto_reconnect=True,
        device_model="EDUCORE ingestor",
        app_version="1.0",
        lang_code="uz",
        system_lang_code="uz",
    )
