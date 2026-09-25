# EDUCORE — DevOps, Infrastructure & Operations

Target: **one VPS, Docker Compose, one command to deploy, one command to restore.** Everything here is a
requirement for Phase 8 unless marked optional.

---

## 1. Environments

| Env | Where | Settings | Notes |
|---|---|---|---|
| dev | developer laptop, `compose.yaml` | `config.settings.dev` | hot reload (`runserver`), mailpit, `AI_PROVIDER=mock` default |
| test | CI + local `make test` | `config.settings.test` | Postgres+Redis services, mock provider enforced, `AI_PROVIDER` override impossible |
| prod | VPS `/opt/educore`, `compose.prod.yaml` | `config.settings.prod` | Caddy TLS, non‑root containers, backups, monitoring |

Settings: `django-environ`; `base.py` reads env with typed defaults; `prod.py` refuses to start if
`SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL`, `REDIS_URL`, `SITE_URL` are missing or `DEBUG=True`.

## 2. `.env.example` (authoritative contract — keep in sync with code)

```
# Django
DJANGO_SETTINGS_MODULE=config.settings.dev
SECRET_KEY=CHANGE_ME_50_random_chars
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1
SITE_URL=http://localhost:8000
CSRF_TRUSTED_ORIGINS=http://localhost:8000
TIME_ZONE=Asia/Tashkent
ADMIN_URL_PATH=boshqaruv-7f3a9c        # change in prod
ADMIN_IP_ALLOWLIST=                    # optional, comma-separated CIDRs

# Data stores
DATABASE_URL=postgres://educore:educore@db:5432/educore   # never add ?conn_max_age= (pooling needs 0)
DATABASE_POOL=false                    # true ONLY in the web service (compose sets it); pool is not fork-safe
DATABASE_POOL_MIN=2
DATABASE_POOL_MAX=10
REDIS_URL=redis://redis:6379/0         # locks, heartbeat, rate limits (noeviction instance)
CACHE_URL=redis://redis-cache:6379/0   # Django cache (allkeys-lru instance)
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=django-db
TRUSTED_PROXY_CIDRS=172.16.0.0/12      # the compose network; X-Forwarded-For honoured only from here
PRIVATE_ROOT=/data/private             # appeal attachments; never served by Caddy

# Telegram (MTProto user session)
TELEGRAM_API_ID=0
TELEGRAM_API_HASH=CHANGE_ME
TELEGRAM_PHONE=+998XXXXXXXXX
TELEGRAM_SESSION_PATH=/data/telegram/educore.session
TELEGRAM_BACKFILL_LIMIT=500
BACKFILL_AI_LIMIT_PER_SOURCE=150
TELEGRAM_BACKFILL_MAX_MEDIA_MB=20      # for backfill posts beyond the AI limit: photos only, this size cap
TELEGRAM_MAX_MEDIA_MB=200
TELEGRAM_MEDIA_CONCURRENCY=2

# AI
AI_PROVIDER=mock                      # mock | anthropic
ANTHROPIC_API_KEY=
AI_MODEL=claude-sonnet-5
AI_MODEL_FAST=claude-haiku-4-5-20251001
AI_DAILY_USD_BUDGET=5
AI_TRANSLATE_TO=ru,en                 # empty to disable AI translations
AI_PRICING_JSON=                      # optional override {"model": {"in": 2, "out": 10}}
EMBEDDING_MODEL=intfloat/multilingual-e5-small
PROMPT_VERSION_OVERRIDE=              # optional

# Publishing policy (SiteSetting in admin overrides these)
PUBLISH_MODE=review                   # auto | review | off — start prod in `review`; switch to `auto` in admin after the golden-set check
PUBLISH_CONFIDENCE_THRESHOLD=0.75
ON_SOURCE_DELETE=archive              # archive | keep

# Media / storage
MEDIA_BACKEND=local                   # local | s3
MEDIA_ROOT=/data/media
S3_ENDPOINT_URL=
S3_BUCKET=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_REGION=
S3_PUBLIC_URL=

# Email
EMAIL_URL=smtp://mailpit:1025         # prod: smtp+tls://user:pass@host:587
DEFAULT_FROM_EMAIL=Educore <noreply@example.uz>
APPEALS_NOTIFY_EMAILS=

# Security / anti-abuse
TURNSTILE_SITE_KEY=
TURNSTILE_SECRET_KEY=
CORS_ALLOWED_ORIGINS=

# Ops
OPS_TELEGRAM_BOT_TOKEN=
OPS_TELEGRAM_CHAT_ID=
SENTRY_DSN=
METRICS_IP_ALLOWLIST=127.0.0.1/32,172.16.0.0/12
PROMETHEUS_MULTIPROC_DIR=/tmp/prom
LOG_LEVEL=INFO

# Backups (prod)
BACKUP_S3_ENDPOINT_URL=
BACKUP_S3_BUCKET=
BACKUP_S3_ACCESS_KEY=
BACKUP_S3_SECRET_KEY=
BACKUP_AGE_RECIPIENT=age1...           # owner's age public key (age -r); private key kept offline by the owner

# Deploy (GitHub secrets, not in .env): DEPLOY_HOST, DEPLOY_USER, DEPLOY_SSH_KEY, GHCR_PAT (read:packages)
```

## 3. Docker image (`Dockerfile`, multi‑stage)

1. `base`: `python:3.12-slim-bookworm`; apt: `libpq5 ffmpeg libmagic1 curl tini`; create user `app` (uid 10001);
   `WORKDIR /app`; env `PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1`.
2. `builder`: install `uv` (copy from `ghcr.io/astral-sh/uv:latest`), `uv sync --frozen --no-dev` into `/app/.venv`
   (build deps: `build-essential libpq-dev`); download the Tailwind standalone binary (`django-tailwind-cli`
   does this: run `manage.py tailwind build` here so the CSS is in the image); `collectstatic --noinput`
   with a dummy `SECRET_KEY`; pre‑download the fastembed model into `/app/.cache/fastembed`.
3. `final`: copy `.venv`, source, `staticfiles`, fastembed cache; `USER app`; `ENTRYPOINT ["tini","--","/app/docker/entrypoint.sh"]`;
   default `CMD ["gunicorn", …]`; `HEALTHCHECK` `curl -fsS http://127.0.0.1:8000/healthz | grep -q '"ok"'`
   (web only — compose overrides per service; `/healthz` is answered by `HealthMiddleware` for any `Host` and is
   exempt from the SSL redirect, so this works inside the container).
   Labels: `org.opencontainers.image.revision=$GIT_SHA`. Image ≤ 900 MB (onnxruntime + ffmpeg).
   `.dockerignore` excludes `.git`, `.env*`, `docs`, `tests`, `node_modules`, `*.session`.

`docker/entrypoint.sh`: waits for DB and Redis (max 60 s), then `exec "$@"`. It never runs migrations
(the `migrate` service does).

## 4. Compose

### 4.1 `compose.yaml` (dev)
Services: `db` (pgvector/pgvector:pg17, `docker/postgres/init.sql` creating extensions, port 5432 → host),
`redis`, `redis-cache` (redis:7-alpine), `mailpit` (8025), `migrate` (one‑shot, `restart: "no"`), `web`
(`runserver 0.0.0.0:8000`, bind mount `.:/app`, port 8000), `worker`, `worker-ai`, `worker-media`, `beat`
(all `depends_on: migrate: condition: service_completed_successfully`), `ingestor` (profile `telegram` — only
starts with `--profile telegram` after `make tg-login`), `tailwind` (watch, profile `ui`), `flower` (profile `ops`).
Named volumes: `pgdata`, `redisdata`, `media`, `private`, `telegram_session`, `fastembed_cache`.
`make up` = `cp -n .env.example .env` (if missing) + `docker compose up -d --wait db redis redis-cache mailpit migrate
web worker worker-ai worker-media beat`.

### 4.2 `compose.prod.yaml`
Same services with prod settings; no host ports except Caddy 80/443; `restart: unless-stopped` for long‑running
services, **`restart: "no"` for `migrate`** (a restarting one‑shot never reaches "completed");
`deploy.resources.limits` (web 1.5 GB, worker 768 MB, worker-ai 1.5 GB, worker-media 1 GB, ingestor 1 GB, db 2 GB,
redis 512 MB with `maxmemory 400mb`, redis-cache 320 MB with `maxmemory 256mb`);
`read_only: true` + `tmpfs: /tmp` (holds `PROMETHEUS_MULTIPROC_DIR`) for `web`; `logging: json-file, max-size 50m, max-file 5`;
`healthcheck` per service (web: `/healthz`; worker: `celery inspect ping`; ingestor: heartbeat age via
`manage.py ingestor_health`; db: `pg_isready`; redis: `redis-cli ping`); `migrate` one‑shot with
`depends_on: db: service_healthy`; `web/worker/beat/ingestor depends_on: migrate: service_completed_successfully`;
`caddy` with `docker/caddy/Caddyfile`, volumes `caddy_data`, `caddy_config`, `media:ro` (the `private` volume is
**never** mounted into Caddy); static served by WhiteNoise, Caddy caches;
`backup` (image with `postgresql-client-17`, `rclone`, `age`; crontab `0 3 * * *`);
optional profile `monitoring`: `prometheus`, `grafana` (provisioned dashboards from `docker/grafana/`),
`celery-exporter` (`danihodovic/celery-exporter`), `node-exporter`, `uptime-kuma`; profile `errors`: none (Sentry is SaaS).
Image reference: `image: ghcr.io/<owner>/educore:${IMAGE_TAG:-latest}`.

### 4.3 `docker/caddy/Caddyfile`
```
{$SITE_DOMAIN} {
    encode zstd gzip
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy strict-origin-when-cross-origin
        Permissions-Policy "camera=(), microphone=(), geolocation=()"
        -Server
    }
    handle_path /media/* {
        root * /srv/media
        header Cache-Control "public, max-age=2592000"
        file_server
    }
    handle /static/* {
        header Cache-Control "public, max-age=31536000, immutable"
        reverse_proxy web:8000
    }
    handle {
        reverse_proxy web:8000 {
            lb_try_duration 30s
            health_uri /healthz
            health_interval 10s
        }
    }
    log {
        output file /var/log/caddy/access.log {
            roll_size 50mb
            roll_keep 5
        }
        format json
    }
}
# Only if a `www` DNS record exists (otherwise Caddy logs certificate failures):
# www.{$SITE_DOMAIN} {
#     redir https://{$SITE_DOMAIN}{uri} permanent
# }
```
Validate with `docker compose -f compose.prod.yaml run --rm caddy caddy validate --config /etc/caddy/Caddyfile`.

## 5. CI/CD (GitHub Actions)

### 5.1 `ci.yml` — on every push/PR
Jobs: `lint` (ruff check + format check, mypy soft), `test` (services: pgvector, redis; `uv sync`; `pytest --cov`
with coverage gates; upload `htmlcov` artifact; `manage.py makemigrations --check`; `manage.py check --deploy`
with prod settings and dummy env; `compilemessages` check), `security` (`pip-audit`, with a documented ignore list for accepted findings), `build` (docker build with
BuildKit cache, Trivy scan `--severity CRITICAL --ignore-unfixed --exit-code 1`), `lighthouse` (optional, on
`main` only, against a compose‑started site with `seed_demo`, budgets ≥ 90).

### 5.2 `deploy.yml` — on tag `v*` (or `workflow_dispatch`), environment `production` (add a required reviewer if the plan allows it)
1. Build & push `ghcr.io/<owner>/educore:{sha}` and `:latest`.
2. Copy `compose.prod.yaml`, `docker/`, `scripts/` to the VPS with `appleboy/scp-action` (no git clone on the
   server), then SSH (`appleboy/ssh-action` with `DEPLOY_SSH_KEY`): `cd /opt/educore && cp .image .image.prev;
   echo IMAGE_TAG={sha} > .image && echo "$GHCR_PAT" | docker login ghcr.io -u <owner> --password-stdin &&
   docker compose --env-file .env --env-file .image -f compose.prod.yaml pull && … up -d --remove-orphans --wait`
   (runs `migrate` first).
3. Smoke: `curl -fsS https://$SITE_DOMAIN/healthz` and `/readyz`; on failure → automatic rollback to the
   previous `.image` and alert; on success → ops bot message "Deployed {sha}".
Rollback manually: `scripts/deploy.sh rollback` (uses `.image.prev`).

## 6. Server provisioning (`scripts/server-setup.sh`, idempotent, Ubuntu 24.04 LTS)

Creates user `deploy` (sudo, SSH key only), disables password SSH and root login, installs Docker Engine +
compose plugin, `ufw` (allow 22, 80, 443; default deny), `fail2ban` (sshd), `unattended-upgrades`, 2 GB swap,
`sysctl` (`vm.overcommit_memory=1` for Redis, `net.core.somaxconn=1024`), `logrotate` for Caddy logs,
`chrony` (time sync — MTProto needs accurate time), timezone `Asia/Tashkent`, `/opt/educore` layout:
```
/opt/educore/{compose.prod.yaml, .env (600), .image, docker/, scripts/, backups/}
/var/lib/docker/volumes/{pgdata, media, telegram_session, caddy_data, ...}
```
Minimum size: 4 vCPU, 8 GB RAM, 80 GB NVMe. Recommended providers: any with Uzbekistan‑friendly latency;
the app is provider‑agnostic.

First‑time runbook (also in `docs/RUNBOOK.md`):
1. DNS A/AAAA → VPS; `SITE_DOMAIN` in `.env`.
2. `scripts/server-setup.sh` → reboot.
3. Copy `.env` (filled), `docker login ghcr.io` with the `GHCR_PAT`.
4. `docker compose -f compose.prod.yaml run --rm ingestor python manage.py telegram_login` (interactive once,
   with the ingestor service **not** running).
5. `docker compose -f compose.prod.yaml up -d --wait` → `createsuperuser` → set up 2FA → keep `publish_mode=review`.
6. `docker compose … exec worker python manage.py telegram_backfill` (inserts an `IngestionRequest`; the running
   ingestor executes it — progress in admin › Telegram › Requests). Temporarily raise `ai_daily_usd_budget` to 50
   in admin for the backfill day.
7. Verify backups ran (`ls backups/`), run `scripts/restore.sh --dry-run`.
8. After the golden‑set check and a week in `review`, switch `publish_mode` to `auto` in admin.

## 7. Backups & disaster recovery

`docker/backup/backup.sh` (03:00 daily, non‑interactive): `pg_dump -Fc` → `educore-YYYYmmdd.dump`; copy of the
Telegram session file and `private/` (appeal attachments); all encrypted with `age -r $BACKUP_AGE_RECIPIENT`
(public‑key mode — passphrase mode is TTY‑only and cannot run from cron; the owner keeps the private key offline);
local retention 7 days; `rclone copy` to `BACKUP_S3_BUCKET` retention 30 days (`rclone delete --min-age 30d`).
Media is **not** tarred locally (disk): `rclone sync media/ → S3` daily when S3 is configured, otherwise weekly
tar with 2 copies max. Success/failure → ops bot. `scripts/restore.sh <dump>` restores DB into a fresh
volume (with confirmation) and media; documented drill executed once in Phase 8 and recorded in `RUNBOOK.md`.
RPO 24 h, RTO 1 h (new VPS: setup script + restore + DNS).

## 8. Monitoring, logging, alerting

- Health: `/healthz` (DB ping, Redis ping) and `/readyz` (+ migrations applied, ingestor heartbeat age
  reported but not failing). Compose healthchecks restart unhealthy containers.
- Logs: structlog JSON to stdout; `docker compose logs -f <svc>`; Caddy access JSON; optional Loki not required.
- Metrics: `django-prometheus` (`/metrics` on `web`, `PROMETHEUS_MULTIPROC_DIR` on tmpfs, IP allowlist incl. the
  compose subnet) plus a custom **pull collector** in `apps/ops/metrics.py` that computes gauges at scrape time from
  DB/Redis (values produced in other containers cannot be pushed into the web process): `educore_posts_ingested_total{source}`
  (from DB counts), `educore_outbox_unprocessed`, `educore_outbox_dead`, `educore_ai_cost_usd_today`,
  `educore_ai_budget_remaining_usd`, `educore_ingestor_heartbeat_age_seconds`, `educore_source_status{source}`;
  task durations/queue depth from `celery-exporter`. Grafana dashboard JSON provisioned (optional profile).
- Alerts (ops bot, throttled): ingestor heartbeat stale, source degraded/offline, dead outbox events, AI budget
  exhausted, AI failure rate > 30 % over 15 min, backup failed, deploy done/failed, disk > 85 % (cron on host),
  new appeal (to moderators), article sent to review (daily digest at 09:00 + immediate for importance ≥ 4).
- Errors: Sentry when `SENTRY_DSN` set (web, workers, ingestor; PII scrubbing on).
- Uptime: `uptime-kuma` (optional) or external monitor hitting `/healthz`.

## 9. Hardening checklist (must all be true before go‑live)
- [ ] `manage.py check --deploy` clean; HSTS preload; CSP report‑only for 1 week then enforce.
- [ ] Admin path secret, 2FA enforced, axes lockout, session 12 h, `ADMIN_IP_ALLOWLIST` if feasible.
- [ ] DB/Redis not exposed; containers non‑root; `read_only` web; resource limits; log rotation.
- [ ] `.env` and session volume `600`; backups encrypted; passphrase stored offline by the owner.
- [ ] Rate limits on appeals/search/API; Turnstile on the appeal form; upload validation.
- [ ] `pip-audit` and Trivy green; Dependabot enabled (weekly, grouped).
- [ ] Restore drill executed; alert test executed (stop ingestor 4 min → alert; start → recovered).
- [ ] Legal pages published; attribution block on every AI article; `robots.txt` allows indexing; sitemap submitted.

## 10. Local developer experience
`make up` (creates `.env` from the example if missing, runs `migrate` before workers start) → `make seed-demo` →
open http://localhost:8000 and http://localhost:8000/boshqaruv-7f3a9c/ (admin, `admin@example.uz` / from
`make createsuperuser`). `make tailwind` in a second terminal for CSS. `make test` runs in < 3 min (inside the
`web` container: `docker compose exec web pytest`, so no host Python is required; host‑side `uv`/`ruff` are optional).
`pre-commit` runs ruff + ruff‑format + `check-added-large-files` + `detect-secrets`. Lighthouse needs Node ≥ 20 and
Chrome on the host (HA0) or the CI job.
