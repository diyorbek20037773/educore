"""Production settings. Refuses to start with missing secrets or DEBUG enabled."""

from __future__ import annotations

import os
import re
import secrets
import sys
from collections.abc import Callable
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# Unset values and hints copied verbatim from docs (`<admin e-mail>`, `CHANGE_ME`) count as "not provided".
_PLACEHOLDER_RE = re.compile(r"\s*(?:<.*>|CHANGE_ME.*)?\s*", flags=re.DOTALL)
_ADMIN_PATH_RE = re.compile(r"[a-z0-9][a-z0-9-]{3,63}")
_ON_RAILWAY = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_ENVIRONMENT_NAME"))


def _is_placeholder(value: str | None) -> bool:
    """True for empty values and copied `<…>` / `CHANGE_ME` hints."""
    return bool(_PLACEHOLDER_RE.fullmatch(value or ""))


def _railway_state(name: str, make: Callable[[], str]) -> str:
    """Value generated once on the Railway volume, shared by every process and redeploy (ADR-032)."""
    path = Path(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") or "/data") / f".{name}"
    try:
        with path.open("x", encoding="utf-8") as fh:
            fh.write(make())
        path.chmod(0o600)
    except FileExistsError:
        pass
    except OSError:
        return make()
    return path.read_text(encoding="utf-8").strip()


# Optional variables: a copied hint must never keep the site down; treat it as unset.
for _name in ("DJANGO_SUPERUSER_EMAIL", "DJANGO_SUPERUSER_PASSWORD"):
    if _name in os.environ and _is_placeholder(os.environ[_name]):
        del os.environ[_name]

# Railway preview (ADR-032): SECRET_KEY and ADMIN_URL_PATH fall back to values generated once on the volume
# when they are missing, still hold the `<…>` hint, or are invalid. Elsewhere (VPS) they stay mandatory.
if _ON_RAILWAY:
    _key = os.environ.get("SECRET_KEY", "")
    if _is_placeholder(_key) or _key.startswith("insecure") or len(_key) < 50:
        os.environ["SECRET_KEY"] = _railway_state("secret_key", lambda: secrets.token_urlsafe(64))
        print("railway: SECRET_KEY not set; using the generated key on the volume", file=sys.stderr)
    _admin = os.environ.get("ADMIN_URL_PATH", "").strip().strip("/").lower()
    if _is_placeholder(_admin) or not _ADMIN_PATH_RE.fullmatch(_admin):
        _admin = _railway_state("admin_url_path", lambda: f"boshqaruv-{secrets.token_hex(3)}")
    os.environ["ADMIN_URL_PATH"] = _admin

# Railway preview (ADR-027): derive host settings from the generated domain when they are unset or when a
# `${{RAILWAY_PUBLIC_DOMAIN}}` reference resolved to nothing (e.g. SITE_URL="https://").
_railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
if _railway_domain:
    for _name, _value in (
        ("ALLOWED_HOSTS", _railway_domain),
        ("SITE_URL", f"https://{_railway_domain}"),
        ("CSRF_TRUSTED_ORIGINS", f"https://{_railway_domain}"),
    ):
        if os.environ.get(_name, "").strip().rstrip("/") in ("", "https:", "http:"):
            os.environ[_name] = _value

from config.settings.base import *  # noqa: E402, F403
from config.settings.base import ADMIN_URL_PATH, env  # noqa: E402

_REQUIRED = ("SECRET_KEY", "ALLOWED_HOSTS", "DATABASE_URL", "REDIS_URL", "SITE_URL")
_EMPTY = ("", "https:", "http:")
_missing = [name for name in _REQUIRED if env(name, default="").strip().rstrip("/") in _EMPTY]
if _missing:
    raise ImproperlyConfigured(
        f"Missing required environment variables: {', '.join(_missing)} "
        "(Railway: generate a domain; ${{<service>.DATABASE_URL}} must name your Postgres service)"
    )
_placeholders = [
    name
    for name in ("SECRET_KEY", "ADMIN_URL_PATH")
    if re.fullmatch(r"<.*>", env(name, default="").strip(), flags=re.DOTALL)
]
if _placeholders:
    _names = ", ".join(_placeholders)
    raise ImproperlyConfigured(f"Fill in real values instead of the <placeholder> text for: {_names}.")
if not re.fullmatch(r"[a-z0-9][a-z0-9-]{3,63}", ADMIN_URL_PATH):
    raise ImproperlyConfigured("ADMIN_URL_PATH must use only lowercase letters, digits and '-' (4-64 chars).")
if env.bool("DEBUG", default=False):
    raise ImproperlyConfigured("DEBUG must be false in production.")
if env("SECRET_KEY").startswith(("CHANGE_ME", "insecure")) or len(env("SECRET_KEY")) < 50:
    raise ImproperlyConfigured("SECRET_KEY must be a random value of at least 50 characters.")

DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_REDIRECT_EXEMPT = [r"^healthz$", r"^readyz$", r"^metrics$"]
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
