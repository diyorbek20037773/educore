"""Production settings guards and the Railway fallbacks (ADR-032), checked in a fresh interpreter."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROBE = (
    "import json, os; from django.conf import settings; "
    "print(json.dumps({'key': settings.SECRET_KEY, 'admin': settings.ADMIN_URL_PATH, "
    "'su': os.environ.get('DJANGO_SUPERUSER_EMAIL')}))"
)
BASE_ENV = {
    "DJANGO_SETTINGS_MODULE": "config.settings.prod",
    "ALLOWED_HOSTS": "example.test",
    "SITE_URL": "https://example.test",
    "DATABASE_URL": "postgres://u:p@localhost:5432/db",
    "REDIS_URL": "redis://localhost:6379/0",
    "DEBUG": "false",
}


def run(extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("RAILWAY_", "DJANGO_SUPERUSER_"))}
    env.update(BASE_ENV)
    env.update(extra)
    return subprocess.run(  # noqa: S603 - fixed interpreter and arguments
        [sys.executable, "-c", PROBE],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_railway_placeholders_fall_back_to_generated_values(tmp_path: Path) -> None:
    extra = {
        "RAILWAY_ENVIRONMENT": "production",
        "RAILWAY_VOLUME_MOUNT_PATH": str(tmp_path),
        "SECRET_KEY": '<python -c "import secrets; print(secrets.token_urlsafe(64))">',
        "ADMIN_URL_PATH": "<secret-admin-path, e.g. boshqaruv-7x3k>",
        "DJANGO_SUPERUSER_EMAIL": "<admin e-mail>",
        "DJANGO_SUPERUSER_PASSWORD": "<strong password>",
    }
    first = run(extra)
    assert first.returncode == 0, first.stderr
    data = json.loads(first.stdout.strip().splitlines()[-1])
    assert len(data["key"]) >= 50
    assert data["admin"].startswith("boshqaruv-")
    assert data["su"] is None
    second = json.loads(run(extra).stdout.strip().splitlines()[-1])
    assert second == data  # stable across processes and redeploys
    assert (tmp_path / ".secret_key").read_text(encoding="utf-8").strip() == data["key"]


def test_railway_real_values_are_kept(tmp_path: Path) -> None:
    key = "k" * 60
    result = run(
        {
            "RAILWAY_ENVIRONMENT": "production",
            "RAILWAY_VOLUME_MOUNT_PATH": str(tmp_path),
            "SECRET_KEY": key,
            "ADMIN_URL_PATH": "/Boshqaruv-abc1/",
            "DJANGO_SUPERUSER_EMAIL": "admin@example.test",
        }
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data == {"key": key, "admin": "boshqaruv-abc1", "su": "admin@example.test"}
    assert not (tmp_path / ".secret_key").exists()


def test_vps_placeholder_secret_key_still_refused() -> None:
    result = run({"SECRET_KEY": "<generate me>", "ADMIN_URL_PATH": "boshqaruv-abc1"})
    assert result.returncode != 0
    assert "Fill in real values" in result.stderr


def test_superuser_placeholders_never_block_startup() -> None:
    result = run(
        {
            "SECRET_KEY": "s" * 60,
            "ADMIN_URL_PATH": "boshqaruv-abc1",
            "DJANGO_SUPERUSER_PASSWORD": "<strong password>",
        }
    )
    assert result.returncode == 0, result.stderr
