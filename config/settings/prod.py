"""Production settings. Refuses to start with missing secrets or DEBUG enabled."""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from config.settings.base import *  # noqa: F403
from config.settings.base import env

_REQUIRED = ("SECRET_KEY", "ALLOWED_HOSTS", "DATABASE_URL", "REDIS_URL", "SITE_URL")
_missing = [name for name in _REQUIRED if not env(name, default="")]
if _missing:
    raise ImproperlyConfigured(f"Missing required environment variables: {', '.join(_missing)}")
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
