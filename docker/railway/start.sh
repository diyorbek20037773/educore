#!/bin/bash
# Railway (temporary hosting, ADR-027): one service runs every EDUCORE process so they share one volume
# (/data: media, private attachments, Telegram session). Workers, beat and the optional ingestor are restarted
# in place; Railway restarts the container only when the web server exits.
set -euo pipefail

mkdir -p /data/media /data/private /data/telegram /data/fastembed /tmp/prom

# Empty values and `<…>` / CHANGE_ME hints copied from docs/RAILWAY.md count as "not set" (ADR-032).
is_unset() {
    case "${1:-}" in "" | "<"* | CHANGE_ME*) return 0 ;; *) return 1 ;; esac
}
if [ -z "${RAILWAY_VOLUME_MOUNT_PATH:-}" ]; then
    echo "railway: WARNING no volume attached at /data: media, Telegram session and generated keys are lost on redeploy" >&2
fi

# Without DJANGO_SETTINGS_MODULE the code falls back to dev settings, whose database default is localhost:5432,
# so a service with no variables crashed with "connection refused". Railway always runs production settings.
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"
if is_unset "${DATABASE_URL:-}"; then
    echo "railway: ERROR DATABASE_URL is empty. Add a Postgres (pgvector) service and set" \
        "DATABASE_URL=\${{<postgres service>.DATABASE_URL}} on this service (docs/RAILWAY.md)" >&2
    exit 1
fi
if is_unset "${REDIS_URL:-}" && [ "${RUN_LOCAL_REDIS:-0}" != "1" ]; then
    echo "railway: ERROR REDIS_URL is empty. Add a Redis service and set REDIS_URL=\${{Redis.REDIS_URL}}/0," \
        "or set RUN_LOCAL_REDIS=1 (docs/RAILWAY.md)" >&2
    exit 1
fi

# RUN_LOCAL_REDIS=1 keeps Redis inside this container (ADR-035): for plans with no room for a Redis service.
if [ "${RUN_LOCAL_REDIS:-0}" = "1" ]; then
    redis-server --bind 127.0.0.1 --save "" --appendonly no --maxmemory 64mb --maxmemory-policy allkeys-lru &
fi

# Wait for Postgres/Redis (reuses the image entrypoint's check), then migrate + create-only seeds.
/app/docker/entrypoint.sh true
python manage.py migrate --noinput
python manage.py seed_all
if ! is_unset "${DJANGO_SUPERUSER_EMAIL:-}" && ! is_unset "${DJANGO_SUPERUSER_PASSWORD:-}"; then
    python manage.py createsuperuser --noinput >/dev/null 2>&1 \
        && echo "railway: superuser ${DJANGO_SUPERUSER_EMAIL} created" \
        || echo "railway: superuser ${DJANGO_SUPERUSER_EMAIL} already exists"
else
    echo "railway: DJANGO_SUPERUSER_EMAIL / DJANGO_SUPERUSER_PASSWORD not set to real values; no admin user created" >&2
fi
admin_path="${ADMIN_URL_PATH:-}"
admin_path="${admin_path#/}"
admin_path="${admin_path%/}"
admin_path="${admin_path,,}"
if { is_unset "$admin_path" || ! [[ "$admin_path" =~ ^[a-z0-9][a-z0-9-]{3,63}$ ]]; } \
    && [ -s "${RAILWAY_VOLUME_MOUNT_PATH:-/data}/.admin_url_path" ]; then
    echo "railway: ADMIN_URL_PATH not set; admin panel is at /$(cat "${RAILWAY_VOLUME_MOUNT_PATH:-/data}/.admin_url_path")/"
fi
if [ "${SEED_DEMO:-0}" = "1" ]; then
    python manage.py seed_demo
fi

# Celery and the ingestor are restarted in place, so a short Postgres/Redis outage never takes the site down.
# Only the web server is "core": when gunicorn exits, every child is stopped and the container exits non-zero,
# so Railway's ON_FAILURE policy restarts it.
supervise() {
    local name=$1 delay=$2
    shift 2
    while true; do
        local code=0
        "$@" || code=$?
        echo "railway: $name exited ($code), restarting in ${delay} s" >&2
        sleep "$delay"
    done
}
stop_children() {
    trap - TERM INT
    kill -TERM 0 2>/dev/null || true
    wait || true
}
trap 'stop_children; exit 0' TERM INT

# RUN_WORKERS=0 serves the site only (ADR-035): for Railway's Free plan, where 0.5 GB does not fit Celery.
if [ "${RUN_WORKERS:-1}" = "1" ]; then
    supervise worker 10 celery -A config worker -Q ingest,default,media -c 2 -Ofair -n worker@%h --loglevel INFO &
    supervise worker-ai 10 celery -A config worker -Q ai -c 1 -Ofair -n worker-ai@%h --loglevel INFO &
    supervise beat 10 celery -A config beat -S django_celery_beat.schedulers:DatabaseScheduler --loglevel INFO &
else
    echo "railway: RUN_WORKERS=0, background tasks are queued but not processed" >&2
fi
if [ "${RUN_INGESTOR:-0}" = "1" ]; then
    supervise ingestor 60 python manage.py telegram_ingest &
fi

gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}"     --threads 4 --timeout 60 --access-logfile - &
web_pid=$!
wait "$web_pid" || true
echo "railway: web server exited, stopping the container" >&2
stop_children
exit 1
