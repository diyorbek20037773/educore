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
