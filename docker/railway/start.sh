#!/bin/bash
# Railway (temporary hosting, ADR-027): one service runs every EDUCORE process so they share one volume
# (/data: media, private attachments, Telegram session). Railway restarts the container if web, a worker
# or beat exits; the optional ingestor is restarted in place and never takes the site down.
set -euo pipefail

mkdir -p /data/media /data/private /data/telegram /data/fastembed /tmp/prom

# Empty values and `<…>` / CHANGE_ME hints copied from docs/RAILWAY.md count as "not set" (ADR-032).
is_unset() {
    case "${1:-}" in "" | "<"* | CHANGE_ME*) return 0 ;; *) return 1 ;; esac
}
if [ -z "${RAILWAY_VOLUME_MOUNT_PATH:-}" ]; then
    echo "railway: WARNING no volume attached at /data: media, Telegram session and generated keys are lost on redeploy" >&2
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

pids=()
celery -A config worker -Q ingest,default,media -c 2 -Ofair -n worker@%h --loglevel INFO &
pids+=($!)
celery -A config worker -Q ai -c 1 -Ofair -n worker-ai@%h --loglevel INFO &
pids+=($!)
celery -A config beat -S django_celery_beat.schedulers:DatabaseScheduler --loglevel INFO &
pids+=($!)

if [ "${RUN_INGESTOR:-0}" = "1" ]; then
    (
        while true; do
            python manage.py telegram_ingest || echo "railway: ingestor exited ($?), restarting in 60 s"
            sleep 60
        done
    ) &
fi

gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" \
    --threads 4 --timeout 60 --access-logfile - &
pids+=($!)

trap 'kill -TERM "${pids[@]}" 2>/dev/null; wait' TERM INT
# Exit (→ Railway restart) as soon as any core process dies.
wait -n "${pids[@]}" || true
echo "railway: a core process exited, stopping the container" >&2
kill -TERM "${pids[@]}" 2>/dev/null || true
wait
exit 1
