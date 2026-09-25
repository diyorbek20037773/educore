# EDUCORE — System Architecture

This document explains **how** the system is built so that a single developer can operate it reliably.
Read together with `SPEC.md` (what) and `AI_PIPELINE.md` (editorial AI).

---

## 1. Context

```
                        ┌───────────────────────────┐
   Telegram (MTProto)   │  5 official channels       │
   ─────────────────────┤  @fvvakad_uz …             │
                        └─────────────┬─────────────┘
                                      │ updates / history / media
                                      ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                              EDUCORE                                    │
   │  ingestor ─► PostgreSQL (posts, media, outbox) ─► Celery workers (AI)    │
   │      │                 ▲            │                     │              │
   │      └── object storage│            └── Redis (broker, cache, locks)     │
   │                        │                                                 │
   │  Django web (site, admin, API) ◄────────────────────────────────────────┤
   └──────────────────────────────────────────────────────────────────────────┘
          ▲                     ▲                       ▲
     Visitors (uz/ru/en)   Editors (admin, 2FA)   Anthropic API (AI), ops bot
```

## 2. Processes (containers) — one image, many commands

| Service | Command | Replicas | Notes |
|---|---|---|---|
| `web` | `gunicorn config.wsgi:application -w 3 --threads 4 -t 60` | 1 (2 later) | WhiteNoise for static; behind Caddy; `PROMETHEUS_MULTIPROC_DIR=/tmp/prom` (tmpfs); `DATABASE_POOL=true` |
| `worker` | `celery -A config worker -Q ingest,default -c 2 -Ofair` | 1 | outbox relay, requests, stats, ops; `acks_late`, prefetch 1; limit 768 MB |
| `worker-ai` | `celery -A config worker -Q ai -c 1 -Ofair` | 1 (scale by replicas) | loads the ONNX embedding model once (≈ 500 MB); limit 1.5 GB |
| `worker-media` | `celery -A config worker -Q media -c 1` | 1 | Pillow/ffmpeg derivatives; limit 1 GB |
| `beat` | `celery -A config beat -S django_celery_beat.schedulers:DatabaseScheduler` | exactly 1 | schedule in DB |
| `ingestor` | `python manage.py telegram_ingest` | exactly 1 (leader lock) | **the only process that talks to Telegram**; limit 1 GB |
| `migrate` | `python manage.py migrate --noinput && python manage.py seed_all` | one‑shot, `restart: "no"` | others `depends_on: condition: service_completed_successfully`; `seed_all` is create‑only |
| `caddy` | Caddy 2 | 1 | TLS, reverse proxy, public media file server (`/media/` only, never `/data/private`) |
| `db` | PostgreSQL 17 + pgvector | 1 | volume, nightly backup |
| `redis` | Redis 7 (`appendonly yes`, `maxmemory 400mb`, `maxmemory-policy noeviction`) | 1 | broker + locks + heartbeat; must not evict |
| `redis-cache` | Redis 7 (`maxmemory 256mb`, `allkeys-lru`) | 1 | Django cache only (`CACHE_URL`) |
| `backup` | cron container (`docker/backup/backup.sh`), `restart: "no"` semantics via cron loop | 1 | pg_dump + media + session → local + S3 |

Dev adds `mailpit` (SMTP UI) and `flower` (optional). Monitoring profile adds `prometheus`, `grafana`,
`celery-exporter`, `node-exporter`, `uptime-kuma` (all optional, see `DEVOPS.md`).

## 3. Telegram ingestion — design

### 3.1 Why MTProto user session (Telethon) and not the Bot API
Bots only receive channel posts from channels where they are **administrators**. We do not control the
five channels, so a user account that has joined them is the only way to receive updates and history.
Both Telethon (Python) and WTelegramClient (C#) are MTProto clients with identical capability; Telethon
is chosen because the rest of the stack is Django/Celery.

Operational rules for the account: dedicated phone number (real SIM, +998), 2FA enabled, only used by the
ingestor, joins only the configured channels, never sends messages, respects `FloodWaitError`. The
session file is a secret (equivalent to being logged in).

### 3.2 Ingestor process (`apps/telegram/ingestor/`)

```
runner.py        asyncio main: leader lock → client → bootstrap sources → register handlers →
                 background loops (heartbeat, source refresh, media queue, IngestionRequest poller (15 s),
                 gap check (10 min), engagement refresh (6 h)) → run_until_disconnected
requests.py      executes IngestionRequest rows: backfill, gapcheck, refresh_engagement, resolve_source, retry_media
client.py        TelegramClient factory (session path, api id/hash, catch_up=True, flood_sleep_threshold=60,
                 request_retries=5, connection_retries=None → infinite with backoff)
bootstrap.py     resolve usernames → entities; join if needed; persist ids/hash/title/about/photo/subscribers
handlers.py      on_new_message / on_album / on_edited / on_deleted (thin: build DTO → repository)
dto.py           TelegramMessageDTO, TelegramMediaDTO (pure dataclasses; no Telethon types leak past here)
normalize.py     Telethon Message → DTO (text, entities, links, hashtags, media descriptors, hash)
media.py         MediaDownloader: bounded asyncio queue (concurrency 2), size limits, storage upload,
                 marks TelegramMedia downloaded/failed, completion futures per post
repository.py    SYNC functions with transaction.atomic (upsert_post, mark_deleted, add_outbox, …);
                 called via sync_to_async(thread_sensitive=True)
leader.py        Redis lock acquire/renew/release; heartbeat writer
backfill.py      iter_messages with grouping by grouped_id, throttling, idempotency
gapcheck.py      compare latest ids/edit dates with DB; ingest missing; two‑miss deletion rule
```

Handler flow for a new single message:

```
NewMessage (chat in active sources, grouped_id is None)
  → normalize → DTO
  → repository.upsert_post(dto)                     # transaction: post row (status pending), media rows (pending)
  → if media: await downloader.download_all(post)  # originals → storage (timeout 120 s total)
  → repository.finalize_post(post_id)              # transaction: content_hash final, has_media, outbox event
                                                   # on_commit → telegram.relay_outbox.delay()
```

Albums use Telethon's `events.Album` (collects items that arrive within a short quiet period) and the
`NewMessage` handler ignores messages whose `grouped_id` is not None. The album's caption is the text of the
item that has one. The post is looked up/created by (`source`, `grouped_id`) — unique partial index — so a
late album item or a catch‑up burst delivering the same album again only **adds media** to the existing post
(never a second post). `telegram_message_id` of the post = the lowest id seen in the group; every item id is
stored on `TelegramMedia.telegram_message_id`, and edit/delete events carrying an item id are mapped through it.
Backfill groups by `grouped_id` while iterating (buffer until `grouped_id` changes).

Edits: `MessageEdited` → normalize → if `content_hash` unchanged (e.g., only views changed) → update
`edited_at`/counters only; else update text/media (new media downloaded, removed media marked) →
`telegram.post.edited` outbox event. Deletions: `MessageDeleted` (channel + ids) → `mark_deleted` →
`telegram.post.deleted`. Telethon delivers channel deletions with `chat_id`, so mapping to a source is direct.

Source refresh loop (every 60 s): reload active sources from DB; for new ones run bootstrap and extend the
handler chat list (Telethon handlers are re‑registered with the new `chats=[...]`).

### 3.3 Idempotency and ordering
- `UNIQUE(source_id, telegram_message_id)` + `INSERT … ON CONFLICT DO UPDATE` (Django: `update_or_create`
  inside `select_for_update`) makes duplicate updates harmless.
- `content_hash = sha256(normalized_text | sorted(media.file_unique_id))`. Same hash → no new outbox event.
- Outbox uniqueness `(post, event_type, payload_hash)` prevents duplicate events for the same content.
- Consumers key their work on `(post_id, content_hash, prompt_version)` so re‑delivery is a no‑op.

### 3.4 Outbox relay (`telegram.relay_outbox`, queue `ingest`, beat every 10 s + on_commit nudge)

```sql
WITH picked AS (
  SELECT id FROM telegram_ingestionoutbox
  WHERE processed_at IS NULL AND is_dead = FALSE
    AND (locked_until IS NULL OR locked_until < now())
  ORDER BY created_at LIMIT 50
  FOR UPDATE SKIP LOCKED
)
UPDATE telegram_ingestionoutbox o SET locked_until = now() + interval '5 minutes', attempts = attempts + 1
FROM picked WHERE o.id = picked.id RETURNING o.id, o.event_type, o.post_id, o.payload;
```
For each row: `ai.process_post.apply_async(args=[post_id, event_type, outbox_id], queue="ai")`.
Semantics (must be exact):
- The relay sets `locked_until = now() + 15 min` when dispatching; the running task **renews** `locked_until`
  every 2 min (heartbeat inside the task), so a live task is never re‑dispatched.
- `process_post` retries transient provider errors itself (Celery `max_retries=5`, backoff ≤ 10 min, all within
  the renewed lock). On success or terminal skip → `processed_at=now()`. On terminal failure → `last_error`,
  `attempts += 1`, `locked_until = now() + 30 min`; after 3 terminal failures → `is_dead=True` + alert.
- Budget exhausted → task ends normally with `locked_until = next 00:05 Asia/Tashkent`, `attempts` unchanged.
- Admin "retry" resets `attempts`, `is_dead`, `locked_until`.
- The `on_commit` nudge (`relay_outbox.delay()`) is wrapped in `try/except` — if Redis is down the 10 s beat
  relay picks the row up later; nothing is lost.

### 3.5 Leader lock and heartbeat
`SET educore:ingestor:leader <hostname:pid> NX EX 60`; renew every 20 s with a Lua compare‑and‑extend
script. If the key is found held by **another** owner → stop the Telethon client and exit(1) (restart policy
brings it back in standby). If Redis is unreachable → log, keep running, retry every 5 s (compose guarantees a
single replica; ingestion must not stop because Redis is down).
Heartbeat `SET educore:ingestor:heartbeat <iso-ts> EX 180` every 30 s. `ops.check_heartbeat` (beat, 2 min)
alerts once per 30 min while stale and flips sources `offline`; on recovery flips back to `live` and alerts "recovered".

### 3.6 Reconnection and gaps
Telethon reconnects automatically; `catch_up=True` fetches missed updates on reconnect using the saved
update state (in the session file). Because catch‑up is best‑effort, the ingestor's own gap‑check loop (every
10 min per source, and once at start) compares the last 100 messages (ids, edit dates) with the DB. Nothing
outside the ingestor ever opens the Telegram session: Celery tasks and management commands that need Telegram
work insert an `IngestionRequest` row; `telegram.request_gapcheck` (beat) only alerts when `last_gapcheck_at`
is older than 20 min. The Telethon SQLite session must never be opened by two processes (locking + update‑state
races); `telegram_backfill --standalone` therefore refuses to run while the leader lock is held.

## 4. AI pipeline — orchestration (details in `AI_PIPELINE.md`)

`ai.process_post(post_id, event_type, outbox_id)` — single task, sequential stages, each stage
idempotent via `AIRun.input_hash` (skips with `status=cached` when the same input was processed with the
same prompt version). Retries: `autoretry_for=(ProviderTransientError,)`, `retry_backoff=True`,
`retry_backoff_max=600`, `max_retries=5`, `acks_late=True`. Budget guard runs before each paid call.
Translations run as separate tasks (`ai.translate_article`) after publication so they never delay uz.

## 5. Web tier

- Django views in `apps/web/views/` grouped by section; selectors in `apps/*/selectors.py`; HTMX partials
  return template fragments; `django-htmx` middleware; `hx-boost` on nav.
- Caching: `cache_page` is **not** used (language/theme variations); instead fragment caching via
  `{% cache %}` with keys including language + version tag, and selector‑level caching (`cache.get_or_set`)
  for home/institution aggregates (30–60 s). Invalidation: signal on Article publish/unpublish bumps a
  `content_version` key that is part of every fragment key.
- Static: WhiteNoise (`CompressedManifestStaticFilesStorage`) inside the image; Caddy caches immutable assets.
  Media: local volume served by Caddy at `/media/` (`MEDIA_BACKEND=local`) or S3 URLs (`s3`).
- Sitemaps and RSS via Django contrib; regenerated lazily with caching (1 h) and bumped on publish.

## 6. Data lifecycle

| Data | Retention |
|---|---|
| Telegram posts/media/raw JSON | forever (audit); deletions are flags |
| AIRun outputs | 180 days full payloads, then payload pruned (keep tokens/cost) — `ai.prune_runs` monthly |
| Outbox rows | processed rows deleted after 30 days — `telegram.cleanup_outbox` daily |
| Celery results | `ignore_result=True` on periodic tasks; `result_expires` 1 day |
| Appeals | PII anonymized 24 months after close |
| Daily stats | forever |
| Backups | 7 days local, 30 days off‑site |

## 7. Failure modes and responses

| Failure | Detection | Response |
|---|---|---|
| Telegram session revoked / account logged out | ingestor exits with `AuthKeyUnregisteredError`; heartbeat stale | alert (ops bot); owner runs `make tg-login`; nothing lost — gap check + backfill window recovers |
| FloodWait | Telethon exception | sleep the required seconds (cap 1 h), log, continue; backfill throttled |
| Channel renamed / username changed | resolve fails at refresh | source `degraded` + alert; admin edits username; ids stay valid |
| Media download fails | downloader exception/timeouts | media `failed`, post still finalized (article without that media); `telegram.request_media_retry` (beat, 6 h) enqueues an `IngestionRequest(retry_media)` for 3 days |
| Worker crash mid‑pipeline | Celery `acks_late` re‑delivers | idempotent stages resume; `AIRun` cached results reused |
| AI API outage | transient errors | retries w/ backoff; then outbox `attempts` grows; dead after 5 (alert); admin retry |
| Budget exhausted | `AIBudgetDay.is_exhausted` | posts stay `queued`; alert; next day relay resumes |
| DB down | healthz red; Caddy 503 page | restart policy; alerts from uptime‑kuma (optional) |
| Redis down | broker errors | ingestor keeps running (lock renewal tolerates connection errors) and writing outbox rows (DB) — nothing lost; on_commit nudge swallowed; relay resumes when Redis is back |
| Disk > 80 % | host cron `df` check → ops bot | prune derivatives/logs; backfill media capped by `TELEGRAM_BACKFILL_MAX_MEDIA_MB`; media backups go to S3 via `rclone sync`, not local tars |
| Disk full | node‑exporter/`df` cron alert at 85 % | prune media derivatives, rotate logs, expand volume |
| Duplicate ingestor instance | leader lock | second instance idles in standby |

## 8. Scaling path (not needed for v1, but nothing blocks it)
- `web` replicas behind Caddy; `worker` replicas per queue; read replicas for analytics;
  move media to S3/CDN (`MEDIA_BACKEND=s3`); pgvector HNSW is fine up to millions of rows;
  50–100 sources are only DB rows (one ingestor session can follow hundreds of channels).

## 9. Key sequence: live post to publication (target ≤ 60 s)

```
t+0s   Telegram update received (Telethon)
t+0.2s post + media rows inserted (pending); media downloads start (2 concurrent)
t+8s   originals stored; finalize → outbox event; on_commit → relay
t+9s   ai.process_post starts: triage → extract (Haiku, ~3 s) → embed (local, 50 ms) → dedupe (pgvector, 5 ms)
t+14s  generate (Sonnet, ~12 s) → fact‑guard (Haiku, ~4 s) → media select → structured upsert
t+31s  publish policy → Article published; cache bumped; sitemap bumped; live panel shows it on next poll (≤ 30 s)
t+32s  translate tasks queued (ru, en) → done within ~40 s; uz‑cyrl transliterated instantly
```
