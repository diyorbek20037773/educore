# Railway deployment (temporary)

EDUCORE runs on Railway until the VPS is ready (Phase 8). Design and trade-offs: `docs/DECISIONS.md` ADR-027.
Nothing here changes the VPS setup (`compose.prod.yaml`, Caddy, `docs/DEVOPS.md`).

## Topology

| Railway service | Source | Notes |
|---|---|---|
| `educore` | this GitHub repo (`railway.json` → `Dockerfile`, start `docker/railway/start.sh`) | web + Celery workers + beat (+ optional ingestor); volume at `/data` |
| `pgvector` | Railway template **pgvector** (PostgreSQL with the `vector` extension) | the plain Postgres template lacks pgvector |
| `Redis` | Railway template **Redis** | broker db 1, locks db 0, cache db 2 |

## First deployment

1. Railway → **New Project** → **Deploy from GitHub repo** → `diyorbek20037773/educore` (branch `main`).
   Railway reads `railway.json` and builds the `Dockerfile`.
2. In the same project: **+ Create** → **Database / Template** → search **pgvector** → deploy.
   Then **+ Create** → **Database** → **Redis**.
3. Add a volume mounted at `/data` to `educore` (volumes are not under the service Settings): right-click the
   `educore` card on the project canvas → **Attach Volume**, or **Ctrl/Cmd + K** → "Create Volume", or
   **+ Create → Volume** → pick `educore`; enter mount path `/data`.
4. `educore` service → **Settings → Networking** → **Generate Domain** (gives `*.up.railway.app`).
5. `educore` service → **Variables** → **Raw Editor**, paste and fill (service names in `${{…}}` must match yours):

```
DJANGO_SETTINGS_MODULE=config.settings.prod
RAILWAY_RUN_UID=0
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(64))">
ALLOWED_HOSTS=${{RAILWAY_PUBLIC_DOMAIN}}
SITE_URL=https://${{RAILWAY_PUBLIC_DOMAIN}}
CSRF_TRUSTED_ORIGINS=https://${{RAILWAY_PUBLIC_DOMAIN}}
ADMIN_URL_PATH=<secret-admin-path, e.g. boshqaruv-7x3k: lowercase letters, digits, dashes>
DATABASE_URL=${{pgvector.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}/0
CELERY_BROKER_URL=${{Redis.REDIS_URL}}/1
CACHE_URL=${{Redis.REDIS_URL}}/2
TRUSTED_PROXY_CIDRS=0.0.0.0/0,::/0
MEDIA_ROOT=/data/media
PRIVATE_ROOT=/data/private
TELEGRAM_SESSION_PATH=/data/telegram/educore.session
FASTEMBED_CACHE_DIR=/data/fastembed
SERVE_MEDIA=true
EMAIL_URL=consolemail://
AI_PROVIDER=mock
PUBLISH_MODE=auto
SEED_DEMO=1
RUN_INGESTOR=0
WEB_CONCURRENCY=2
DJANGO_SUPERUSER_EMAIL=<admin e-mail>
DJANGO_SUPERUSER_PASSWORD=<strong password>
```

   `ALLOWED_HOSTS`, `SITE_URL` and `CSRF_TRUSTED_ORIGINS` may be omitted: prod settings derive them from
   `RAILWAY_PUBLIC_DOMAIN` (step 4 must be done first). For `DATABASE_URL`, prefer **+ New Variable → Add
   Reference** and pick the Postgres service's `DATABASE_URL`, so the service name is always right.
   If the service's **Settings → Deploy → Custom Start Command** is empty and `railway.json` is not applied, the
   image entrypoint still switches to `docker/railway/start.sh` on Railway (`RAILWAY_ENVIRONMENT` is set).
6. Deploy. The first start migrates, seeds, creates the superuser and (with `SEED_DEMO=1`) the demo articles;
   the health check (`/healthz`) turns green after that (timeout 600 s).
7. Open `https://<domain>/` and `https://<domain>/<ADMIN_URL_PATH>/` → log in → set up TOTP 2FA.
   Afterwards remove `DJANGO_SUPERUSER_PASSWORD` from the variables.

## Real data (when the keys arrive)

- **AI (HA3):** `AI_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=…`, `AI_DAILY_USD_BUDGET=…`; set `SEED_DEMO=0`
  and archive the demo articles in admin.
- **Telegram (HA2):** add `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_PHONE`; then, with the Railway CLI,
  `railway ssh` into the `educore` service and run `python manage.py telegram_login` (enter the code sent to
  Telegram). Set `RUN_INGESTOR=1` and redeploy. Backfill: admin → Sources → "backfill".
- **E-mail (HA7):** `EMAIL_URL=smtp+tls://user:pass@smtp.example.uz:587`, `DEFAULT_FROM_EMAIL`,
  `APPEALS_NOTIFY_EMAILS`. **Alerts:** `OPS_TELEGRAM_BOT_TOKEN`, `OPS_TELEGRAM_CHAT_ID`.
  **Turnstile:** `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`.
- **Custom domain:** Settings → Networking → Custom Domain, add the CNAME at the DNS provider, then add the domain to
  `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and `SITE_URL`.

## Operations

- Logs: service → **Deployments → View logs** (JSON lines; `railway:` lines come from the start script).
- Shell / management commands: `railway ssh` then `python manage.py <command>`.
- Every push to `main` redeploys automatically. Roll back: **Deployments** → previous deployment → **Redeploy**.
- Backups: the pgvector service → **Backups** (Railway volume snapshots); the nightly `age`-encrypted backup job
  is part of the VPS setup only.

## Verified locally

The same image was started the way Railway runs it (`--user 0`, `DJANGO_SETTINGS_MODULE=config.settings.prod`,
`PORT=8080`, a fresh database without pre-installed extensions): migrations and seeds ran, 38 demo articles were
published by the mock pipeline, `/healthz`, `/readyz`, `/`, `/ru/`, `/murojaat/`, `/yangiliklar/`, `/sitemap.xml`,
static CSS and media WebP returned 200, both Celery workers answered `inspect ping`; memory ≈ 650 MB.
