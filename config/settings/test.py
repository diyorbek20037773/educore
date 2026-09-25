"""Test settings: mock AI enforced, no network, fast hashing, isolated caches."""

from __future__ import annotations

from config.settings.base import *  # noqa: F403
from config.settings.base import BASE_DIR

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"  # noqa: S105
ALLOWED_HOSTS = ["*"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# The real provider must never be called from tests (AI_PIPELINE §4). Not overridable by env.
AI_PROVIDER = "mock"
ANTHROPIC_API_KEY = ""
OPS_TELEGRAM_BOT_TOKEN = ""
OPS_TELEGRAM_CHAT_ID = ""
SENTRY_DSN = ""
TELEGRAM_API_ID = 0
TELEGRAM_API_HASH = ""

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "educore-test"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

MEDIA_ROOT = BASE_DIR / "data" / "test-media"
PRIVATE_ROOT = BASE_DIR / "data" / "test-private"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
AXES_ENABLED = False
RATELIMIT_ENABLE = True
