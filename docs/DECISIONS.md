# EDUCORE — Architecture Decision Records

Format: `ADR-NNN — Title` · Status · Context · Decision · Consequences. Append new records; never rewrite
accepted ones (supersede instead).

## ADR-001 — Django 5.2 LTS + Celery monolith with worker processes
**Status:** accepted. **Context:** single developer; needs admin, ORM, i18n, background jobs, strong AI ecosystem.
**Decision:** Django 5.2 LTS (extended support to April 2028), Celery on Redis, one repository, one image, many
processes. **Consequences:** no microservices overhead; upgrade to Django 6.2 LTS planned after April 2027.

## ADR-002 — Telegram ingestion via MTProto user session (Telethon), not Bot API
**Status:** accepted. **Context:** we do not administer the five channels; bots receive channel posts only as admins.
**Decision:** dedicated Telegram user account + Telethon ≥ 1.45 (`catch_up=True`); Bot API reserved via
`TelegramSource.ingest_method="bot"` for channels that later add our bot as admin. **Consequences:** session file is a
secret; strict rate‑limit etiquette; single ingestor process.

## ADR-003 — Transactional outbox in PostgreSQL relayed by Celery beat
**Status:** accepted. **Context:** ingestion must never lose an event even if Redis/Celery is down.
**Decision:** post upsert + outbox row in one transaction; relay every 10 s with `FOR UPDATE SKIP LOCKED`; on_commit nudge.
**Consequences:** at‑least‑once delivery; consumers idempotent by (post, content hash, prompt version).

## ADR-004 — Exactly one ingestor (Redis leader lock) and media downloaded by the ingestor
**Status:** accepted. **Context:** one Telegram session cannot be safely shared by parallel processes; only the
session holder can download media. **Decision:** leader lock with TTL renewal; ingestor downloads originals with
bounded concurrency; derivatives produced by Celery `media` queue. **Consequences:** ingestor is a singleton;
horizontal scaling happens in workers, not in ingestion.

## ADR-005 — Server‑rendered UI with HTMX/Alpine and Tailwind via standalone CLI (no Node)
**Status:** accepted. **Context:** SEO, official site, solo maintenance, real‑time panel needs are modest.
**Decision:** Django templates + HTMX polling + Alpine; `django-tailwind-cli`; vendored ECharts. **Consequences:**
one deploy unit; no JS build; charts configured from JSON endpoints.

## ADR-006 — Content translation via `django-modeltranslation`; uz‑Cyrl by transliteration; ru/en by AI
**Status:** accepted. **Context:** four languages, one of which is a script variant. **Decision:** field‑level
translations with fallback to `uz`; deterministic transliterator for Cyrillic; AI translations queued after
publication and never blocking. **Consequences:** wide tables (4 columns per text field) accepted for simplicity.

## ADR-007 — Validated institution chart palette in fixed order
**Status:** accepted. **Context:** five series must remain distinguishable for color‑vision‑deficient readers in light
and dark themes. **Decision:** palette `#E4552F, #2B6FD6, #1FA463, #9C4DC4, #0E97A5` (FVV, IIV, Bojxona, HMQA, JXU)
validated with the dataviz six‑check validator (OKLCH lightness band, chroma floor, CVD ΔE ≥ 8 adjacent, normal‑vision
floor ≥ 15, contrast ≥ 3:1 on `#FCFCFB` and `#0B1220`); text variants ≥ 4.5:1. `Institution.order` is the series
order. **Consequences:** changing colors or order requires re‑validation; legends + direct labels + table views always present.

## ADR-008 — Auto‑publish by policy, with editorial review as the safety valve
**Status:** accepted. **Context:** the owner's requirement is real‑time publication; official site cannot publish
hallucinations. **Decision:** `publish_mode=auto` gated by fact‑guard, risk flags, confidence and importance;
everything else to review; `review` and `off` modes switchable in admin. **Consequences:** editors monitor the
review queue; prompts versioned and evaluated on a golden set before enabling `auto` in production.

## ADR-009 — All Telegram I/O inside the ingestor via `IngestionRequest`
**Status:** accepted. **Context:** Telethon's SQLite session must not be opened by two processes (locking, update‑state
races). Backfill, gap check, engagement refresh and media retries all need the session. **Decision:** other
processes insert `IngestionRequest` rows; the ingestor polls and executes them; `--standalone` commands refuse to
run while the leader lock is held. **Consequences:** admin actions are asynchronous with visible request status.

## ADR-010 — Create‑only seeds, private attachment storage, proxy‑aware client IP, health middleware
**Status:** accepted. **Context:** review findings. **Decision:** `seed_all` never overwrites owner edits; appeal
attachments live under `PRIVATE_ROOT` and are served only by a staff view; `TrustedProxyMiddleware` derives the
client IP from Caddy's `X-Forwarded-For`; `HealthMiddleware` answers `/healthz` before host/SSL checks.
**Consequences:** rate limits, axes, allowlists and page‑view uniqueness work behind the proxy; container health checks pass.

## ADR-011 — Outbox lock renewal, terminal‑failure counting, no long Celery ETAs
**Status:** accepted. **Context:** Redis broker visibility timeout re‑delivers long‑ETA tasks; relay could re‑dispatch live
tasks. **Decision:** running tasks renew `locked_until` every 2 min; `attempts` counts terminal failures only (dead after 3);
budget exhaustion parks the row with `locked_until` = next 00:05 instead of an ETA. **Consequences:** exactly‑once‑in‑practice.

## ADR-012 — Alpine CSP build, lazy ECharts, two Redis instances, worker split
**Status:** accepted. **Context:** nonce CSP is incompatible with Alpine's eval; embedding model memory; cache eviction vs
locks. **Decision:** `@alpinejs/csp`; ECharts loaded on reveal; `redis` (noeviction) + `redis-cache` (allkeys-lru);
`worker-ai -c 1` holds the model, `worker-media -c 1`, `worker -c 2` for the rest. **Consequences:** predictable memory (< 6 GB total).

<!-- Claude Code: append ADR-013+ below as decisions are made during implementation. -->

## ADR-013 — Tailwind source CSS lives in `assets/css/input.css`, not under `static/`
**Status:** accepted (2026-09-25). **Context:** `django-tailwind-cli` 4.8 warns (W001) that a source CSS inside
`STATICFILES_DIRS` is collected by `collectstatic`, and `CompressedManifestStaticFilesStorage` then fails on its
`@import "tailwindcss"`. CLAUDE.md §4 / T0.7 name `static/src/css/input.css`. **Decision:** keep the source at
`assets/css/input.css` (outside `STATICFILES_DIRS`); the built file goes to `static/css/output.css` (git-ignored,
built in the image). **Consequences:** the path in CLAUDE.md §4 is superseded by this ADR; `make tailwind*` use the setting.

## ADR-014 — Configurable dev host ports with non-default values
**Status:** accepted (2026-09-25). **Context:** the owner's machine already runs other stacks on 80/443, 6379, 8000,
1025/8025 (Docker) and a native PostgreSQL on 5432; publishing the spec defaults would fail. **Decision:** dev
`compose.yaml` publishes only web, db, mailpit and flower, bound to `127.0.0.1`, on ports from `.env`
(`EDUCORE_WEB_PORT=8100`, `EDUCORE_DB_PORT=5442`, `EDUCORE_MAILPIT_PORT=8125`, `EDUCORE_FLOWER_PORT=5655`); Redis is not
published. Inside the compose network every service keeps its standard port (web 8000, db 5432, redis 6379).
**Consequences:** local URLs are `http://localhost:8100/…`; AC checks that mention `localhost:8000` use `8100`.
Production is unaffected (only Caddy publishes 80/443).

## ADR-015 — Celery 5.6 within the pinned 5.x line
**Status:** accepted (2026-09-25). **Context:** CLAUDE.md §3 names Celery 5.5; the resolver picked 5.6.3 for
`celery[redis]>=5.5,<6`. **Decision:** accept 5.6.x (same major, maintained, same configuration surface).
**Consequences:** none for the design; revisit only on a 6.0 release.

## ADR-016 — ECharts stays on 5.x; vendored assets and subset fonts are committed
**Status:** accepted (2026-09-25). **Context:** ECharts 6 is the latest release, the spec pins ECharts 5; a clean
clone must build offline-friendly images. **Decision:** vendor ECharts 5.6.0, htmx 2.0.11, Alpine CSP 3.17.4 and the
Lucide 1.48.0 sprite under `static/vendor/` (versions in `VERSIONS.md`); fonts are Fontsource variable woff2 files
(latin, latin-ext, cyrillic, cyrillic-ext; ≈ 290 KB total) committed under `static/fonts/` and regenerated with
`make fonts` (`scripts/fetch_fonts.py` writes `assets/css/fonts.css`). Tailwind CLI pinned to 4.3.3.
**Consequences:** no network needed for static assets at build time except the Tailwind binary download.

## ADR-017 — Embedding model pre-download moves to Phase 3
**Status:** accepted (2026-09-25). **Context:** DEVOPS §3 pre-downloads the fastembed model during the image build;
nothing uses embeddings before Phase 3 and the ONNX file (~470 MB) dominates build time and image size.
**Decision:** the Phase 0 image does not pre-download it; T3.1 adds the download step (cached in the
`fastembed_cache` volume in dev). **Consequences:** Phase 0 images are smaller; AC0.3 is unaffected.

## ADR-018 — Beat schedule rows are created for every task, enabled only once the task exists
**Status:** accepted (2026-09-25). **Context:** `seed_all` must create the full beat schedule (AC5.2), but most tasks
arrive in later phases; beat would otherwise publish unknown task names every few seconds. **Decision:**
`apps/core/services/beat.py` holds the authoritative table (CLAUDE.md §11) and `sync_beat_schedule()` upserts one
`PeriodicTask` per entry with `enabled = task is registered in the Celery app`. **Consequences:** re-running
`seed_all` after a phase lands enables its tasks automatically; the table lives in one place.

## ADR-019 — Seeded institution facts: verified where public, otherwise flagged; no invented codes
**Status:** accepted (2026-09-25). **Context:** SPEC §12 asks for realistic seed content; T1.3 asks to verify names.
**Decision:** names, parent bodies, websites, e-mails and one phone were taken from the channels' about texts and
official sites (gov.uz, akademiya.fvv.uz, akadmvd.uz, proacademy.uz, mgjxu.uz, customs.uz); every institution,
program, profession and metric is `needs_verification=True`; official program classifier codes and KPI values are
left empty rather than guessed. **Consequences:** the owner completes them in admin (HA9); the site shows "—".

## ADR-020 — Relaxed CSP for the admin only; 2FA views under the secret admin path
**Status:** accepted (2026-09-25). **Context:** Unfold renders Alpine expressions and inline styles that need
`unsafe-eval`/`unsafe-inline`; SPEC NFR-SEC-2c requires a strict nonce CSP for the site. **Decision:**
`EducoreCSPMiddleware` replaces `script-src`/`style-src`/`img-src` (without nonce, so `unsafe-inline` is honoured) only
for paths under `/<ADMIN_URL_PATH>/`; the public site keeps `script-src 'self' 'nonce-…'`. django-two-factor-auth
URLs are mounted at `/<ADMIN_URL_PATH>/account/…`, the admin login redirects there, and
`RequireTwoFactorForStaff` sends unverified staff to setup (no device) or to the 2FA login (device, unverified).
**Consequences:** admin attack surface is limited by the secret path, mandatory TOTP, axes lockout and the optional
`ADMIN_IP_ALLOWLIST` (T7.2); the public CSP stays strict.

## ADR-021 — Rule-based transliteration with a loanword list; soft sign is not reconstructed
**Status:** accepted (2026-09-25). **Context:** FR-I18N-5 requires deterministic Latin↔Cyrillic with round-trip tests.
Two things cannot be derived from Latin letters alone: `ц` in loanwords (`sirk`, `stansiya`) and `й`+vowel after a
vowel (`mayor`), and the Cyrillic soft sign `ь` (`kompyuter` → `компьютер`, `fakultet` → `факультет`).
**Decision:** letter rules + `LOANWORDS_TO_CYR` (extendable) + the `-tsiya → -ция` suffix rule; Cyrillic → Latin is
fully rule-based (`ц` → `s`/`ts` by position). Words that need `ь` are not guaranteed; the golden corpus (207 words)
excludes them and editors can correct the `_uz_cyrl` field in admin. Apostrophes are normalized to U+02BB/U+02BC
before transliteration and by the sanitizer on every save (`SanitizedHTMLMixin`). **Consequences:** uz-cyrl is
instant and free; rare loanwords may need a list entry.

## ADR-022 — Ingestion details: relay semantics, album deletes, gap-check misses, beat gap-check role
**Status:** accepted (2026-09-25). **Context:** ARCHITECTURE §3.4's SQL sample increments `attempts` on dispatch, while
the binding semantics (NFR-REL-2, ADR-011) count terminal failures only; CLAUDE.md §11 says `request_gapcheck` enqueues
a request per live source while ARCHITECTURE §3.6 says it only alerts. **Decision:** (1) the relay sets
`locked_until = now() + 15 min` and never touches `attempts`; it does not pick rows until `ai.process_post` is
registered (Phase 2 runs before the AI pipeline exists). (2) `telegram.request_gapcheck` alerts **and** enqueues a
gap-check request only for live sources whose `last_gapcheck_at` is older than 20 min (the ingestor's own 10-min loop
is the normal path). (3) Deleting some items of an album keeps the post, marks those media `deleted_in_telegram` and
emits `telegram.post.edited`; deleting every item archives the post. (4) Two-miss deletion uses a new
`TelegramPost.missing_checks` counter (migration `telegram.0003`). (5) Tests run against the isolated Redis DB 15 and
revive genuine Telethon objects from `fixtures/telethon/*.json` (generated by `scripts/make_telethon_fixtures.py`).
**Consequences:** at-least-once delivery without phantom attempt counts; no duplicate gap checks in normal operation.

## ADR-023 — Anthropic provider: native structured outputs, no sampling parameters, SDK retries off
**Status:** accepted (2026-09-25). **Context:** AI_PIPELINE §1 proposes a forced tool for JSON and `temperature=0.2`.
Current models reject sampling parameters (Sonnet 5 returns 400 for `temperature`), and newer models (Opus 5.5,
Fable 5.1) reject forced `tool_choice`; §1 allows a native structured-output option. **Decision:** `AnthropicProvider`
sends `output_config.format = {type: json_schema, schema: anthropic.transform_schema(Model)}` (unsupported keywords
such as `maxLength` move into descriptions) and always re-validates with Pydantic; the system prompt is one cacheable
block; no `temperature`; `max_retries=0` so Celery owns retries and every attempt is an `AIRun`. Error mapping:
429/408/409/5xx/529 and connection/timeouts → `ProviderTransientError`; other 4xx and `refusal` →
`ProviderPermanentError`; bad JSON or `max_tokens` truncation → one retry with the validation error appended.
**Consequences:** switching `AI_MODEL` to any current Claude model needs no code change.

## ADR-024 — Retry budget per stage, offline embeddings in dev, zero-cost mock runs
**Status:** accepted (2026-09-25). **Context:** AI_PIPELINE §4 caps "3 LLM calls per stage incl. retries" while AS-7
expects "retried 5 times with backoff". **Decision:** within one task attempt a stage makes at most two calls
(original + one schema-correction retry); transient provider errors fail the attempt and Celery retries the task
(`max_retries=5`, backoff ≤ 600 s) — AS-7 wins. Successful stages are cached by `(stage, input_hash, prompt_version)`
so retries resume where they failed. `EMBEDDING_BACKEND=auto` uses deterministic trigram vectors while
`AI_PROVIDER=mock` (no 470 MB download in dev/CI) and fastembed otherwise; production images bake the model in with
`--build-arg PREFETCH_EMBEDDINGS=1` (`manage.py ai_warm_embeddings`). Mock runs are logged with cost 0 so they never
consume the real daily budget. **Consequences:** AS-7 is reproducible; dev stays fully offline.

## ADR-025 — Client IP resolved once by TrustedProxyMiddleware; axes reads REMOTE_ADDR only
**Status:** accepted (2026-09-25). **Context:** SPEC NFR-SEC-2 sets `AXES_IPWARE_PROXY_COUNT=1`, while NFR-SEC-2b
makes `TrustedProxyMiddleware` rewrite `REMOTE_ADDR` from the first `X-Forwarded-For` hop (only when the peer is in
`TRUSTED_PROXY_CIDRS`) and says everything afterwards uses `REMOTE_ADDR`. With ipware, a proxy count of 1 over
`REMOTE_ADDR` alone yields no IP at all, and reading `X-Forwarded-For` again would trust spoofed headers from
untrusted peers. **Decision:** the middleware is first in the stack; axes uses
`AXES_IPWARE_META_PRECEDENCE_ORDER=("REMOTE_ADDR",)` with `AXES_IPWARE_PROXY_COUNT=0`. Rate limits (`key="ip"`),
IP allowlists and page-view hashing already read `REMOTE_ADDR`. **Consequences:** one place decides the client
IP; lockouts work behind Caddy and cannot be dodged with a forged header.

## ADR-026 — Charts read daily rollups; "today" refreshed hourly; page views in Redis
**Status:** accepted (2026-09-25). **Context:** SPEC §6.9 charts must render from aggregated data, but a nightly-only
rollup would hide today's activity until 02:00. **Decision:** time-series charts (activity, categories, posting
heatmap, engagement) read `InstitutionDailyStat`; `analytics.flush_pageviews` (hourly) also re-aggregates today, and
`analytics.aggregate_daily` (02:00) recomputes the last 7 days because Telegram views/forwards keep growing after
publication. Aggregation is idempotent per Asia/Tashkent day. Trend tags, comparison and radar stay live queries
(small, cached 5 min). Page views follow SPEC §2.8: Redis counters + a HyperLogLog of a salted, daily-rotated hash
of IP + user agent (no cookies, no stored IPs); bots, staff, fragments and non-200 responses are not counted; article
views and search terms are drained atomically (`RENAME`) and added to the DB hourly. **Consequences:** charts lag by
at most one hour; request handling never depends on Redis (all counter writes are best effort).

## ADR-027 — Temporary Railway hosting as one all-in-one service
**Status:** accepted (2026-09-26). **Context:** the owner wants the site online on Railway (railway.com) now and
moves to the VPS (Phase 8, `compose.prod.yaml` + Caddy) later. Railway volumes attach to exactly one service, but
web (serves `/media/`), the media worker (writes derivatives), the ingestor (session file, downloads) and the
private appeal attachments all need the same files. **Decision:** one Railway service built from the same
`Dockerfile` runs `docker/railway/start.sh`: wait for DB/Redis → `migrate` → `seed_all` (create-only) → optional
superuser / demo seed → Celery worker (`ingest,default,media`), Celery AI worker (`ai`, `-c 1`), beat, optional
ingestor (`RUN_INGESTOR=1`, restarted in place) and gunicorn on `$PORT`; any core process exiting stops the container
so Railway restarts it. One volume at `/data` (media, private, telegram session, fastembed cache); Railway mounts
volumes as root, so `RAILWAY_RUN_UID=0` is required. Postgres comes from Railway's pgvector template (the
`core.0001` migration creates `vector`, `pg_trgm`, `unaccent`); a single Railway Redis serves broker (db 1), locks
(db 0) and cache (db 2). Django serves `/media/` (`SERVE_MEDIA=true`) because there is no Caddy. The Railway edge is
the only way in, so `TRUSTED_PROXY_CIDRS=0.0.0.0/0,::/0`. The Dockerfile drops its BuildKit cache mount (Railway
rejects cache mounts without its own id format). **Consequences:** no horizontal scaling and one noisy neighbour
(AI worker) shares CPU with web — acceptable for a preview; single Redis without the `noeviction`/`allkeys-lru`
split. Everything reverts to the SPEC topology on the VPS; nothing Railway-specific is read by the application code.

## ADR-028 — Public UI restyled after timeshighereducation.com
**Status:** accepted (2026-09-26). **Context:** the owner asked for the public frontend to look like
timeshighereducation.com (THE). SPEC §7.1–7.2 described a navy/gold palette with serif headlines. **Decision:** keep
the structure, components and every SPEC §6 section; restyle to THE's visual language: black header and footer
(`--color-chrome #09090B`), white body, all-sans bold headings (Manrope, self-hosted, standing in for THE's Open Sans),
violet accent `#6933F7` (links, primary buttons, pill CTA), indigo panels `#272457`/`#432EA7` (table heads, promo
panels), THE's blue-pink-orange gradient (`#4352FF → #DE1B7C → #FE4537`) for the intro headline, active-nav underline,
logo mark and footer bar; 16 px card radius; article tiles without a box (rounded image, bold title, grey kicker);
section headers "Title … Barchasi →". The home page gains THE's intro (gradient headline + 8 section launcher tiles)
before the hero band, and the closing CTA becomes three promo panels (appeal, analytics, admissions). Sequential chart
ramp becomes violet. Institution colours (ADR-007) are unchanged. Source Serif stays only for motivation quotes and
is no longer preloaded. All text pairs checked ≥ 4.5:1 (accent on white 6.15, on `#F4F4F5` 5.59). **Consequences:**
SPEC §7.1–7.2 and §6.2 updated; no copying of THE assets, names or content, only the layout and palette idiom.
Partly superseded by ADR-029.

## ADR-029 — Home and chrome follow the THE homepage spec 1:1
**Status:** accepted (2026-09-26). **Context:** the owner supplied a detailed THE homepage design spec (tokens,
typography, section-by-section layout) and asked for it to be applied exactly. **Decision:** Open Sans (self-hosted
variable woff2, replaces Manrope), grey `#F2F2F2` page with flat white 16 px cards, 944 px content column, 56 px
black sticky header with a red `#E41C38` logo badge and three-line wordmark, `#D5D5D5` 14 px nav links, red user
icon (appeal tracking) and search icon; black full-width dropdown menu on small screens; `#09090B` footer with a
700 px inner column, 40 px link rows, divider, copyright and icons; a round floating button bottom-left (THE's
accessibility button) carries the theme toggle. Home sections are mapped onto THE's blocks without dropping any
SPEC §6.2 content: hero, announcement banner (analytics teaser), 8 feature cards, latest news (4 image cards),
KPI tiles ("jobs" tiles), institutions ("partner" cards), live panel + charts, professions (dark "rankings"
cards), cadets/students ("study abroad"), admissions tiles + programs, gradient profession search ("career
search"), events ("resources"), motivation carousel, appeal banner. Deviations: the desktop nav appears from
1280 px (not 1024 px) because nine Uzbek/Russian links do not fit next to the logo at 1024 px; social icons are
RSS/Telegram/search (no Facebook/X/YouTube/LinkedIn accounts exist); dark mode is kept (SPEC requirement).
Contrast: `#6B6B6B` on `#F2F2F2` 4.76:1, on white 5.33:1. **Consequences:** CSS split into `chrome.css` and
`cards.css`; SPEC §6.2 and §7.2 updated; screenshots at 1280 px and 390 px checked, no horizontal overflow.
