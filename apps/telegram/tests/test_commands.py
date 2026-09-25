"""Management commands: backfill/gapcheck enqueue, standalone guard, login guard, health check."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import StringIO
from typing import Any

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command

from apps.telegram.ingestor.client import build_client, session_path
from apps.telegram.ingestor.leader import LEADER_KEY, write_heartbeat
from apps.telegram.models import IngestionRequest, TelegramSource

pytestmark = pytest.mark.django_db


def test_backfill_enqueues_request_with_limits(source_row: TelegramSource) -> None:
    out = StringIO()
    call_command(
        "telegram_backfill",
        "--source",
        f"@{source_row.username}",
        "--limit",
        "50",
        "--ai-limit",
        "5",
        stdout=out,
    )
    req = IngestionRequest.objects.get()
    assert (req.kind, req.source_id, req.params) == ("backfill", source_row.pk, {"limit": 50, "ai_limit": 5})
    assert "Queued backfill request" in out.getvalue()


def test_backfill_all_sources_and_unknown_source() -> None:
    call_command("telegram_backfill", stdout=StringIO())
    assert IngestionRequest.objects.get().source_id is None
    with pytest.raises(CommandError):
        call_command("telegram_backfill", "--source", "nobody")


def test_standalone_backfill_refuses_while_ingestor_runs(redis_clean: Any) -> None:
    redis_clean.set(LEADER_KEY, "ingestor:1", ex=60)
    with pytest.raises(CommandError, match="leader lock"):
        call_command("telegram_backfill", "--standalone")


def test_gapcheck_enqueues(source_row: TelegramSource) -> None:
    call_command("telegram_gapcheck", "--source", source_row.username, stdout=StringIO())
    assert IngestionRequest.objects.get().kind == "gapcheck"


def test_login_refuses_while_ingestor_runs(redis_clean: Any) -> None:
    redis_clean.set(LEADER_KEY, "ingestor:1", ex=60)
    with pytest.raises(CommandError, match="leader lock"):
        call_command("telegram_login")


def test_ingestor_health_exit_codes(redis_clean: Any) -> None:
    with pytest.raises(SystemExit) as exc:
        call_command("ingestor_health", stdout=StringIO())
    assert exc.value.code == 1
    write_heartbeat(redis_clean, datetime.now(UTC) - timedelta(seconds=10))
    out = StringIO()
    call_command("ingestor_health", stdout=out)
    assert '"healthy": true' in out.getvalue()


def test_client_requires_credentials_and_strips_session_suffix(settings: Any) -> None:
    with pytest.raises(ImproperlyConfigured):
        build_client()
    settings.TELEGRAM_SESSION_PATH = "/data/telegram/educore.session"
    assert str(session_path()).endswith("educore")
