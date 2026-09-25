"""Celery application: queues `ingest`, `ai`, `media`, `default` (CLAUDE.md §3, §11)."""

from __future__ import annotations

import os

from celery import Celery
from kombu import Exchange, Queue

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("educore")
app.config_from_object("django.conf:settings", namespace="CELERY")

_default_exchange = Exchange("default", type="direct")
app.conf.task_queues = (
    Queue("default", _default_exchange, routing_key="default"),
    Queue("ingest", _default_exchange, routing_key="ingest"),
    Queue("ai", _default_exchange, routing_key="ai"),
    Queue("media", _default_exchange, routing_key="media"),
)
app.conf.task_default_queue = "default"
app.conf.task_default_exchange = "default"
app.conf.task_default_routing_key = "default"
app.conf.task_routes = {
    "telegram.relay_outbox": {"queue": "ingest"},
    "telegram.request_*": {"queue": "ingest"},
    "telegram.cleanup_outbox": {"queue": "default"},
    "media.*": {"queue": "media"},
    "ai.prune_runs": {"queue": "default"},
    "ai.*": {"queue": "ai"},
}

app.autodiscover_tasks()


@app.task(name="core.ping", ignore_result=False)
def ping() -> str:
    """Liveness probe task used by smoke tests and `celery inspect`."""
    return "pong"
