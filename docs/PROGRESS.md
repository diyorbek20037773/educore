# EDUCORE — Progress (living document)

> Claude Code: update this file after **every** completed task and before every pause. This file plus the
> git history is the source of truth for resuming work after a context reset.

## Current focus
- Phase: **3 — AI editorial pipeline** (Phase 2 done except HA2-dependent AC2.2–AC2.4)
- Current task: T3.4
- Last updated: 2026-09-25, Claude Code

## Human actions needed (owner)
| # | Needed for | What exactly | Status |
|---|---|---|---|
| HA0 | Phase 0 | GitHub repository + remote URL; GNU make (`winget install ezwinports.make`); Chrome (Node 22 already present) | pending (asked 2026-09-25) |
| HA2 | Phase 2 | `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` from https://my.telegram.org → "API development tools"; dedicated phone number; run `make tg-login` and enter the code; a private test channel you administer | pending |
| HA3 | Phase 3 | `ANTHROPIC_API_KEY` (https://platform.claude.com) | pending |
| HA7 | Phase 7 | optional: Turnstile keys, ops bot token + chat id, SMTP, Sentry DSN | pending |
| HA8 | Phase 8 | VPS (Ubuntu 24.04, ≥ 4 vCPU/8 GB/80 GB), domain + DNS A record, GitHub secrets `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `GHCR_PAT`; your `age` public key for backups | pending |
| HA9 | Phase 9 | official About/contact texts; verify seeded programs/professions/metrics in admin | pending |

## Blockers
- none (HA0 pending — work continues locally)

## Open follow-ups
- GNU make is not installed on the dev machine yet (asked in HA0); Phase 0 checks were run with the equivalent
  `docker compose` commands from the Makefile.
- Prod image is 1.45 GB uncompressed (target ≤ 900 MB): trim in T8.1 (static ffmpeg, drop gettext from runtime).
- Gunicorn access/error logs are plain text; switch to JSON in T7.3.

## Phase checklist

### Phase 0 — Bootstrap
- [x] T0.1 repo + .gitignore — 2026-09-25 · `git init -b main`, `.gitignore` + `.gitattributes` (LF enforced for Docker scripts on Windows)
- [x] T0.2 pyproject + uv lock — 2026-09-25 · 139 pkgs locked (Django 5.2.17, Telethon 1.45.0, Celery 5.6.3, anthropic 1.8.0, fastembed 0.8.1)
- [x] T0.3 Django project + settings split + apps + custom User — 2026-09-25 · 11 apps, `accounts.User` (email login) + `0001_initial_user`; dev/test import OK, prod refuses missing env; ADR-013
- [x] T0.4 Dockerfile, entrypoint, compose.yaml, .env.example — 2026-09-25 · multi-stage non-root image (uid 10001), `SKIP_WAIT`, dev ports via env (ADR-014), comments on own lines (docker `--env-file` safe)
- [x] T0.5 Makefile (all targets exist) — 2026-09-25 · every §5 target; later-phase ones print "not yet implemented" or call commands added later
- [x] T0.6 Celery, beat, health endpoints, logging, metrics — 2026-09-25 · 4 queues + routes, DB beat scheduler, `HealthMiddleware` (`/healthz`, `/readyz`), structlog JSON, `/metrics` IP allowlist
- [x] T0.7 Tailwind, base.html, vendored HTMX/Alpine/ECharts/Lucide, fonts — 2026-09-25 · Tailwind 4.3.3, tokens §7.2, dark via `data-theme`, CSP nonce boot, htmx 2.0.11 / Alpine CSP 3.17.4 / ECharts 5.6.0 / Lucide 1.48.0, 12 subset woff2 (ADR-013, ADR-016)
- [x] T0.8 ruff/mypy/pytest/pre-commit/CI/README — 2026-09-25 · pytest forced to `config.settings.test` (`--ds`), CI jobs lint/test/security/build(+Trivy)
- [x] T0.9 PROGRESS + DECISIONS initialized — 2026-09-25 · ADR-013…ADR-017 appended
- [ ] HA0 received (remote pushed)
- [x] AC0.1 — stack up (`migrate` exited 0, web healthy); `curl localhost:8100/healthz` → `{"status": "ok"}` [200] (also with a foreign Host); `/` renders `<h1 …>EDUCORE</h1>`, `/static/css/output.css` 200 (17.7 KB, token classes present)
- [x] AC0.2 — `pytest` in web container: 7 passed (settings import, healthz, readyz public/allowlisted, metrics 403, celery ping, home); `ruff check` + `ruff format --check` clean
- [x] AC0.3 — `docker build .` (prod, no dev deps) OK; container runs `gunicorn` as uid 10001, `/healthz` 200; `check --deploy` with prod settings → "no issues (0 silenced)"
- [x] AC0.4 — `ci.yml` parses; `actionlint` 0 errors; jobs mirror `make lint` / `make test` (+ check --deploy, pip-audit, Trivy)

### Phase 1 — Domain models, seeds, admin
- [x] T1.1 models + translations + history + indexes — 2026-09-25 · all SPEC §2 models (26 + 2 historical), `translation.py` in core/institutions/content, simple-history on Article/Appeal after modeltranslation (history has `_uz_cyrl/_ru/_en`), HNSW + GIN indexes, hex/contrast validators (ADR-007 palette tested)
- [x] T1.2 named migrations + extensions + triggers — 2026-09-25 · `core.0001_postgres_extensions` (vector, pg_trgm, unaccent), descriptive names, DB triggers keep `search_vector` (post text; article title A / lead+ru/en title B / body C); `makemigrations --check` clean
- [x] T1.3 seed_all (create-only) + sync_roles — 2026-09-25 · 5 institutions (+SVG logos, 15 contacts, 40 KPI placeholders), 5 sources, 16 categories, 12 tags, 21 professions, 25 programs (5/institution, 6 levels), 6 pages, 16 FAQ, 4 roles, 13 beat rows; second run creates 0 (ADR-018, ADR-019)
- [x] T1.4 unfold admin for every model — 2026-09-25 · every model registered (filters/search/inlines/actions: mark verified, publish/archive/review/feature/pin, source resolve/backfill/gapcheck/disable, post skip, outbox retry), SPEC §8 sidebar, dashboard callback with live counts, 2FA-only admin (ADR-020). Pipeline actions (reprocess/regenerate/re-translate/merge) arrive with T2.6/T3.4
- [x] T1.5 translit + sanitize + translit_po — 2026-09-25 · `apps/core/translit.py` (207-word golden corpus, both directions + round trip, URLs/mentions/hashtags kept, HTML text nodes only), `apps/core/sanitize.py` (nh3 allowlist, safe schemes, forced rel, apostrophes), `SanitizedHTMLMixin` on every rich field, `scripts/translit_po.py` keeps placeholders (ADR-021)
- [x] T1.6 factories + selectors + query-count tests — 2026-09-25 · 31 factories (each validated with `full_clean`), content + institution selectors, `django_assert_num_queries` tests (lists = 1–2 queries regardless of size); 305 tests green
- [x] AC1.1 — `migrate` (no pending) + `seed_all` ×2 on the dev DB: second run `created …=0` everywhere; `Institution=5`, `Category=16`, `Profession=21`
- [x] AC1.2 — every registered model's changelist returns 200 for a 2FA-verified superuser (test iterates `admin.site._registry`); Unfold sidebar/dashboard render; anonymous → 2FA login, staff without device → setup, TOTP setup wizard confirms a device end-to-end (`apps/accounts/tests/test_admin_2fa.py`, 7 passed); 2FA pages styled with site tokens
- [x] AC1.3 — `pytest apps/core apps/institutions apps/content` → 298 passed; translit tests 218 passed (207-word corpus both directions + round trip)

### Phase 2 — Telegram ingestion
- [x] T2.1 ingestor package — 2026-09-25 · client, leader lock (Lua renew, tolerant to Redis outages), heartbeat, bootstrap/resolve+join, handlers (new/album/edit/delete), normalize → DTO (UTF-16 entities, reactions, forwards), album-aware repository (grouped_id + item-id mapping), bounded media downloader (limits, 120 s), IngestionRequest poller + executors, gap check (two-miss rule), engagement refresh, source refresh loop
- [x] T2.2 commands — 2026-09-25 · `telegram_login` (refuses while leader lock held), `telegram_ingest` (SIGTERM-graceful, exit 2 when unauthorized), `telegram_backfill` (enqueue / `--standalone` guarded), `telegram_gapcheck`, `ingestor_health`
- [x] T2.3 Celery tasks — 2026-09-25 · `telegram.relay_outbox` (SKIP LOCKED, 15-min lock, waits for `ai.process_post`), `request_gapcheck`, `request_engagement_refresh`, `request_media_retry`, `cleanup_outbox`, `media.process_media` (WebP 1600/800/400 + ffmpeg poster), `ops.check_heartbeat` (stale/recovered alerts, sources offline/live); 6 beat rows enabled (ADR-022)
- [x] T2.4 storage — 2026-09-25 · `apps/telegram/storage.py` (local/s3 via Django storages, `telegram/{username}/{yyyy}/{mm}/{message_id}/{n}.{ext}`), `{% media_url media "800" %}` / `{% media_srcset %}` with fallbacks
- [x] T2.5 tests — 2026-09-25 · 66 telegram tests on revived Telethon fixtures + fake client: single, album (+late item), edit (hash change / views only), delete (+partial album), forwarded, service, oversized video, sticker, outbox uniqueness, two concurrent relays (each event once), leader lock, backfill grouping/idempotency/AI limit, FloodWait, gap check, new source picked up without restart
- [x] T2.6 admin + readiness — 2026-09-25 · sources monitor (status, lag, counters, resolve/backfill/gapcheck/disable), posts (raw JSON, media thumbs, skip), media, requests, outbox retry; `/readyz` detail adds heartbeat age + per-source status (allowlist)
- [ ] HA2 received
- [x] AC2.1 — `pytest apps/telegram` → 66 passed; coverage `apps/telegram` **86 %**
- [ ] AC2.2 · [ ] AC2.3 · [ ] AC2.4 — **waiting for HA2** (real Telegram account + test channel); everything they exercise is covered by the fixture tests above

### Phase 3 — AI editorial pipeline
- [x] T3.1 providers, pricing, budget, runs, embeddings, schemas, prompts — 2026-09-25 · `AnthropicProvider` (structured outputs, cacheable system block, typed error mapping), deterministic `MockProvider`, pricing table (+`AI_PRICING_JSON`), atomic `AIBudgetDay` guard, `call_llm` (cache, budget, one schema retry, AIRun), fastembed e5-small custom model + `FakeEmbedding`, Pydantic schemas with word-boundary truncation, prompts `v1/*.md` (ADR-023, ADR-024)
- [x] T3.2 process_post stages — 2026-09-25 · triage → normalize → extract → embed → dedupe (pgvector ±72 h, confirm, merge + refresh) → generate → fact-guard (+1 regeneration) → media select → publish policy → article (history, uz-cyrl translit, tags, gallery) → structured upsert (Event/Admission/Story/Program/Profession) → post-publish (cache bump, ru/en queued, review alert); outbox semantics (lock renewal thread, 5 retries w/ backoff, terminal count, dead after 3, budget parking); idempotent per (post, hash, prompt version); 16 e2e tests
- [x] T3.3 translate, digest, ai_reprocess — 2026-09-25 · `ai.translate_article` (tag-sequence check + one retry, `manual` never overwritten, failures never block uz), `ai.weekly_digest` (previous Mon–Sun, to review), `ai.prune_runs`, `ai_reprocess --post/--failed/--article/--force/--stage translate` (closes dead outbox rows on success)
- [ ] T3.4 editorial admin
- [ ] T3.5 golden set + ai-eval + tests
- [ ] HA3 received
- [ ] AC3.1 · [ ] AC3.2 · [ ] AC3.3 (latency measured: ___ s; cost/post: $___)

### Phase 4 — Public website
- [ ] T4.1 · [ ] T4.2 · [ ] T4.3 · [ ] T4.4 · [ ] T4.5 · [ ] T4.6 · [ ] T4.7
- [ ] AC4.1 · [ ] AC4.2 (scores: perf __ / seo __ / a11y __ / bp __) · [ ] AC4.3

### Phase 5 — Analytics
- [ ] T5.1 · [ ] T5.2 · [ ] T5.3 · [ ] T5.4
- [ ] AC5.1 · [ ] AC5.2

### Phase 6 — Appeals
- [ ] T6.1 · [ ] T6.2 · [ ] T6.3 · [ ] T6.4
- [ ] AC6.1

### Phase 7 — API, hardening, observability
- [ ] T7.1 · [ ] T7.2 · [ ] T7.3 · [ ] T7.4
- [ ] HA7 (optional) received
- [ ] AC7.1 · [ ] AC7.2 · [ ] AC7.3

### Phase 8 — Production deployment
- [ ] T8.1 · [ ] T8.2 · [ ] T8.3
- [ ] HA8 received
- [ ] AC8.1 · [ ] AC8.2 · [ ] AC8.3

### Phase 9 — Verification, QA, handover
- [ ] T9.1 · [ ] T9.2 · [ ] T9.3 · [ ] T9.4
- [ ] HA9 received
- [ ] AC9.1 — Definition of Done verified line by line

## Log (newest first)
| Date | Phase/Task | Note |
|---|---|---|
| 2026-09-25 | Phase 2 | ingestor, commands, tasks, derivatives, heartbeat alerts; AC2.1 green (86 % coverage); AC2.2–2.4 wait for HA2 |
| 2026-09-25 | Phase 1 | models, migrations, seeds, admin + 2FA, translit, sanitizer, factories/selectors; AC1.1–AC1.3 green (305 tests) |
| 2026-09-25 | Phase 0 | bootstrap complete; AC0.1–AC0.4 green; HA0 pending |
| — | — | project bootstrapped from the specification bundle |
