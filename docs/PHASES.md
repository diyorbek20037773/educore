# EDUCORE — Phased Execution Plan (A → Z)

Execute phases **in order**. A phase is complete only when every acceptance check passes with real commands.
Record progress in `docs/PROGRESS.md` (tick items, dates, notes). Commit after every task.
Estimated effort is for planning only; correctness beats speed.

Legend: **T** = task, **AC** = acceptance check (must be run and pass), **HA** = human action point.

---

## Phase 0 — Bootstrap (repo, tooling, containers, CI skeleton)

T0.1 `git init`, `.gitignore` (Python, Django, `.env*`, `*.session`, `media/`, `staticfiles/`, `.venv`, `node_modules`, `htmlcov`).
T0.2 `pyproject.toml` with `uv`: Django 5.2.x and all pinned deps from `CLAUDE.md §3`; dev group (pytest, ruff, mypy, factory_boy, freezegun, respx, pytest-cov, pre-commit, django-debug-toolbar).
T0.3 Django project `config/` with settings split (`base/dev/test/prod`) via `django-environ`; `apps/` package with all apps registered (empty models ok); custom `User` in `accounts` **before first migration**.
T0.4 `Dockerfile` (multi‑stage), `docker/entrypoint.sh`, `docker/postgres/init.sql` (extensions), `compose.yaml` (dev), `.env.example` (full contract from `DEVOPS.md §2`).
T0.5 `Makefile` with every target from `CLAUDE.md §5` (targets for later phases may print "not yet implemented" but must exist).
T0.6 Celery app (`config/celery.py`), queues, beat scheduler config, `django-celery-beat/results` installed; health endpoints `/healthz`, `/readyz`; structlog JSON logging; `django-prometheus` wired.
T0.7 Tailwind 4 via `django-tailwind-cli` (`static/src/css/input.css` with tokens from `SPEC.md §7.2`), `base.html` skeleton, HTMX + Alpine + ECharts + Lucide vendored into `static/vendor/` (download pinned versions), fonts via `make fonts`.
T0.8 `ruff`, `mypy`, `pytest` config (`pytest.ini`/pyproject; `DJANGO_SETTINGS_MODULE=config.settings.test`), `pre-commit`, `.github/workflows/ci.yml` (lint + test with services + build), `README.md` (quickstart).
T0.9 `docs/PROGRESS.md` initialized from the template; `docs/DECISIONS.md` already holds ADR‑001…ADR‑008 — append ADR‑009+ for choices you make.
**HA0** Owner creates the GitHub repository and gives the remote URL; installs Node ≥ 20 + Chrome for Lighthouse. Push as soon as the remote exists.

AC0.1 `make up` (creates `.env` from the example if missing, runs `migrate`, then starts services) → `curl -s localhost:8000/healthz` returns `{"status":"ok"}`; home page renders "EDUCORE" with Tailwind styles.
AC0.2 `make test` passes (≥ 3 smoke tests: healthz, settings import, celery app loads); `make lint` clean.
AC0.3 `docker build .` succeeds; image runs `gunicorn`; `make check-deploy` (with dummy prod env) reports 0 errors.
AC0.4 CI workflow file validated (`act` optional) — at minimum YAML is valid and jobs mirror `make lint`/`make test`.

---

## Phase 1 — Domain models, migrations, seeds, admin

T1.1 Implement every model in `SPEC.md §2` with translations (`translation.py` per app), history, indexes, constraints; `TextChoices`; `pgvector` field; `SearchVectorField` maintenance.
T1.2 Migrations (named), including `CreateExtension` for `vector`, `pg_trgm`, `unaccent` and HNSW index (`RunSQL` if needed).
T1.3 `seed_all` (create‑only, never overwrites existing rows — see SPEC §12): institutions (verify official names/descriptions from channel about‑texts and websites via WebFetch; store; flag `needs_verification` where unsure), contacts, metrics placeholders, sources, categories, tags, ≥ 20 professions, ≥ 4 programs per institution, pages, FAQ, SiteSetting, roles (`sync_roles`), placeholder SVG logos/covers.
T1.4 Admin with `django-unfold`: registrations for all models with list filters/search/inlines/actions from `SPEC.md §8`; dashboard index with placeholder widgets (real data in Phase 5).
T1.5 `apps/core/translit.py` (Latin ↔ Cyrillic) with golden‑corpus tests; `apps/core/sanitize.py` (`nh3`) with tests; `scripts/translit_po.py`.
T1.6 Factories for every model; selectors for list pages with `django_assert_num_queries` tests.

AC1.1 `make migrate && make seed` idempotent (run twice, no duplicates; `Institution.objects.count()==5`, `Category==16`, `Profession>=20`).
AC1.2 Admin shows every model; unfold theme active; 2FA setup flow works for a staff user (`django-two-factor-auth`).
AC1.3 `pytest apps/core apps/institutions apps/content -q` green; translit round‑trip test passes on the 200‑word corpus.

---

## Phase 2 — Telegram ingestion (live, history, media, outbox)

T2.1 `apps/telegram/ingestor/` per `ARCHITECTURE.md §3.2`: client factory, leader lock (tolerates Redis outages), heartbeat, bootstrap, handlers (new/album/edit/delete; albums keyed by `grouped_id`), normalize → DTO, repository (sync, atomic), media downloader (bounded concurrency, limits, storage), finalize + outbox, source refresh loop, `IngestionRequest` poller + executors (backfill, gapcheck, refresh_engagement, resolve_source, retry_media), built‑in gap‑check (10 min) and engagement (6 h) loops.
T2.2 Management commands: `telegram_login` (interactive; refuses to run while the leader lock is held), `telegram_ingest` (long‑running, graceful SIGTERM), `telegram_backfill` (inserts a request; `--standalone` runs in‑process only when no ingestor is running; `--source`, `--limit`, `--ai-limit`), `telegram_gapcheck` (inserts a request), `ingestor_health`.
T2.3 Celery: `telegram.relay_outbox` (SKIP LOCKED SQL, lock renewal, on_commit nudge in try/except), `telegram.request_gapcheck`, `telegram.request_engagement_refresh`, `telegram.request_media_retry`, `telegram.cleanup_outbox`, `media.process_media` (WebP 1600/800/400 + poster via ffmpeg), `ops.check_heartbeat` (1 min); beat entries created by `seed_all`.
T2.4 Storage abstraction (`local`/`s3`), path scheme, `TelegramMedia` derivative handling, template tag `{% media_url media "800" %}` with fallback.
T2.5 Tests with recorded fixtures (`fixtures/telethon/*.json` built from Telethon `to_dict()` samples you construct): single, album, edit (hash change / no change), delete, forwarded, service message, media over limit, outbox uniqueness, relay locking (two concurrent relays → each event dispatched once), leader lock, backfill grouping, FloodWait handling (mocked), source refresh picks up a new source.
T2.6 Admin: sources monitor (status, lag, counters, actions), posts (raw JSON viewer, reprocess/skip), media, outbox (retry). `/healthz` detail includes ingestor heartbeat age and per‑source status.
**HA2** Owner provides `TELEGRAM_API_ID/HASH/PHONE`; runs `make tg-login` and enters the code. Until then, everything is verified with fixtures and a mocked Telethon client.

AC2.1 `pytest apps/telegram -q` green; coverage ≥ 80 % for `apps/telegram`.
AC2.2 (after HA2) `docker compose --profile telegram up -d ingestor` → logs show 5 sources `live` with channel ids; `make tg-backfill` imports ≥ 500 posts/source (or channel total) with albums grouped and media downloaded; re‑running adds 0 rows.
AC2.3 (after HA2) Post to the owner's test channel added as a 6th source in admin (no restart) → `TelegramPost` row within 10 s, media `downloaded`, outbox event present; edit → `edited` event; delete → `is_deleted=True` + event.
AC2.4 Stop the ingestor for 5 min → `ops.check_heartbeat` logs alert within 4 min (bot optional) and sources `offline`; start → `live` again, "recovered" alert, missed test posts ingested.

---

## Phase 3 — AI editorial pipeline

T3.1 Providers (`AnthropicProvider`, `MockProvider`), pricing, budget guard (outbox `locked_until` semantics), `AIRun` logging, embeddings (`fastembed` custom‑model registration, `FakeEmbedding` trigram hashing), schemas (`apps/ai/schemas.py`, word‑boundary truncation validators), prompts `v1/*.md` exactly as in `AI_PIPELINE.md §3` (extend as needed, keep the rules).
T3.2 `ai.process_post` with all stages (`AI_PIPELINE.md §2`), per‑stage caching, retries, dead‑letter handling; dedupe with pgvector + confirm; structured upsert; publish policy; post‑publish (translit, cache bump, sitemap bump, alerts, stats counters).
T3.3 `ai.translate_article`, `ai.weekly_digest`, `ai_reprocess` command (`--post`, `--article`, `--force`, `--stage`).
T3.4 Editorial admin: article changelist with filters/actions/preview/side‑by‑side source; AI runs viewer; clusters; budget days; "needs review" queue view as the Tahririyat landing page.
T3.5 Golden set (`apps/ai/tests/golden/`, 20 posts) + `make ai-eval`; unit tests for every stage with `MockProvider` and `FakeEmbedding`; integration test: fixture post → published article end‑to‑end in < 5 s with mock; dedupe test: two posts from different sources with near‑identical text → one article, two sources; edit → regenerate + history; delete → archived; budget exhaustion → queued + alert; fact‑guard fail → review.
**HA3** Owner provides `ANTHROPIC_API_KEY`; switch `AI_PROVIDER=anthropic` in dev, run `make ai-eval` (≥ 90 % category accuracy) and process 10 real backfilled posts; review quality; tune prompts (bump `PROMPT_VERSION`).

AC3.1 `pytest apps/ai -q` green; coverage ≥ 80 % for `apps/ai` and `apps/content`.
AC3.2 `make seed-demo` (mock) produces ≥ 30 published articles with covers, categories, tags, sources, uz‑cyrl copies; site lists render.
AC3.3 (after HA3) Real post → published article ≤ 60 s (measure and record in PROGRESS.md); cost per post recorded in `AIRun` and shown in admin.

---

## Phase 4 — Public website

T4.1 Design system: tokens, fonts, components (`SPEC.md §7.3`), dark/light, icons sprite, ECharts theme + `charts.js` (fixed institution palette, table view, CSV), sparkline SVG helper.
T4.2 Pages: home (all 11 blocks), institutions list/profile (all tabs)/comparison, news list/detail (+410 archived), articles, programs, admissions, students/cadets hubs, professions, events (+calendar +ics), motivation, analytics page (data endpoints can be stubbed until Phase 5, but charts must render), appeals form/tracking (Phase 6 wires backend; build the UI now), search, static pages, error pages, maintenance page.
T4.3 HTMX behaviors: live panel polling, filter chips, infinite scroll, search suggestions, chart data loading, `hx-boost`; Alpine for drawer/menus/theme/lightbox.
T4.4 i18n: `i18n_patterns`, switcher, `.po` for ru/en (write them), `make translit-po` for uz_Cyrl, fallback notice, `hreflang`.
T4.5 SEO: sitemaps (sections, alternates), RSS feeds (global/institution/category), JSON‑LD (`NewsArticle`, `Event`, `Organization`, `BreadcrumbList`), OG images (article cover or generated default), `robots.txt`, canonical, `manifest.webmanifest`.
T4.6 Caching + invalidation (`content_version` key), WhiteNoise, image `srcset`, lazy loading, ECharts loaded lazily on `revealed`, subset fonts, `django-csp` (nonce; Alpine CSP build; `htmx.config.allowEval=false`), `TrustedProxyMiddleware`, `HealthMiddleware`, security headers in dev parity.
T4.7 Tests: every URL returns 200 with demo data in all four languages (parametrized), HTMX partials return fragments, `django_assert_num_queries` on lists, sitemap/RSS validity, 404/410 behavior, dark mode toggle presence; Playwright smoke (optional `make e2e`).

AC4.1 `make seed-demo` then crawl: script `scripts/crawl_check.py` fetches every sitemap URL in 4 languages → all 200, no template errors, no N+1 warnings.
AC4.2 Lighthouse (mobile) ≥ 90 ×4 on `/` and one article (`npx lighthouse` via `npx`/Chrome in CI optional; locally mandatory once, record scores in PROGRESS.md).
AC4.3 Manual visual check at 360 px, 768 px, 1280 px in light and dark: no overflow, readable charts, live panel updates.

---

## Phase 5 — Analytics & dashboards

T5.1 `analytics.aggregate_daily` (02:00) computing `DailyStat`/`InstitutionDailyStat` (posts, articles, TG views/forwards, by category/content type/hour); `stats_rebuild` command (backfill from history); `Institution.stats_cache` refresh; page‑view counters flush (hourly).
T5.2 Chart data services + endpoints (`/analitika/data/<chart>/`, JSON, cached 5 min) for every chart in `SPEC.md §6.9` and institution profile charts; CSV export.
T5.3 Admin dashboard (unfold index) with real numbers/charts; comparison page data; KPI tiles with sparklines wired to real data.
T5.4 Tests for aggregation correctness (fixtures with known counts), timezone edges (Asia/Tashkent day boundaries), empty data rendering.

AC5.1 `make stats-rebuild` fills stats for all backfilled data; `/analitika/` shows all 7 charts with real numbers and table views; comparison page correct.
AC5.2 Beat schedule contains all periodic tasks (`django-celery-beat` rows) after `seed_all`.

---

## Phase 6 — Appeals (Murojaat) & notifications

T6.1 Appeal models/forms/views: validation (`+998` phone regex, message ≥ 20 chars), honeypot, rate limit, Turnstile (feature‑flagged: disabled when keys empty), attachments (mime sniff, **private storage + staff‑only download view**), tracking code generator, success page, tracking page with timeline, email confirmation (mailpit in dev), moderator alert (ops bot/email).
T6.2 Admin inbox: statuses, assignment, replies (`AppealMessage`, email to applicant), internal notes, CSV export, SLA overdue filter; `anonymize_appeals` command (24 months).
T6.3 Public API `POST /api/v1/appeals` sharing the same service layer.
T6.4 Tests: submission happy path, rate limit, honeypot, invalid file, tracking page, anonymization.

AC6.1 Submit via UI and API → inbox shows both; reply → tracking page shows public reply; emails visible in mailpit.

---

## Phase 7 — Public API & hardening & observability

T7.1 `django-ninja` API per `SPEC.md §9` with schemas, pagination, filtering, language handling, ETags, rate limits, CORS allowlist, OpenAPI docs; tests for every endpoint.
T7.2 Security: prod settings, CSP enforcement, `django-axes`, 2FA middleware, admin path/IP allowlist, upload validation everywhere, `nh3` everywhere, `check --deploy` clean, `pip-audit` clean.
T7.3 Observability: custom Prometheus pull collector, `PROMETHEUS_MULTIPROC_DIR`, `/metrics` allowlist, Sentry integration (flagged), ops bot notifier with throttling (`AlertEvent`), alert rules from `DEVOPS.md §8`, `ops.check_ai_failure_rate`, `ops.review_digest`.
T7.4 Data lifecycle tasks: `ai.prune_runs`, `telegram.cleanup_outbox`, `telegram.request_media_retry`, `analytics.flush_pageviews`, `analytics.refresh_institution_stats` (if not done in Phase 5).
**HA7** Optional keys: Turnstile, ops bot token/chat id, SMTP, Sentry DSN.

AC7.1 `/api/docs` renders; `pytest apps/api` green; rate limit returns 429 with `Retry-After`.
AC7.2 `make check-deploy` 0 issues with prod env; `pip-audit` clean; Trivy no CRITICAL on the built image.
AC7.3 Alert test: stop ingestor 5 min → message in ops chat (or log when unconfigured) within 4 min, and again "recovered".

---

## Phase 8 — Production deployment

T8.1 `compose.prod.yaml` (migrate `restart: "no"`, two Redis instances, worker split, private volume), `docker/caddy/Caddyfile` (validated with `caddy validate`), `docker/backup/backup.sh` (`age -r`, rclone), `scripts/server-setup.sh`, `scripts/deploy.sh` (deploy/rollback), `scripts/restore.sh`, `.github/workflows/deploy.yml` (GHCR + scp + SSH + smoke + rollback + notify).
T8.2 `docs/RUNBOOK.md`: first‑time setup, daily operations, common incidents (session revoked, flood wait, disk full, AI outage, restore), how to add a source, how to change publish mode, how to rotate secrets.
T8.3 Local dry‑run of prod compose (`SITE_DOMAIN=localhost` with Caddy internal TLS) → healthz over HTTPS, migrate one‑shot works, read‑only web works, backups run once via `make backup`.
**HA8** Owner provides VPS + domain + GitHub secrets; owner runs `server-setup.sh`, copies `.env`, runs `telegram_login` on the server.

AC8.1 Tagged release deploys via Actions; smoke passes; rollback tested once (deploy previous tag).
AC8.2 Backup file appears at 03:00 (or via `make backup`); `scripts/restore.sh` drill on a scratch DB documented with timestamps in RUNBOOK.
AC8.3 Site live on the domain with A+ TLS (ssllabs optional), HSTS, security headers present (`curl -I`).

---

## Phase 9 — Content verification, QA, handover

T9.1 Full backfill on prod (all 5 sources; budget raised for the day), AI processing of the newest 150/source, spot‑check 30 articles for faithfulness; tune prompts if needed (bump version, reprocess sample).
T9.2 Verify seeded institution data/programs/professions against official sources; owner marks verified in admin (bulk action); remaining `needs_verification` items listed in PROGRESS.md for the owner.
**HA9** Owner provides official About/contact texts and verifies seeded content in admin.
T9.3 Final QA: crawl check in prod, Lighthouse in prod, accessibility pass (axe via Playwright optional), all AS‑1…AS‑12 scenarios from `SPEC.md §13` executed and recorded.
T9.4 Handover: README (architecture summary, commands), RUNBOOK complete, DECISIONS complete, PROGRESS.md final report in Uzbek for the owner, secrets rotation guide, cost report (AI spend to date).

AC9.1 Project Definition of Done (`CLAUDE.md §10`) — every line verified and ticked in PROGRESS.md with evidence (command + output summary).

---

## Effort guide (single senior developer + Claude Code)
Phase 0: 0.5 d · Phase 1: 1.5 d · Phase 2: 3 d · Phase 3: 3 d · Phase 4: 5 d · Phase 5: 1.5 d · Phase 6: 1 d ·
Phase 7: 1.5 d · Phase 8: 1.5 d · Phase 9: 1.5 d ≈ **20 working days** of focused execution.
