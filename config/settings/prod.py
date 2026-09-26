"""Production settings. Refuses to start with missing secrets or DEBUG enabled."""

from __future__ import annotations

import os

from django.core.exceptions import ImproperlyConfigured

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
from config.settings.base import env  # noqa: E402

_REQUIRED = ("SECRET_KEY", "ALLOWED_HOSTS", "DATABASE_URL", "REDIS_URL", "SITE_URL")
_EMPTY = ("", "https:", "http:")
_missing = [name for name in _REQUIRED if env(name, default="").strip().rstrip("/") in _EMPTY]
if _missing:
    raise ImproperlyConfigured(
        f"Missing required environment variables: {', '.join(_missing)} "
        "(Railway: generate a domain; ${{<service>.DATABASE_URL}} must name your Postgres service)"
    )
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
