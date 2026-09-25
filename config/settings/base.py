"""Base settings shared by every environment. All configuration comes from the environment.

`.env.example` is the authoritative contract for every variable read here.
"""

from __future__ import annotations

from pathlib import Path

import django.conf.locale
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(str(_env_file), overwrite=False)

# --- Core ------------------------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", default="insecure-dev-only-key-change-me")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS: list[str] = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS: list[str] = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SITE_URL: str = env("SITE_URL", default="http://localhost:8000").rstrip("/")
ADMIN_URL_PATH: str = env("ADMIN_URL_PATH", default="boshqaruv-7f3a9c").strip("/")
ADMIN_IP_ALLOWLIST: list[str] = env.list("ADMIN_IP_ALLOWLIST", default=[])
TRUSTED_PROXY_CIDRS: list[str] = env.list("TRUSTED_PROXY_CIDRS", default=["172.16.0.0/12"])
METRICS_IP_ALLOWLIST: list[str] = env.list("METRICS_IP_ALLOWLIST", default=["127.0.0.1/32", "172.16.0.0/12"])

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SITE_ID = 1

# --- Applications ----------------------------------------------------------------------------------
DJANGO_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.simple_history",
    "modeltranslation",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
]
THIRD_PARTY_APPS = [
    "django_htmx",
    "django_tailwind_cli",
    "django_celery_beat",
    "django_celery_results",
    "django_otp",
    "django_otp.plugins.otp_static",
    "django_otp.plugins.otp_totp",
    "two_factor",
    "axes",
    "simple_history",
    "django_prometheus",
    "corsheaders",
    "csp",
    "django_structlog",
]
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.institutions",
    "apps.telegram",
    "apps.ai",
    "apps.content",
    "apps.appeals",
    "apps.analytics",
    "apps.web",
    "apps.api",
    "apps.ops",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django_structlog.middlewares.RequestMiddleware",
    "axes.middleware.AxesMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "csp.context_processors.nonce",
            ],
        },
    },
]

# --- Database --------------------------------------------------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL", default="postgres://educore:educore@localhost:5432/educore")}
DATABASES["default"]["CONN_MAX_AGE"] = 0
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
if env.bool("DATABASE_POOL", default=False):
    # Web process only: psycopg's pool is not fork-safe under Celery prefork (SPEC NFR-PERF-2).
    DATABASES["default"].setdefault("OPTIONS", {})["pool"] = {
        "min_size": env.int("DATABASE_POOL_MIN", default=2),
        "max_size": env.int("DATABASE_POOL_MAX", default=10),
    }

# --- Redis: broker/locks (noeviction) and cache (allkeys-lru) --------------------------------------
REDIS_URL: str = env("REDIS_URL", default="redis://localhost:6379/0")
CACHE_URL: str = env("CACHE_URL", default="redis://localhost:6380/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": CACHE_URL,
        "KEY_PREFIX": "educore",
        "TIMEOUT": 300,
    }
}

# --- Auth ------------------------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "two_factor:login"
LOGIN_REDIRECT_URL = "admin:index"
SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 0.5  # hours = 30 min
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_IPWARE_PROXY_COUNT = 1

# --- i18n / time -----------------------------------------------------------------------------------
LANGUAGE_CODE = "uz"
LANGUAGES = [
    ("uz", "Oʻzbekcha"),
    ("uz-cyrl", "Ўзбекча"),
    ("ru", "Русский"),
    ("en", "English"),
]
django.conf.locale.LANG_INFO.setdefault(
    "uz-cyrl",
    {"bidi": False, "code": "uz-cyrl", "name": "Uzbek (Cyrillic)", "name_local": "Ўзбекча"},
)
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = env("TIME_ZONE", default="Asia/Tashkent")
USE_I18N = True
USE_TZ = True

MODELTRANSLATION_DEFAULT_LANGUAGE = "uz"
MODELTRANSLATION_LANGUAGES = ("uz", "uz-cyrl", "ru", "en")
MODELTRANSLATION_FALLBACK_LANGUAGES = {"default": ("uz",)}

# --- Static & media --------------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "data" / "media")))
PRIVATE_ROOT = Path(env("PRIVATE_ROOT", default=str(BASE_DIR / "data" / "private")))
MEDIA_BACKEND: str = env("MEDIA_BACKEND", default="local")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
if MEDIA_BACKEND == "s3":
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "endpoint_url": env("S3_ENDPOINT_URL", default=None),
            "bucket_name": env("S3_BUCKET", default=""),
            "access_key": env("S3_ACCESS_KEY", default=""),
            "secret_key": env("S3_SECRET_KEY", default=""),
            "region_name": env("S3_REGION", default=None),
            "custom_domain": env("S3_PUBLIC_URL", default="").replace("https://", "") or None,
            "querystring_auth": False,
            "file_overwrite": False,
        },
    }
FILE_UPLOAD_PERMISSIONS = 0o640

TAILWIND_CLI_SRC_CSS = "assets/css/input.css"  # outside STATICFILES_DIRS (ADR-013)
TAILWIND_CLI_DIST_CSS = "css/output.css"

# --- Celery ----------------------------------------------------------------------------------------
CELERY_BROKER_URL: str = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND: str = env("CELERY_RESULT_BACKEND", default="django-db")
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_EXPIRES = 24 * 60 * 60
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_TRANSPORT_OPTIONS = {"visibility_timeout": 3600}
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_WORKER_HIJACK_ROOT_LOGGER = False

# --- Telegram --------------------------------------------------------------------------------------
TELEGRAM_API_ID: int = env.int("TELEGRAM_API_ID", default=0)
TELEGRAM_API_HASH: str = env("TELEGRAM_API_HASH", default="")
TELEGRAM_PHONE: str = env("TELEGRAM_PHONE", default="")
TELEGRAM_SESSION_PATH: str = env("TELEGRAM_SESSION_PATH", default=str(BASE_DIR / "data" / "telegram" / "educore"))
TELEGRAM_BACKFILL_LIMIT: int = env.int("TELEGRAM_BACKFILL_LIMIT", default=500)
BACKFILL_AI_LIMIT_PER_SOURCE: int = env.int("BACKFILL_AI_LIMIT_PER_SOURCE", default=150)
TELEGRAM_BACKFILL_MAX_MEDIA_MB: int = env.int("TELEGRAM_BACKFILL_MAX_MEDIA_MB", default=20)
TELEGRAM_MAX_MEDIA_MB: int = env.int("TELEGRAM_MAX_MEDIA_MB", default=200)
TELEGRAM_MEDIA_CONCURRENCY: int = env.int("TELEGRAM_MEDIA_CONCURRENCY", default=2)

# --- AI --------------------------------------------------------------------------------------------
AI_PROVIDER: str = env("AI_PROVIDER", default="mock")
ANTHROPIC_API_KEY: str = env("ANTHROPIC_API_KEY", default="")
AI_MODEL: str = env("AI_MODEL", default="claude-sonnet-5")
AI_MODEL_FAST: str = env("AI_MODEL_FAST", default="claude-haiku-4-5-20251001")
AI_DAILY_USD_BUDGET: float = env.float("AI_DAILY_USD_BUDGET", default=5.0)
AI_TRANSLATE_TO: list[str] = env.list("AI_TRANSLATE_TO", default=["ru", "en"])
AI_PRICING_JSON: str = env("AI_PRICING_JSON", default="")
EMBEDDING_MODEL: str = env("EMBEDDING_MODEL", default="intfloat/multilingual-e5-small")
FASTEMBED_CACHE_DIR: str = env("FASTEMBED_CACHE_DIR", default=str(BASE_DIR / ".cache" / "fastembed"))
PROMPT_VERSION_OVERRIDE: str = env("PROMPT_VERSION_OVERRIDE", default="")

# --- Publishing policy (SiteSetting overrides) -----------------------------------------------------
PUBLISH_MODE: str = env("PUBLISH_MODE", default="review")
PUBLISH_CONFIDENCE_THRESHOLD: float = env.float("PUBLISH_CONFIDENCE_THRESHOLD", default=0.75)
ON_SOURCE_DELETE: str = env("ON_SOURCE_DELETE", default="archive")

# --- Email -----------------------------------------------------------------------------------------
vars().update(env.email_url("EMAIL_URL", default="smtp://localhost:1025"))
DEFAULT_FROM_EMAIL: str = env("DEFAULT_FROM_EMAIL", default="Educore <noreply@example.uz>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
APPEALS_NOTIFY_EMAILS: list[str] = env.list("APPEALS_NOTIFY_EMAILS", default=[])

# --- Security / anti-abuse -------------------------------------------------------------------------
TURNSTILE_SITE_KEY: str = env("TURNSTILE_SITE_KEY", default="")
TURNSTILE_SECRET_KEY: str = env("TURNSTILE_SECRET_KEY", default="")
CORS_ALLOWED_ORIGINS: list[str] = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_URLS_REGEX = r"^/api/.*$"
CORS_ALLOW_METHODS = ("GET", "OPTIONS", "POST")
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
RATELIMIT_USE_CACHE = "default"

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'"],
        "script-src": ["'self'", "https://challenges.cloudflare.com"],
        "style-src": ["'self'"],
        "img-src": ["'self'", "data:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "frame-src": ["https://challenges.cloudflare.com"],
        "frame-ancestors": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "object-src": ["'none'"],
    },
}

# --- Ops / observability ---------------------------------------------------------------------------
OPS_TELEGRAM_BOT_TOKEN: str = env("OPS_TELEGRAM_BOT_TOKEN", default="")
OPS_TELEGRAM_CHAT_ID: str = env("OPS_TELEGRAM_CHAT_ID", default="")
SENTRY_DSN: str = env("SENTRY_DSN", default="")
LOG_LEVEL: str = env("LOG_LEVEL", default="INFO")
PROMETHEUS_EXPORT_MIGRATIONS = False

# --- Unfold admin ----------------------------------------------------------------------------------
UNFOLD = {
    "SITE_TITLE": "EDUCORE",
    "SITE_HEADER": "EDUCORE boshqaruv paneli",
    "SITE_SYMBOL": "school",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "COLORS": {
        "primary": {
            "50": "232 238 248",
            "100": "232 238 248",
            "200": "197 211 235",
            "300": "148 172 214",
            "400": "92 126 184",
            "500": "43 88 160",
            "600": "27 58 107",
            "700": "27 58 107",
            "800": "18 41 77",
            "900": "11 31 58",
            "950": "7 20 38",
        },
    },
}

TWO_FACTOR_PATCH_ADMIN = False
OTP_TOTP_ISSUER = "EDUCORE"

