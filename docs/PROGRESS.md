# EDUCORE — Progress (living document)

> Claude Code: update this file after **every** completed task and before every pause. This file plus the
> git history is the source of truth for resuming work after a context reset.

## Current focus
- Phase: **6 — Appeals** (Phases 4–5 done; Phase 3 done except HA3-dependent AC3.3)
- Current task: Phase 6 — T6.1
- Last updated: 2026-09-26, Claude Code
- **Owner priority (2026-09-26): temporary deployment on Railway (railway.com) now; real VPS later (Phase 8).**

## Human actions needed (owner)
| # | Needed for | What exactly | Status |
|---|---|---|---|
| HA0 | Phase 0 | GitHub repository + remote URL; GNU make (`winget install ezwinports.make`); Chrome (Node 22 already present) | done 2026-09-25: `origin` = github.com/diyorbek20037773/educore, `main` pushed, CI green (lint, test, security/pip-audit, build + Trivy); Chrome present; GNU make still missing (optional) |
| HA2 | Phase 2 | `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` from https://my.telegram.org → "API development tools"; dedicated phone number; run `make tg-login` and enter the code; a private test channel you administer | pending |
| HA3 | Phase 3 | `ANTHROPIC_API_KEY` (https://platform.claude.com) | pending |
| HA7 | Phase 7 | optional: Turnstile keys, ops bot token + chat id, SMTP, Sentry DSN | pending |
| HA8 | Phase 8 | VPS (Ubuntu 24.04, ≥ 4 vCPU/8 GB/80 GB), domain + DNS A record, GitHub secrets `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `GHCR_PAT`; your `age` public key for backups | pending |
| HR | Railway preview | Railway account/project: deploy the repo, add **pgvector** + **Redis** templates, a volume at `/data`, the variables from `docs/RAILWAY.md`, generate a domain; send the URL | pending |
| HA9 | Phase 9 | official About/contact texts; verify seeded programs/professions/metrics in admin | pending |

## Blockers
- none (real Telegram ingestion waits for HA2 — work continues with fixtures)

## Open follow-ups
- GNU make is not installed on the dev machine yet (asked in HA0); Phase 0 checks were run with the equivalent
  `docker compose` commands from the Makefile.
- Prod image is 1.45 GB uncompressed (target ≤ 900 MB): trim in T8.1 (static ffmpeg, drop gettext from runtime).
- New appeal UI strings (timeline, e-mails, errors) need ru/en/uz-Cyrl catalog entries (`make messages`).
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
- [x] T3.4 editorial admin — 2026-09-25 · "Koʻrik navbati" proxy (sidebar landing, most important first), article actions regenerate / re-translate ru·en / merge duplicates (`content/services/editorial.py`), original Telegram text side panel, preview link, post "reprocess" action, `ai.regenerate_article` task; AI runs/budget/clusters admins from T1.4
- [x] T3.5 golden set + ai-eval + tests — 2026-09-25 · 20-post golden set (uz-Latn/uz-Cyrl/ru, albums, congratulation, admission, event, ad, greeting), `ai_eval` (accuracy per field, cost, `--min-accuracy`, mock only with `--allow-mock`; CI runs it on the mock), unit tests for every stage, e2e: fixture post → published < 5 s, dedupe (2 sources → 1 article), edit → regenerate + history, delete → archived, budget → queued + alert, fact-guard fail → review, AS-7 (5 retries → terminal, dead after 3), invalid JSON retry; `seed_demo` (40 fixture posts + generated images, offline)
- [ ] HA3 received
- [x] AC3.1 — `pytest apps/ai` green; coverage `apps/ai` **92 %**, `apps/content` **92 %** (full suite 426 passed, overall 91 %)
- [x] AC3.2 — `seed_demo` → **38 published** articles, all with cover, category, tags, sources and uz-cyrl; 10 events, 10 admissions, 2 stories; second run processes 0 posts (list pages themselves render in Phase 4 — re-checked by AC4.1)
- [ ] AC3.3 (latency measured: ___ s; cost/post: $___) — **waiting for HA3** (`ANTHROPIC_API_KEY`)

### Phase 4 — Public website
- [x] T4.1 design system — 2026-09-25 · component layer in `assets/css/components.css`, Alpine CSP components, Lucide subset sprite (79 icons, 19 KB, `make icons`, aliases for renamed icons), PWA icons + default OG image (`make brand-images`), `charts.js` (lazy ECharts, fixed palette, table view, CSV, theme re-render), sparkline SVG tag
- [x] T4.2 pages — 2026-09-25 · all SPEC §6 routes: home (11 blocks), institutions (list, 7 profile tabs, comparison + CSV + charts), news/long-reads (filters, infinite scroll, 410, staff preview, TOC), programs, admissions, hubs, professions, events (list/calendar/.ics), stories, analytics + 7 chart endpoints (JSON/CSV), appeal UI + tracking (backend Phase 6), search (FTS + trigram, Cyrillic→Latin), CMS pages, 404/410/500/503, RSS ×3, i18n sitemaps, robots/humans/manifest; 40 web tests; admin preview link re-asserted
- [x] T4.3 HTMX — 2026-09-25 · live panel polling + filter chips, filter forms (`hx-push-url`, `#results` indicator), infinite scroll (`revealed`), search suggestions (300 ms), lazy chart loading (bound once, survives polling), `hx-boost` on header/footer/breadcrumbs with a top progress bar; boosted and history-restore requests get full pages; drawer scroll lock cleared on boosted swaps
- [x] T4.4 i18n — 2026-09-25 · `i18n_patterns` (uz unprefixed), switcher keeps the path, 768-string catalogs: ru/en written, uz labels for English field names, uz_Cyrl via `translit-po` (format-spec fix), 100 % translated; fallback notice; hreflang uz-Latn/uz-Cyrl/ru/en/x-default; `.mo` compiled in image + CI (not committed)
- [x] T4.5 SEO — 2026-09-25 · i18n sitemaps with alternates (7 sections), RSS ×3, JSON-LD (WebSite, Organization, CollegeOrUniversity, NewsArticle, Event, BreadcrumbList — validated in tests), OG/Twitter (cover or default image), canonical, robots, manifest, humans
- [x] T4.6 perf/security — 2026-09-25 · home/global/chart caches keyed by `content_version`, WhiteNoise, WebP srcset + lazy images, fonts subset, ECharts lazy on reveal, strict nonce CSP (Alpine CSP, `allowEval=false`), `TrustedProxyMiddleware` first (ADR-025), maintenance 503, `Vary` on HTMX headers, Permissions-Policy
- [x] T4.7 tests — 2026-09-25 · 58 web tests: every route 200 in 4 languages, partials are fragments, boosted/history requests get full pages, query counts constant as data grows (news, home, events, programs, professions, stories, search), chart contract + CSV, RSS/sitemap XML, JSON-LD validity, 404/410/preview, maintenance, proxy IP, headers, theme toggle; `apps/web` 83–100 % per module, overall 92 % (484 passed). Playwright e2e left optional
- [x] AC4.1 — 2026-09-25 · `seed_demo` data, `scripts/crawl_check.py` (`make crawl`): **592 sitemap URLs** (all sections × uz/uz-cyrl/ru/en alternates) → all 200, no template leaks, stylesheet on every page; N+1 guarded by the constant-query tests (T4.7); serial dev timings ≈ 0.25 s/page
- [x] AC4.2 — 2026-09-25 · Lighthouse 12 mobile, headless Chrome, prod-like local run (gunicorn, `DEBUG=False`, WhiteNoise compressed statics, HTML uncompressed): `/` perf **96** / a11y **100** / bp **100** / seo **100**; article perf **98–99** / 100 / 100 / 100. Fixed on the way: muted-text contrast (ink-muted no longer used for text), "Yangilangan"/status badges use text-safe gold, CTA button background, footer tap targets, dev media serving (`SERVE_MEDIA`), hero image + serif font preloads. On the Django dev server (no compression) `/` scores perf 88 — re-measure behind Caddy in Phase 8 
- [x] AC4.3 — 2026-09-25 · headless Chrome (puppeteer-core) at 360/768/1280 × light/dark on 18 pages: no horizontal overflow, no console errors, HTMX + Alpine loaded, every chart renders (or shows the no-data state) with its table view, live-panel filter swap and theme toggle work; screenshots reviewed. Fixed: home grid overflow at 360 px (`min-w-0`), radar labels on narrow screens, source link in the "Manba" block (`telegram_url`), empty charts/metric rows

### Phase 5 — Analytics
- [x] T5.1 aggregation — 2026-09-25 · `apps/analytics/services/aggregation.py` (`aggregate_day` per Asia/Tashkent day: posts, articles, TG views/forwards, by category/content type/hour, AI runs + cost, appeals), `stats_rebuild` command, `Institution.stats_cache` refresh, cookie-less page views (Redis + HLL, `PageViewMiddleware`), article views/search terms flushed hourly; tasks `analytics.aggregate_daily` / `flush_pageviews` / `refresh_institution_stats` (ADR-026)
- [x] T5.2 chart services — 2026-09-25 · activity/categories/heatmap/engagement read `InstitutionDailyStat`; tags, comparison, radar live; JSON + CSV, cached 5 min
- [x] T5.3 admin dashboard — 2026-09-25 · Unfold index: KPIs, 14-day posts/published bar chart from `DailyStat`, AI spend vs daily budget (progress), page views + unique visitors, sources table
- [x] T5.4 tests — 2026-09-25 · known counts, Tashkent day boundaries (23:30 vs 00:30 local), deleted posts excluded, idempotent re-aggregation keeps page views, empty days, rebuild/command/task, page-view rules (bots, staff, fragments, errors, boosted), HLL uniques, flush drains once, Redis outage safe; `apps/analytics` 95–100 %
- [x] AC5.1 — 2026-09-25 · `stats_rebuild` on the demo DB: 30 days, 5 institutions; chart endpoints report 38 articles (activity/categories), 39 posts (heatmap), tags 64; `/analitika/` 7 charts + tables render (AC4.3 check), comparison page correct (metrics without values hidden until HA9)
- [x] AC5.2 — 2026-09-25 · `seed_all` → 14 beat rows, 12 enabled; `ops.check_ai_failure_rate` and `ops.review_digest` stay disabled until their tasks exist (Phase 7, ADR-018)

### Phase 6 — Appeals
- [x] T6.1 submission — 2026-09-26 · shared service (`appeals/services/submission.py`): libmagic sniff + extension match (pdf/jpg/png/docx, docx zip check), ≤ 5 MB, private storage opaque names, random `EDC-YYYY-NNNNNN` codes, shared 5/h/IP limit (only accepted submissions count, 429 + `Retry-After`), honeypot, Turnstile (flagged, fails closed), success redirect, tracking page with status timeline (30/m/IP), confirmation e-mail + moderator alert (ops bot/log + `APPEALS_NOTIFY_EMAILS`, no PII) via `appeals.notify_new`
- [x] T6.2 admin inbox — 2026-09-26 · status actions with `answered_at`/`closed_at`, "assign to me", public reply → answered + e-mail (`appeals.notify_reply`, `notified_at`), internal notes, CSV export (BOM, formula-safe), SLA overdue filter (> 15 working days), staff-only attachment download (`appeals.view_appeal`); `anonymize_appeals` (24 months, attachments + applicant messages + history rows, `anonymized_at`)
- [ ] T6.3 API `POST /api/v1/appeals` — with the API in T7.1
- [x] T6.4 tests — 2026-09-26 · 22 appeal tests (happy path + attachment + e-mail, rate limit, invalid attempts not counted, honeypot, invalid/oversized files, Turnstile, tracking timeline/public replies, reply e-mail, notes, SLA, CSV, anonymization, download permission); full suite 520 passed
- [ ] AC6.1

### Interim — Railway preview hosting (owner request 2026-09-26, ADR-027)
- [x] R.1 — 2026-09-26 · `railway.json` (Dockerfile build, `/healthz` check), `docker/railway/start.sh` (migrate, seeds, superuser, optional demo seed, workers, beat, optional ingestor, gunicorn on `$PORT`), Dockerfile without BuildKit cache mount, webp/woff2 MIME types, `docs/RAILWAY.md` (step-by-step + variables); simulated locally as root with prod settings on a fresh DB: migrations + seeds + 38 demo articles, all key pages 200, workers ping, `check --deploy` clean
- [x] R.3 — 2026-09-26 · prod settings reject unfilled `<placeholder>` values and invalid `ADMIN_URL_PATH` with a clear message
- [ ] R.2 — owner creates the Railway project (repo + pgvector + Redis + volume + variables, `docs/RAILWAY.md`) and shares the domain; then smoke-test the live URL

### Interim — THE-style redesign (owner request 2026-09-26, ADR-028)
- [x] D.1 — 2026-09-26 · tokens (black chrome, violet accent, brand gradient, 16 px radius, sans headings), header/footer,
  article tiles, section headers, home intro + launcher + promo panels, violet chart ramp, ru/en/uz‑Cyrl strings;
  verified with headless Edge at 1440 px (light/dark) and 375 px (no horizontal scroll); contrast ≥ 4.5:1; 520 tests

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
| 2026-09-26 | Railway | deploy no longer crashes on `<…>` variable hints; generated SECRET_KEY/admin path on the volume (ADR-032) |
| 2026-09-26 | Redesign | `/muassasalar/` in THE rankings wallpaper layout: sub-nav, rotating featured banner, navy side rails with stat badges from real data, mobile strip (ADR-031); 545 tests |
| 2026-09-26 | Redesign | full-width layout, no empty side areas on wide screens (ADR-030) |
| 2026-09-26 | Redesign | THE homepage spec applied 1:1: Open Sans, grey page + white cards, 56 px black header, new home layout (ADR-029); 520 tests |
| 2026-09-26 | Redesign | public UI restyled after timeshighereducation.com (ADR-028); Railway placeholder guard |
| 2026-09-26 | Phase 6 / Railway | appeals backend + inbox + anonymization (T6.1, T6.2, T6.4); Railway all-in-one deployment prepared and simulated (ADR-027); 520 tests |
| 2026-09-25 | Phase 3 | providers, full process_post pipeline, translations, digest, editorial admin, golden set, seed_demo; AC3.1–3.2 green; AC3.3 waits for HA3 |
| 2026-09-25 | Phase 2 | ingestor, commands, tasks, derivatives, heartbeat alerts; AC2.1 green (86 % coverage); AC2.2–2.4 wait for HA2 |
| 2026-09-25 | Phase 1 | models, migrations, seeds, admin + 2FA, translit, sanitizer, factories/selectors; AC1.1–AC1.3 green (305 tests) |
| 2026-09-25 | Phase 0 | bootstrap complete; AC0.1–AC0.4 green; HA0 pending |
| — | — | project bootstrapped from the specification bundle |
