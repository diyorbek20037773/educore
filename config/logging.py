"""structlog + stdlib logging configuration: JSON lines to stdout (CLAUDE.md §7)."""

from __future__ import annotations

from typing import Any

import structlog

SHARED_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
]


def build_logging(level: str, json: bool = True) -> dict[str, Any]:
    """Return a ``LOGGING`` dict routing stdlib and structlog records through one JSON renderer."""
    renderer: Any = structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.format_exc_info,
                    renderer,
                ],
                "foreign_pre_chain": SHARED_PROCESSORS,
            },
        },
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "structured"}},
        "root": {"handlers": ["console"], "level": level},
        "loggers": {
            "django.db.backends": {"level": "WARNING"},
            "django.server": {"level": "WARNING"},
            "celery": {"level": level},
            "telethon": {"level": "WARNING"},
            "httpx": {"level": "WARNING"},
        },
    }


def configure_structlog() -> None:
    """Configure structlog to hand records to stdlib logging (rendered by the formatter above)."""
    structlog.configure(
        processors=[
            *SHARED_PROCESSORS,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
