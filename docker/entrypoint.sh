#!/bin/sh
# Wait for PostgreSQL and Redis (max 60 s), then exec the container command.
# Migrations are never run here: the one-shot `migrate` service owns them.
# SKIP_WAIT=1 skips the wait (lint/format/tailwind runs that need no database).
set -eu

if [ "${SKIP_WAIT:-0}" = "1" ]; then exec "$@"; fi

python - <<'PY'
import os
import sys
import time
from urllib.parse import urlparse

import psycopg
import redis

deadline = time.monotonic() + 60
db_url = os.environ.get("DATABASE_URL", "")
redis_url = os.environ.get("REDIS_URL", "")


def wait(name, check):
    while True:
        try:
            check()
            return
        except Exception as exc:  # noqa: BLE001 - any failure means "not ready yet"
            if time.monotonic() > deadline:
                print(f"entrypoint: {name} not reachable after 60 s: {exc}", file=sys.stderr)
                sys.exit(1)
            time.sleep(1)


if db_url:
    wait("postgres", lambda: psycopg.connect(db_url, connect_timeout=3).close())
if redis_url:
    wait("redis", lambda: redis.Redis.from_url(redis_url, socket_connect_timeout=3).ping())
print(f"entrypoint: dependencies ready ({urlparse(db_url).hostname or '-'}, {urlparse(redis_url).hostname or '-'})")
PY

exec "$@"
