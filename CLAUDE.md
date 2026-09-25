# EDUCORE — CLAUDE.md (project constitution)

> **Read this file first in every session.** Then read `docs/PROGRESS.md` and continue from the first
> unchecked item. Detailed specifications live in `docs/`. Rules in this file override everything
> except explicit instructions from the owner (Marjona, sole developer).

---

## 1. What we are building

**Educore** — the unified, official information & analytics web platform of five law‑enforcement
education institutions of the Republic of Uzbekistan. It aggregates their official Telegram channels in
real time, turns every post into a structured, professionally written article with an AI editorial
pipeline, and presents everything as a Times‑Higher‑Education‑style "institutional intelligence"
dashboard (news, institutions, programs, admissions, students/cadets, professions, events, motivation,
analytics, appeals).

| order | Institution (official short name) | Slug | Telegram source | Color (validated, see SPEC §7.4) |
|---|---|---|---|---|
| 1 | FVV Akademiyasi (Favqulodda vaziyatlar vazirligi Akademiyasi) | `fvv-akademiyasi` | `@fvvakad_uz` | `#E4552F` |
| 2 | IIV Akademiyasi (Ichki ishlar vazirligi Akademiyasi) | `iiv-akademiyasi` | `@akadmvduz` | `#2B6FD6` |
| 3 | Bojxona instituti (Davlat bojxona qoʻmitasi Bojxona instituti) | `bojxona-instituti` | `@DBQ_BOJXONA_INSTITUTI` | `#1FA463` |
| 4 | Huquqni muhofaza qilish akademiyasi | `huquqni-muhofaza-qilish-akademiyasi` | `@TheLawEnforcementAcademy` | `#9C4DC4` |
| 5 | Jamoat xavfsizligi universiteti | `jamoat-xavfsizligi-universiteti` | `@jamoat_xavfsizligi_universiteti` | `#0E97A5` |

`order` is also the chart series order (ADR‑007). Colors and order are defined **only** in `docs/SPEC.md §7.4`; this table mirrors it.

Official full names must be verified from each channel's "about" text and each institution's website during
Phase 1 and stored in the DB (editable in admin). Never hard‑code them in templates.

**The product loop:**

```
Telegram post ──► Ingestor (Telethon, MTProto, real time) ──► PostgreSQL (posts, media, outbox)
      ──► AI editorial pipeline (Celery) ──► Article + structured objects (Event/Admission/…)
      ──► auto‑publish (policy) or editorial review ──► public site + dashboards + API + RSS
```

Languages: **uz‑Latn (default, no URL prefix)**, `uz-cyrl` (deterministic transliteration, no AI cost),
`ru`, `en` (AI translation, can be disabled). Time zone: `Asia/Tashkent`.

Owner's language is Uzbek. **Status reports to the owner: Uzbek (Latin).** Code, comments, commits,
docs, identifiers: English.

Where things are specified:

| Topic | File |
|---|---|
| Functional + technical spec (pages, models, admin, API, i18n, security) | `docs/SPEC.md` |
| System design, data flows, reliability, failure modes | `docs/ARCHITECTURE.md` |
| AI pipeline: stages, prompts, schemas, guardrails, cost | `docs/AI_PIPELINE.md` |
| Docker, CI/CD, VPS, backups, monitoring, hardening | `docs/DEVOPS.md` |
| Phased execution plan with acceptance criteria | `docs/PHASES.md` |
| Living progress checklist (you update it) | `docs/PROGRESS.md` |
| Architecture decision records (you append) | `docs/DECISIONS.md` |
| Owner‑facing explanation in Uzbek | `docs/TZ_UZ.md` |

---

## 2. Non‑negotiables

1. **Scope is fixed.** Everything in `docs/SPEC.md` is a requirement. Do not simplify features away.
   If something is truly impossible, implement the closest equivalent and record why in `docs/DECISIONS.md`.
2. **Real verification.** Nothing is "done" until you ran it: tests, `make` targets, `curl` against the
   running app, `docker compose ps/logs`. Never claim success from reading code.
3. **Ingestion reliability first.** Idempotent writes (`UNIQUE(source, telegram_message_id)`),
   transactional outbox, at‑least‑once processing with idempotent consumers, single‑leader ingestor,
   periodic gap check, heartbeat + alerting.
4. **AI never invents facts.** The fact‑guard stage is mandatory. A draft that fails fact‑guard or
   carries risk flags goes to the review queue and is never published automatically.
5. **Secrets never enter git.** Do not open `.env`. `.env.example` is the contract and must always list
   every variable the code reads, with a comment and a safe default or `CHANGE_ME`.
6. **Official tone and correct Uzbek Latin orthography** (oʻ, gʻ, tutuq belgisi ʼ — U+02BB / U+02BC, never
   the ASCII apostrophe in published content). No emojis in generated content or UI copy.
7. **Source attribution on every AI article**: institution name + link to the original Telegram post.
8. **Solo maintainability**: boring, well‑maintained libraries; no clever abstractions; modules ≤ 500 lines;
   full type hints; docstrings on public functions; ruff‑clean.
9. **Never run destructive commands** (`docker compose down -v`, `DROP`, `git push --force`,
   `rm -rf` outside the repo, `flush`). Ask the owner explicitly if one seems needed.
10. **Do not stop early.** Work phase by phase until the project Definition of Done (§10) passes.
    Only pause at the defined human action points (§9), and even then continue with everything that
    does not depend on the missing input (mock provider, demo seed).

---

## 3. Tech stack (pinned — do not substitute without an ADR)

| Layer | Choice |
|---|---|
| Language / framework | Python 3.12 · **Django 5.2 LTS** (latest 5.2.x; extended support to April 2028; plan upgrade to 6.2 LTS after April 2027, not before) |
| Database | PostgreSQL 17 with extensions `vector` (pgvector), `pg_trgm`, `unaccent` — image `pgvector/pgvector:pg17` |
| Cache / broker / locks | Redis 7 — **two instances**: `redis` (broker + locks + heartbeat, `noeviction`, AOF) and `redis-cache` (Django cache, `allkeys-lru`) |
| Background jobs | Celery 5.5 + `django-celery-beat` + `django-celery-results`. Queues: `ingest`, `ai`, `media`, `default` |
| Telegram | **Telethon ≥ 1.45, < 2** (MTProto **user** session; PyPI `Telethon`; upstream repo is now `codeberg.org/Lonami/Telethon`) |
| AI | `anthropic` Python SDK behind a provider interface. `AI_MODEL=claude-sonnet-5` (drafting/translation), `AI_MODEL_FAST=claude-haiku-4-5-20251001` (classification, fact‑guard, dedupe confirm). `AI_PROVIDER=mock` for dev/tests. Model IDs live only in env. |
| Embeddings | `fastembed` (ONNX, no torch) with `intfloat/multilingual-e5-small` registered as a **custom model** (`TextEmbedding.add_custom_model`, mean pooling, normalized, dim 384 — it is not in fastembed's built‑in list) → `pgvector.django.VectorField(dimensions=384)`. Dimension is baked into a migration; the model is not swappable via env without a migration. |
| Web / UI | Django templates + `django-htmx` (HTMX 2.x, `allowEval=false`) + **Alpine.js 3.x CSP build** (`@alpinejs/csp`; components registered with `Alpine.data()`, no inline expressions that need `eval`) + **Tailwind CSS 4 via `django-tailwind-cli`** (standalone binary, no Node) + Apache ECharts 5 (vendored, lazy‑loaded when a chart scrolls into view) + Lucide icons (SVG sprite) + self‑hosted, subset fonts |
| Admin | `django-unfold` (dashboard, editorial queue, monitors) |
| i18n | `django-modeltranslation` (`_uz`, `_uz_cyrl`, `_ru`, `_en`) + `i18n_patterns` + `.po` files |
| Public API | `django-ninja` (read‑only JSON, OpenAPI at `/api/docs`) |
| Storage | Local volume by default (`MEDIA_BACKEND=local`), `django-storages[s3]` when `MEDIA_BACKEND=s3` |
| Media processing | Pillow (WebP derivatives), `ffmpeg` (video posters) |
| Safety / security | `nh3` (HTML sanitizer), `django-ratelimit`, `django-csp`, `django-otp` + `django-two-factor-auth`, `django-axes`, Cloudflare Turnstile (appeal form) |
| Observability | `structlog` + `django-structlog` (JSON logs), `django-prometheus`, `sentry-sdk` (optional), ops Telegram bot alerts |
| Tooling | `uv`, `ruff`, `mypy` (soft), `pytest` + `pytest-django` + `factory_boy` + `freezegun` + `respx`, `pre-commit`, GitHub Actions, Docker multi‑stage (non‑root), Compose (`compose.yaml` dev / `compose.prod.yaml` prod), Caddy 2 (auto‑TLS) |

Forbidden without ADR: Django REST Framework, React/Vue/Next, Node build pipeline, ORMs other than Django's,
RabbitMQ, Kubernetes, any unmaintained package.

---

## 4. Repository layout

```
educore/
├── CLAUDE.md  PROMPT.md  README.md  Makefile  pyproject.toml  uv.lock  .env.example
├── .pre-commit-config.yaml  .github/workflows/{ci.yml,deploy.yml}  .claude/settings.json
├── Dockerfile  compose.yaml  compose.prod.yaml
├── docker/{entrypoint.sh, caddy/Caddyfile, postgres/init.sql, backup/backup.sh}
├── config/                     # Django project
│   ├── settings/{base,dev,test,prod}.py   urls.py   celery.py   asgi.py   wsgi.py
├── apps/
│   ├── core/          # SiteSetting, Page, FAQ, base models, translit, sanitizer, healthz, template tags
│   ├── accounts/      # custom User (email login), roles/groups, 2FA
│   ├── institutions/  # Institution, InstitutionContact, InstitutionMetric, Program, Profession
│   ├── telegram/      # TelegramSource, TelegramPost, TelegramMedia, IngestionOutbox, ingestor, commands
│   ├── ai/            # providers, embeddings, prompts/, pipeline stages, AIRun, EventCluster, budget
│   ├── content/       # Category, Tag, Article, ArticleSource, ArticleMedia, Event, Admission, Story
│   ├── appeals/       # Appeal, AppealAttachment, AppealMessage, notifications
│   ├── analytics/     # DailyStat, InstitutionDailyStat, aggregation tasks, chart data services
│   ├── web/           # public views, HTMX partials, search, sitemaps, feeds
│   ├── api/           # django-ninja routers
│   └── ops/           # heartbeat checks, ops bot notifier, metrics
├── templates/         # base.html, components/, pages/, partials/, emails/, admin/
├── static/            # src/css/input.css, js/, vendor/{htmx,alpine,echarts,lucide}, fonts/, img/
├── locale/{uz,uz_Cyrl,ru,en}/LC_MESSAGES/django.po
├── fixtures/          # demo seed data (institutions, categories, sample posts, professions, programs)
├── scripts/           # server-setup.sh, deploy.sh, backup.sh, restore.sh, translit_po.py
├── docs/              # SPEC, ARCHITECTURE, AI_PIPELINE, DEVOPS, PHASES, PROGRESS, DECISIONS, RUNBOOK, TZ_UZ
└── manage.py
```

Each app: `models.py`, `admin.py`, `services/` (business logic), `tasks.py` (Celery), `selectors.py`
(read queries), `tests/`. Views stay thin; logic lives in `services/`.

---

## 5. Commands (Makefile is the single entry point — keep it current)

```
make up / down / ps / logs         # dev stack; `up` copies .env.example → .env if missing, runs migrate first, then starts db, redis, mailpit, web, worker, worker-ai, beat
make migrate / makemigrations      # DB
make seed                          # create-only seed: institutions, categories, sources, professions, programs, pages, roles, beat schedule
make seed-demo                     # + ~40 sample posts and generated demo articles (mock provider)
make createsuperuser / shell / dbshell
make test / test-fast / cov        # pytest (-x -q), coverage report (gate: 80% on telegram/ai/content)
make lint / fmt / typecheck        # ruff check, ruff format, mypy
make tailwind / tailwind-build     # Tailwind watch / production build
make fonts                         # download + subset self-hosted fonts into static/fonts
make messages / compilemessages    # i18n .po extraction / compile; make translit-po (uz -> uz_Cyrl)
make tg-login                      # interactive first Telegram login (HUMAN ACTION)
make tg-run                        # start the ingestor (compose profile `telegram`)
make tg-backfill / tg-gapcheck     # enqueue an IngestionRequest for the running ingestor (see SPEC FR-TG-6/7)
make worker / worker-ai / beat / flower
make ai-eval                       # golden-set evaluation (opt-in, needs ANTHROPIC_API_KEY)
make stats-rebuild                 # rebuild DailyStat/InstitutionDailyStat from history
make e2e                           # Playwright smoke (optional)
make check-deploy                  # manage.py check --deploy with prod settings
make backup / restore FILE=...
make prod-deploy / prod-rollback   # ssh deploy / rollback (see docs/DEVOPS.md)
```

Every command must work from a clean clone with only Docker installed (`make up` builds everything).

---

## 6. Architecture in one screen

```
                 ┌────────────────────────── VPS (Docker Compose) ──────────────────────────┐
                 │  caddy (TLS, static, media)                                              │
 Internet ─────► │    └─► web (gunicorn, Django)  ──► postgres 17 (+pgvector)  ◄── worker    │
                 │                                 └► redis 7                  ◄── beat      │
 Telegram ─────► │  ingestor (Telethon, 1 replica, leader lock, heartbeat) ──► postgres      │
                 │  migrate (one‑shot)   backup (cron)   [prometheus, grafana, flower: opt]  │
                 └───────────────────────────────────────────────────────────────────────────┘
```

Processes (same image, different command): `web`, `worker` (queues `ingest,default`, `-c 2`),
`worker-ai` (queue `ai`, `-c 1`, loads the embedding model), `worker-media` (queue `media`, `-c 1`),
`beat`, `ingestor` (`manage.py telegram_ingest`), `migrate` (one‑shot, `restart: "no"`).

Key invariants:
- Only the **ingestor** process ever talks to Telegram (live updates, history backfill, gap check,
  engagement refresh, media downloads). Other processes request Telegram work by inserting an
  `IngestionRequest` row (`backfill|gapcheck|refresh_engagement|resolve_source`) which the ingestor polls every 15 s.
- Every DB write from the ingestor goes through `apps/telegram/repository.py` (sync, `transaction.atomic`)
  called via `asgiref.sync.sync_to_async`. One transaction = post upsert + media rows + outbox event.
- `IngestionOutbox` is relayed by Celery beat every 10 s (`SELECT … FOR UPDATE SKIP LOCKED`) **and**
  nudged immediately via `transaction.on_commit` (nudge failures are swallowed — the relay is the guarantee).
  Consumers are idempotent (keyed by post id + content hash). `attempts` counts terminal task failures only.
- Behind Caddy the real client IP comes from `X-Forwarded-For` (first hop, only when the peer is the Caddy
  container): a `TrustedProxyMiddleware` rewrites `REMOTE_ADDR` before rate limiting, axes, allowlists and
  page‑view hashing. `/healthz`, `/readyz` are answered by a middleware placed before `SecurityMiddleware`/
  `CommonMiddleware` (any Host, no SSL redirect) so container health checks work.
- Albums (`grouped_id`) are one post with N media. Edits update in place (new content hash → reprocess).
  Deletes archive (`is_deleted=True`), never physically delete.
- Ingestor heartbeat in Redis (`educore:ingestor:heartbeat`); beat task alerts if stale > 3 min.
- AI pipeline is a single Celery task `process_post` with persisted per‑stage `AIRun` rows; retries are safe.
- Publish policy (`PUBLISH_MODE=auto|review|off`, `PUBLISH_CONFIDENCE_THRESHOLD`) is the only gate to public.

---

## 7. Coding standards

- Python: ruff (`E,F,I,B,UP,N,S,DJ,ASYNC`), line length 110, `from __future__ import annotations`,
  full type hints, Pydantic v2 for all AI I/O and external payloads, dataclasses for internal DTOs.
- Django: fat `services/`, thin views; `select_related/prefetch_related` in selectors; all list views
  paginated; every model has `created_at/updated_at`; `Meta.ordering` explicit; `__str__` defined;
  `db_index`/`Index` on every filter/sort column; migrations reviewed (no auto‑generated names for
  non‑trivial migrations); `TextChoices` for statuses.
- Templates: one `base.html`, components in `templates/components/` (`{% include %}` with explicit
  context), HTMX partials in `templates/partials/`, no inline JS except CSP‑nonced boot scripts.
  UI copy through `{% trans %}`/`{% blocktrans %}`.
- Accessibility: semantic HTML, focus states, `aria-live` for the live panel, contrast ≥ AA, reduced‑motion.
- Tests: pytest, one test module per service; factories in `apps/<app>/tests/factories.py`; no network in
  tests (`respx`/mocks); AI tests use `MockProvider`; Telegram tests use recorded fixture messages.
- Logging: structlog, `event` names in `snake_case`, always include `post_id`/`source`/`stage` when relevant.
- Commits: Conventional Commits (`feat(telegram): …`, `fix(ai): …`, `chore(devops): …`), one logical change each.
- Docs: update `docs/PROGRESS.md` after every task; append ADRs to `docs/DECISIONS.md` for every non‑obvious choice.

---

## 8. Workflow protocol (how you operate)

1. **Session start:** read `CLAUDE.md` → `docs/PROGRESS.md` → `git log --oneline -20` → `git status`.
   Continue from the first unchecked item of the current phase. Never re‑do completed work.
2. **Per task:** plan briefly (what files, what tests) → implement → run the verification commands listed in
   `docs/PHASES.md` → fix until green → update `docs/PROGRESS.md` (tick + date + one line) → commit.
3. **Per phase:** run the phase acceptance checklist end‑to‑end, write a 5–10 line status report in Uzbek
   for the owner (what works, how to check, what is next, any human action needed), commit `docs/PROGRESS.md`.
4. **Decisions:** when the spec leaves a choice, decide (favor simplicity and reliability), record it in
   `docs/DECISIONS.md` (ADR format), move on. Do not ask the owner for things you can decide.
5. **Blocked by a human action point (§9):** write the exact request in `docs/PROGRESS.md › Human actions`
   and in your message, then continue with everything else using `AI_PROVIDER=mock`, demo seed, and
   fixtures. Return to the blocked item when the input arrives.
6. **Context reset / compaction:** re‑read §8.1; the repo + `docs/PROGRESS.md` are the source of truth.
7. **Before finishing any session:** `make lint && make test` green, everything committed, PROGRESS.md accurate.

---

## 9. Human action points (the only places you wait — and only for that item)

| ID | When | What the owner must provide | How you proceed meanwhile |
|---|---|---|---|
| HA0 | Phase 0 | An empty GitHub repository + `git remote origin` (for CI); Node.js ≥ 20 and Chrome (for `npx lighthouse`) on the dev machine | Work locally; push when the remote exists |
| HA2 | Phase 2 | Telegram `api_id`, `api_hash` (my.telegram.org) + a dedicated phone account; run `make tg-login` and type the SMS/app code; **a private test channel the owner administers** (for AC2.3 / AS‑1…AS‑5) | Build & test ingestion with fixture messages and a mocked Telethon client |
| HA3 | Phase 3 | `ANTHROPIC_API_KEY` | `AI_PROVIDER=mock` end‑to‑end |
| HA7 | Phase 7 | Cloudflare Turnstile keys (optional), ops bot token + chat id (optional), SMTP creds (optional), Sentry DSN (optional) | Feature‑flagged; mailpit in dev; alerts go to the log |
| HA8 | Phase 8 | VPS (Ubuntu 24.04, ≥ 4 vCPU / 8 GB / 80 GB), domain + DNS A record (and `www` if wanted), GitHub secrets `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `GHCR_PAT` (read:packages), the owner's `age` public key for backups | Prepare everything, dry‑run locally with `compose.prod.yaml` |
| HA9 | Phase 9 | Official texts (About, contacts) and verification of seeded programs/professions/metrics in admin | Seed realistic drafts flagged `needs_verification=True` |

---

## 10. Definition of Done (whole project)

1. `docker compose -f compose.prod.yaml up -d` on a clean VPS with a filled `.env` → site live on the
   domain with valid TLS; `/healthz` and `/readyz` green; `manage.py check --deploy` clean.
2. All five Telegram sources `live` in admin; a new post in any source becomes a published article
   (auto mode) with media and attribution within **60 s**; an edit updates it; a deletion archives it.
3. Backfill done: the newest `BACKFILL_AI_LIMIT_PER_SOURCE` (default 150) posts per institution processed by the
   pipeline (each ended as a published article, a merge into an existing article, a review item, or a recorded
   skip); cross‑source duplicates merged into one article with multiple sources.
4. Every page in `docs/SPEC.md §6` implemented in all four languages, responsive, dark/light,
   Lighthouse (mobile) ≥ 90 for Performance, SEO, Accessibility, Best Practices on home + article pages.
5. Admin: dashboard, editorial queue, sources monitor, outbox/AI runs with retry, AI cost, appeals inbox,
   settings, users with mandatory 2FA.
6. Analytics page and institution comparison render from real aggregated data; nightly aggregation runs.
7. Public API documented at `/api/docs`, rate‑limited, covered by tests.
8. CI green on `main`: ruff, tests (coverage ≥ 80 % on `apps/telegram`, `apps/ai`, `apps/content`; ≥ 70 % overall),
   `check --deploy`, `pip-audit`, Trivy (no CRITICAL).
9. Nightly backups verified by one documented restore drill; ops alerts proven (stop the ingestor → alert arrives
   in the ops Telegram chat, or in the log when HA7 keys are absent).
10. `README.md`, `docs/RUNBOOK.md`, `docs/DECISIONS.md`, `docs/PROGRESS.md` complete; `.env.example` complete.

---

## 11. Quick reference — names you must use consistently

- Env vars: see `.env.example` (authoritative). Core ones: `DJANGO_SETTINGS_MODULE`, `SECRET_KEY`, `DEBUG`,
  `ALLOWED_HOSTS`, `SITE_URL`, `DATABASE_URL`, `DATABASE_POOL` (web only), `REDIS_URL`, `CACHE_URL`, `CELERY_BROKER_URL`, `TELEGRAM_API_ID`,
  `TELEGRAM_API_HASH`, `TELEGRAM_PHONE`, `TELEGRAM_SESSION_PATH`, `TELEGRAM_BACKFILL_LIMIT`,
  `BACKFILL_AI_LIMIT_PER_SOURCE`, `AI_PROVIDER`, `ANTHROPIC_API_KEY`, `AI_MODEL`, `AI_MODEL_FAST`,
  `AI_DAILY_USD_BUDGET`, `AI_TRANSLATE_TO`, `EMBEDDING_MODEL`, `PUBLISH_MODE`, `PUBLISH_CONFIDENCE_THRESHOLD`,
  `ON_SOURCE_DELETE`, `MEDIA_BACKEND`, `S3_*`, `ADMIN_URL_PATH`, `OPS_TELEGRAM_BOT_TOKEN`, `OPS_TELEGRAM_CHAT_ID`,
  `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `EMAIL_URL`, `DEFAULT_FROM_EMAIL`, `SENTRY_DSN`.
- Statuses: `TelegramPost.processing_status ∈ {pending, queued, processing, processed, skipped, failed}`;
  `Article.status ∈ {draft, review, published, archived, rejected}`; `TelegramMedia.status ∈ {pending, downloaded, ready, failed}`;
  `TelegramSource.status ∈ {live, degraded, offline, disabled}`; `Appeal.status ∈ {new, in_progress, answered, closed, rejected}`.
- Outbox event types: `telegram.post.created`, `telegram.post.edited`, `telegram.post.deleted`.
- `IngestionRequest.kind ∈ {backfill, gapcheck, refresh_engagement, resolve_source, retry_media}`; `AIRun.stage ∈
  {triage, normalize, extract, embed, dedupe, generate, fact_guard, media_select, structured_upsert, publish_policy,
  post_publish, translate, regenerate, digest}`.
- **Celery tasks — authoritative table (name · queue · schedule):**

  | Task | Queue | Schedule |
  |---|---|---|
  | `telegram.relay_outbox` | ingest | every 10 s + on_commit nudge |
  | `telegram.request_gapcheck` (inserts IngestionRequest for every live source) | ingest | every 10 min |
  | `telegram.request_engagement_refresh` | ingest | every 6 h |
  | `telegram.request_media_retry` (failed media < 3 days old) | ingest | every 6 h |
  | `telegram.cleanup_outbox` (processed > 30 d) | default | daily 04:00 |
  | `media.process_media` | media | on demand |
  | `ai.process_post` | ai | on demand (from relay) |
  | `ai.translate_article` | ai | on demand (after publish) |
  | `ai.weekly_digest` | ai | Monday 07:00 |
  | `ai.prune_runs` (payloads > 180 d) | default | monthly |
  | `analytics.aggregate_daily` | default | daily 02:00 |
  | `analytics.flush_pageviews` | default | hourly |
  | `analytics.refresh_institution_stats` | default | daily 02:30 |
  | `ops.check_heartbeat` | default | every 1 min |
  | `ops.check_ai_failure_rate` | default | every 15 min |
  | `ops.review_digest` | default | daily 09:00 |
  | `web.bump_content_version` (cache/sitemap invalidation) | default | on publish/edit |
  | `appeals.notify_new` | default | on submit |

  All periodic tasks use `ignore_result=True`; `result_expires = 1 day`.
- Management commands: `telegram_login`, `telegram_ingest`, `telegram_backfill` (enqueues an `IngestionRequest`;
  `--standalone` runs directly and requires the ingestor to be stopped), `telegram_gapcheck` (enqueues),
  `ingestor_health`, `seed_all`, `seed_demo`, `sync_roles`, `ai_reprocess`, `stats_rebuild`, `anonymize_appeals`.
