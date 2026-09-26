# EDUCORE — Functional & Technical Specification (SPEC)

Status: **binding**. Every numbered requirement (`FR-…`, `NFR-…`) is a deliverable. Companion documents:
`ARCHITECTURE.md` (how), `AI_PIPELINE.md` (editorial AI), `DEVOPS.md` (infra), `PHASES.md` (order of work).

---

## 1. Purpose, scope, actors

### 1.1 Purpose
A single official web platform that (a) mirrors, in real time, the official Telegram channels of five
law‑enforcement education institutions of Uzbekistan, (b) converts each post into a professionally written,
structured, multilingual article via an AI editorial pipeline, and (c) presents institutions, programs,
admissions, students/cadets, professions, events, motivation stories, appeals and analytics as a
Times‑Higher‑Education‑style dashboard site.

### 1.2 In scope
Telegram ingestion (live + history), AI editorial pipeline with auto‑publish policy, public multilingual
site with dashboards and charts, admin/editorial panel, appeals module, analytics, public read‑only API,
RSS, search, SEO, DevOps (Docker, CI/CD, backups, monitoring, hardening).

### 1.3 Out of scope (v1)
Mobile apps, user accounts for the public, comments, newsletters, payment, LMS features, Telegram Bot
API ingestion (reserved via `TelegramSource.ingest_method`), Kubernetes.

### 1.4 Actors
| Actor | Description |
|---|---|
| Visitor | Public reader (applicants, students, cadets, parents, staff, journalists). No login. |
| Editor | Staff user reviewing/approving/editing AI drafts, managing content. 2FA mandatory. |
| Moderator | Staff user handling appeals (Murojaat). 2FA mandatory. |
| Analyst | Staff user with read‑only access to dashboards/exports. |
| Admin (Owner) | Full access, settings, users, sources, AI budget. |
| Ingestor | System process holding the Telegram session. |
| AI pipeline | System workers producing drafts/translations/structured data. |

---

## 2. Domain model

Conventions: every model has `created_at`, `updated_at` (abstract `TimeStampedModel`), explicit
`Meta.ordering`, `__str__`. `*` after a field = translated with `django-modeltranslation`
(`_uz`, `_uz_cyrl`, `_ru`, `_en`). Rich text fields store sanitized HTML (`nh3`, allowlist in
`apps/core/sanitize.py`: `p h2 h3 h4 ul ol li blockquote strong em a[href|rel|target] br figure figcaption img[src|alt|width|height] table thead tbody tr th td`).

### 2.1 `apps.core`
- **SiteSetting** (singleton; `SiteSetting.get()` cached 60 s): `site_name`, `tagline*`, `publish_mode`
  (`auto|review|off`, default from env `PUBLISH_MODE`), `publish_confidence_threshold` (float, default env),
  `on_source_delete` (`archive|keep`), `ai_daily_usd_budget`, `ai_translate_to` (list; default env),
  `live_panel_refresh_seconds` (30), `maintenance_mode`, `contact_email`, `contact_phone`, `address*`,
  `footer_text*`, `social_links` (JSON), `ga_measurement_id` (optional). Precedence: DB value if set,
  else env default (`apps/core/services/settings.py: get_setting(name)`).
- **Page**: `slug`, `title*`, `body*`, `is_published`, `show_in_footer`, `order`, `seo_title*`, `seo_description*`.
- **FAQ**: `question*`, `answer*`, `topic` (choices: `qabul, talim, kursant, talaba, kasb, murojaat, umumiy`),
  `institution` (FK null), `order`, `is_published`.

### 2.2 `apps.accounts`
- **User** (`AbstractUser`, `USERNAME_FIELD = "email"`): `email` (unique), `full_name`, `phone`, `locale`.
  Groups: `admin`, `editor`, `moderator`, `analyst` with permissions defined in
  `apps/accounts/roles.py` (`sync_roles` management command creates/updates them; run by `seed_all`).
- 2FA: `django-two-factor-auth` (TOTP). Middleware `RequireTwoFactorForStaff` redirects any `is_staff`
  user without a confirmed device to setup. Admin login is the two‑factor login view.
- `django-axes`: lock after 5 failed attempts / 30 min, keyed by username+IP.

### 2.3 `apps.institutions`
- **Institution**: `slug` (unique), `short_name*`, `full_name*`, `abbreviation` (FVV, IIV, DBQ, HMQA, JXU),
  `kind` (`academy|institute|university`), `parent_body*` (ministry/agency), `description*` (rich),
  `mission*` (rich), `founded_year`, `website_url`, `telegram_username`, `email`, `phone`, `address*`,
  `city*`, `latitude`, `longitude`, `logo` (image), `hero_image` (image), `color` (hex, validated chart color),
  `color_text` (hex, ≥ 4.5:1 on white), `order` (chart/series order — see §7.4), `is_active`,
  `stats_cache` (JSON, refreshed nightly: `posts_total, posts_30d, articles_total, articles_30d, events_upcoming,
  programs_count, professions_count, tg_subscribers, tg_views_30d, last_post_at`), `needs_verification`.
- **InstitutionContact**: `institution` FK, `kind` (`admissions|press|appeals|general|dormitory`), `title*`,
  `phone`, `email`, `hours*`, `order`.
- **InstitutionMetric**: `institution` FK, `year`, `key` (`students|cadets|faculty|programs|graduates|
  dormitory_places|labs|partners`), `value` (int), `unit*`, `note*`, `source_url`. Unique (`institution, year, key`).
  Editable KPIs shown on profiles and comparison (values seeded as `needs_verification`; empty = "—").
- **Program** (yoʻnalish): `institution` FK, `slug`, `code`, `name*`, `level` (`kurs|bakalavr|magistr|
  qayta_tayyorlash|malaka_oshirish|doktorantura`), `form` (`kunduzgi|sirtqi|masofaviy|aralash`),
  `duration_years` (decimal), `language*`, `description*`, `admission_requirements*`, `qualification*`,
  `quota` (int null), `tuition_note*`, `cover` (image null), `is_active`, `source_url`, `needs_verification`,
  `professions` M2M. Unique (`institution, slug`).
- **Profession** (kasb): `slug` (unique), `name*`, `summary*`, `description*`, `responsibilities*`,
  `requirements*`, `education_path*`, `rank_system*`, `work_places*`, `salary_note*`, `icon` (lucide name),
  `cover` (image null), `institutions` M2M through **ProfessionInstitution** (`program` FK null, `note*`),
  `order`, `is_published`, `needs_verification`.

### 2.4 `apps.telegram`
- **TelegramSource**: `institution` FK (null allowed), `username` (unique, stored lowercase, without `@`),
  `title`, `about_text`, `photo` (image null), `telegram_channel_id` (BigInt, unique, null until resolved),
  `access_hash` (BigInt null), `ingest_method` (`mtproto` default; `bot` reserved), `is_active`,
  `status` (`live|degraded|offline|disabled`), `last_message_id`, `last_message_at`, `last_update_seen_at`,
  `last_gapcheck_at`, `backfill_done_at`, `subscribers_count`, `error_count`, `last_error`, `joined_at`,
  `signature_patterns` (JSON list of regexes stripped from post text before AI; editable).
- **IngestionRequest**: `kind` (`backfill|gapcheck|refresh_engagement|resolve_source|retry_media`), `source` FK
  (null = all), `params` (JSON: `limit`, `ai_limit`, `media_ids`…), `status` (`pending|running|done|failed`),
  `requested_by` FK (User, null), `started_at`, `finished_at`, `result` (JSON), `error`. The ingestor polls
  `pending` rows every 15 s and is the **only** process that executes them (it owns the Telegram session).
  Admin actions and `telegram_backfill`/`telegram_gapcheck` commands just insert rows.
- **TelegramPost**: `source` FK, `telegram_message_id` (BigInt), `grouped_id` (BigInt null, indexed),
  `text` (plain), `entities` (JSON; Telethon entities serialized), `links` (JSON list of URLs), `hashtags`
  (JSON list), `published_at`, `edited_at` (null), `telegram_url`, `content_hash` (sha256 of normalized text +
  sorted media unique ids), `has_media`, `media_count`, `views`, `forwards`, `reactions` (JSON), `reply_to_id`,
  `is_forwarded`, `forward_from` (text), `is_deleted`, `deleted_at`, `is_backfill`, `raw_json` (JSONB),
  `language` (detected, null), `processing_status` (`pending|queued|processing|processed|skipped|failed`),
  `processing_error`, `processed_at`, `skip_reason`, `embedding` (`VectorField(384)`, null), `cluster` FK
  (`ai.EventCluster`, null), `search_vector` (`SearchVectorField`, maintained in `save()`/trigger),
  `importance` (int null, from extraction).
  Constraints: `UNIQUE(source, telegram_message_id)`, `UNIQUE(source, grouped_id) WHERE grouped_id IS NOT NULL`
  (an album is resolved by `grouped_id` first, so late album items or catch‑up bursts never create a second post).
  Indexes: `(source, published_at DESC)`, `(published_at DESC)`, `(processing_status)`, GIN(`search_vector`),
  `pgvector.django.HnswIndex(fields=["embedding"], opclasses=["vector_cosine_ops"])`.
- **TelegramMedia**: `post` FK, `telegram_message_id` (BigInt; album item id), `order`, `kind`
  (`photo|video|document|audio|voice|animation|sticker|webpage|other`), `telegram_file_id` (BigInt: Telethon
  `photo.id` / `document.id`; used in `content_hash`), `mime_type`,
  `size_bytes`, `width`, `height`, `duration_seconds`, `original` (FileField), `derivatives` (JSON:
  `{"1600": key, "800": key, "400": key, "poster": key}`), `caption`, `status`
  (`pending|downloaded|ready|failed`), `error`. Unique (`post, telegram_message_id`).
- **IngestionOutbox**: `id` UUID, `event_type` (`telegram.post.created|telegram.post.edited|telegram.post.deleted`),
  `post` FK, `payload` (JSONB), `payload_hash`, `locked_until` (null), `processed_at` (null), `attempts`,
  `last_error`, `is_dead`. Unique (`post, event_type, payload_hash`). Partial index `WHERE processed_at IS NULL`.

### 2.5 `apps.ai`
- **AIRun**: `post` FK (null), `article` FK (null), `stage` (`triage|normalize|extract|embed|dedupe|generate|
  fact_guard|media_select|structured_upsert|publish_policy|post_publish|translate|regenerate|digest`), `provider`
  (`anthropic|mock|rules|local`), `model` (blank for rule/local stages), `prompt_version`, `input_hash`, `input_tokens`,
  `output_tokens`, `cost_usd` (Decimal 10,6), `duration_ms`, `status` (`ok|failed|skipped|cached`), `error`,
  `request_id`, `output` (JSONB validated result). Indexes: `(post, stage)`, `(created_at)`.
- **AIBudgetDay**: `date` (unique), `usd_spent`, `input_tokens`, `output_tokens`, `runs`, `is_exhausted`.
  Updated atomically (`F()` expressions) by every run; guard checked before each paid call.
- **EventCluster**: `title`, `first_seen_at`, `last_seen_at`, `embedding` (`VectorField(384)`),
  `canonical_article` FK (`content.Article`, null), `posts_count`, `sources_count`.

### 2.6 `apps.content`
- **Category**: `slug` (unique), `name*`, `description*`, `icon` (lucide), `color` (hex), `order`, `parent` FK
  (null), `is_active`, `show_in_nav`. Seed (slug → uz name): `yangiliklar` Yangiliklar; `maqolalar` Maqolalar;
  `talim` Taʼlim; `qabul` Qabul; `talabalar` Talabalar; `kursantlar` Kursantlar; `kasblar` Kasblar;
  `tadbirlar` Tadbirlar; `motivatsiya` Motivatsiya; `ilm-fan` Ilm‑fan; `xalqaro-hamkorlik` Xalqaro hamkorlik;
  `sport` Sport; `manaviyat` Maʼnaviyat va madaniyat; `rahbariyat` Rahbariyat va tashriflar; `elonlar` Eʼlonlar;
  `tabriklar` Tabriklar.
- **Tag**: `slug` (unique), `name*`, `usage_count`.
- **Article**: `slug` (unique; from uz title + 6‑char hash), `title*`, `lead*`, `body*` (sanitized HTML),
  `content_type` (`news|event|admission|program|profession|story|announcement|analysis|digest|other`; mapping from
  extraction: `congratulation|advertisement|service → announcement` with `ai_meta.extracted_content_type` kept),
  `importance` (int 1–5 from extraction; used for hero selection),
  `category` FK, `tags` M2M, `primary_institution` FK (null), `institutions` M2M (denormalized from sources),
  `cover_media` FK (`TelegramMedia`, null), `cover_image` (upload, null), `status`
  (`draft|review|published|archived|rejected`), `review_reason`, `published_at` (null), `source_published_at`,
  `is_featured`, `featured_until`, `is_pinned`, `ai_generated`, `ai_confidence`, `ai_meta` (JSON),
  `cluster` FK (null), `view_count`, `reading_time_min`, `seo_title*`, `seo_description*`, `og_image` (null),
  `author` FK (User, null), `editor` FK (User, null), `edited_at`, `needs_refresh`, `translation_status`
  (JSON per language: `pending|done|failed|manual`), `search_vector`. History: `django-simple-history`
  registered in `AppConfig.ready()` **after** `modeltranslation` has patched the model, so history tables include
  the `_uz_cyrl/_ru/_en` columns (same for `Appeal`).
  Indexes: `(status, published_at DESC)`, `(category, status, published_at DESC)`,
  `(primary_institution, status, published_at DESC)`, `(is_featured, status)`, GIN(`search_vector`).
- **ArticleSource**: `article` FK, `post` OneToOne (`TelegramPost`), `institution` FK, `is_primary`, `added_at`.
- **ArticleMedia**: `article` FK, `media` FK (`TelegramMedia`, null), `image` (upload, null), `order`,
  `caption*`, `is_cover`.
- **Event**: `slug`, `title*`, `description*`, `institution` FK (null), `article` FK (null), `source_post` FK
  (null), `starts_at`, `ends_at` (null), `all_day`, `location*`, `is_online`, `registration_url`, `kind`
  (`seminar|konferensiya|ochiq_eshiklar|tanlov|sport|madaniy|uchrashuv|boshqa`), `cover` (image null),
  `is_published`, `needs_verification`. Property `status` (`upcoming|ongoing|past`). Index `starts_at`.
- **Admission**: `institution` FK, `year`, `title*`, `description*`, `starts_at` (null), `ends_at` (null),
  `programs` M2M, `requirements*`, `documents*`, `quota` (null), `apply_url`, `contact*`, `status`
  (`announced|open|closed`), `source_post` FK (null), `article` FK (null), `is_published`.
  Unique (`institution, year, title`).
- **Story** (motivatsiya): `slug`, `title*`, `person_name`, `person_role*`, `institution` FK (null),
  `quote*`, `body*`, `cover` (image null) / `cover_media` FK (null), `article` FK (null), `source_post` FK (null),
  `is_published`, `published_at`, `order`.

### 2.7 `apps.appeals`
- **Appeal**: `tracking_code` (unique, `EDC-YYYY-NNNNNN`), `institution` FK (null), `topic`
  (`qabul|talim|kursant_talaba|shikoyat|taklif|hamkorlik|boshqa`), `full_name`, `phone`, `email` (blank ok),
  `message`, `consent` (bool), `status` (`new|in_progress|answered|closed|rejected`), `priority`
  (`normal|high`), `assigned_to` FK (User, null), `ip_hash`, `user_agent`, `locale`, `answered_at`,
  `closed_at`, `internal_note`. History enabled.
- **AppealAttachment**: `appeal` FK, `file` (validated: ≤ 5 MB, `pdf|jpg|jpeg|png|docx`; mime sniffed with
  `python-magic`) stored in a **private storage** (`PRIVATE_ROOT=/data/private`, never under `MEDIA_ROOT`, never
  served by Caddy) with opaque random names; downloads only through a staff‑only view
  (`/boshqaruv…/appeals/<id>/attachments/<uuid>/` → `FileResponse`, permission `appeals.view_appeal`),
  `original_name`, `size_bytes`, `mime_type`.
- **AppealMessage**: `appeal` FK, `author` FK (User, null = applicant), `body`, `is_public`, `notified_at`.

### 2.8 `apps.analytics`
- **DailyStat**: `date` (unique), `posts_ingested`, `articles_published`, `articles_review`, `ai_runs`,
  `ai_cost_usd`, `appeals_new`, `pageviews`, `unique_visitors`, `search_queries`.
- **InstitutionDailyStat**: `date`, `institution` FK, `posts`, `articles`, `tg_views_sum`, `tg_forwards_sum`,
  `by_category` (JSON), `by_content_type` (JSON), `by_hour` (JSON, 24 ints). Unique (`date, institution`).
- **SearchLog** (do not name it `SearchQuery` — shadows `django.contrib.postgres.search.SearchQuery`):
  `query_norm` (unique), `count`, `last_searched_at`.
- Page views: no per‑visit rows. Middleware increments Redis counters (`pv:{date}:{path_key}`) and a
  HyperLogLog (`uv:{date}`) keyed by a salted, daily‑rotated hash of IP+UA (no cookies, no PII); an hourly
  task flushes into `DailyStat` and `Article.view_count`.

### 2.9 `apps.ops`
- **AlertEvent**: `kind`, `dedupe_key`, `message`, `sent_at`, `channel` (`telegram|email|log`). Alerts with
  the same `dedupe_key` are throttled to once per 30 min.

---

## 3. Telegram ingestion — functional requirements

- **FR‑TG‑1** The ingestor authenticates as a Telegram **user** (MTProto, Telethon) using `TELEGRAM_API_ID`,
  `TELEGRAM_API_HASH`, session file at `TELEGRAM_SESSION_PATH` (Docker volume). First login is interactive via
  `manage.py telegram_login` (phone → code → optional 2FA password). `telegram_ingest` never prompts; if
  unauthorized it logs a clear error, sets all sources `offline`, alerts, and exits non‑zero.
- **FR‑TG‑2** On start the ingestor resolves every active `TelegramSource` by username, stores
  `telegram_channel_id`, `access_hash`, `title`, `about_text`, avatar and `subscribers_count`; joins the channel
  if not joined; marks it `live`. Failures mark the source `degraded` with `last_error` and continue with others.
- **FR‑TG‑3** Live updates: new messages, edits and deletions in any active source are persisted within
  10 s of receipt. Albums (`grouped_id`) are stored as **one** `TelegramPost` with N `TelegramMedia`, resolved
  by (`source`, `grouped_id`); edit/delete events that carry an album *item* id are mapped to the post through
  `TelegramMedia.telegram_message_id`.
- **FR‑TG‑4** Media originals (photo, video ≤ `TELEGRAM_MAX_MEDIA_MB` (default 200), document ≤ 50 MB,
  audio/voice/animation) are downloaded by the ingestor to storage under
  `telegram/{username}/{yyyy}/{mm}/{message_id}/{n}.{ext}`; larger files are recorded as metadata only
  with a link to the original post. Derivatives (WebP 1600/800/400, video poster) are produced by
  `media.process_media` on the `media` queue.
- **FR‑TG‑5** The outbox event `telegram.post.created` is written in the same transaction as the post once
  all media originals are downloaded or failed/timed out (max wait 120 s). Edits with a changed
  `content_hash` produce `telegram.post.edited`; deletions produce `telegram.post.deleted`.
- **FR‑TG‑6** History backfill: `manage.py telegram_backfill [--source USERNAME] [--limit N] [--ai-limit M]`
  inserts an `IngestionRequest(kind=backfill)`; the running ingestor executes it (`--standalone` runs it
  in‑process and refuses to start while the ingestor leader lock is held). Defaults `TELEGRAM_BACKFILL_LIMIT=500`
  per source, `BACKFILL_AI_LIMIT_PER_SOURCE=150`. Imports the newest N messages (albums grouped), throttled
  (batches of 100, sleep 1.5 s, `FloodWaitError` honored), idempotent (re‑running never duplicates), marks
  posts `is_backfill=True`, emits outbox events only for the newest M posts; for posts beyond M only photos are
  downloaded (videos/documents recorded as metadata + link) to bound disk usage (`TELEGRAM_BACKFILL_MAX_MEDIA_MB=20`).
- **FR‑TG‑7** Gap check (ingestor loop every 10 min per source, plus on demand via `IngestionRequest`): fetch
  the latest 100 messages; ingest any missing; detect edits by comparing `edit_date`; mark ids present in the DB
  but absent from that window as deleted only after two consecutive misses. `telegram.request_gapcheck` (beat)
  only alerts when `last_gapcheck_at` is older than 20 min.
- **FR‑TG‑8** Engagement refresh (ingestor, every 6 h) for posts of the last 7 days (`views`, `forwards`, `reactions`).
- **FR‑TG‑9** Single leader: Redis lock `educore:ingestor:leader` (TTL 60 s, renewed every 20 s). A second
  instance waits in standby. The ingestor exits only when the key is held by **another** owner; on Redis
  connection errors it keeps running (compose guarantees one replica) and retries. Heartbeat key
  `educore:ingestor:heartbeat` written every 30 s; `ops.check_heartbeat` (every 1 min) alerts when stale > 3 min
  and sets sources `offline`; alerts again "recovered".
- **FR‑TG‑10** Source status: `live` (update seen or gapcheck ok within 24 h), `degraded` (errors but running),
  `offline` (ingestor down/unauthorized), `disabled` (`is_active=False`). Shown in admin; per‑source detail is
  exposed on `/readyz` only from `METRICS_IP_ALLOWLIST` or to staff; `/healthz` returns only `{"status": "ok"}`.
- **FR‑TG‑11** Every raw message is preserved (`raw_json`) for audit; nothing is physically deleted.
- **FR‑TG‑12** Adding a 6th source = inserting a `TelegramSource` row in admin; the ingestor picks it up within
  60 s (it re‑reads active sources every minute and re‑registers handlers) — no code change, no restart.

---

## 4. AI editorial pipeline — functional requirements (details in `AI_PIPELINE.md`)

- **FR‑AI‑1** Every outbox event is consumed by `ai.process_post` (queue `ai`), idempotent per
  (`post_id`, `content_hash`, `prompt_version`).
- **FR‑AI‑2** Stages, in order: triage → normalize → extract/classify → embed → dedupe → generate → fact‑guard
  (with one regeneration on failure) → media select → structured upsert → publish policy → post‑publish
  (translations, cache, sitemap, alerts). Each stage writes an `AIRun`.
- **FR‑AI‑3** Publish policy (`auto` default): publish iff fact‑guard passed, no risk flags, `confidence ≥
  threshold`, `importance ≥ 2`, not low‑value, category resolved. Otherwise `status=review` with
  `review_reason`. `review` mode sends everything to review; `off` stores posts only.
- **FR‑AI‑4** Cross‑source duplicate detection merges the same event reported by several institutions into
  one article with multiple `ArticleSource` rows; the article shows all sources.
- **FR‑AI‑5** Edits regenerate and version the article (history); "Yangilangan" badge with time. Source
  deletion archives the article when `on_source_delete=archive`.
- **FR‑AI‑6** Translations: `uz-cyrl` by deterministic transliteration (`apps/core/translit.py`, never AI);
  `ru`/`en` by AI when listed in `ai_translate_to`. Translation failures never block publishing (uz is live,
  other languages fall back to uz with a notice until done).
- **FR‑AI‑7** Cost control: per‑run cost computed from a pricing table (`apps/ai/pricing.py`, env‑overridable);
  daily USD budget guard; when exhausted, drafts are not generated: the task ends normally, the post stays
  `queued`, the outbox row gets `locked_until = next 00:05 Asia/Tashkent` **without** incrementing `attempts`,
  one alert is sent, and the relay resumes it the next day. (No long Celery ETAs — Redis visibility timeout.)
- **FR‑AI‑8** Weekly digest: every Monday 07:00 an `analysis`‑type article "Haftalik sharh" summarizing the
  week per institution is generated to `review` (never auto‑published).
- **FR‑AI‑9** Admin can: re‑process a post, regenerate an article, re‑translate, approve/reject, edit any field,
  see every AIRun with tokens/cost/prompt version, retry dead outbox events.

---

## 5. Multilingual (i18n) requirements

- **FR‑I18N‑1** `LANGUAGES = [("uz","Oʻzbekcha"),("uz-cyrl","Ўзбекча"),("ru","Русский"),("en","English")]`;
  `LANGUAGE_CODE="uz"`; `i18n_patterns(..., prefix_default_language=False)` → `/`, `/uz-cyrl/…`, `/ru/…`, `/en/…`.
- **FR‑I18N‑2** All UI strings via gettext; `.po` for `uz` (source language identity), `uz_Cyrl` generated by
  `scripts/translit_po.py`, `ru`/`en` written by Claude Code and reviewed later.
- **FR‑I18N‑3** Model content via `modeltranslation`; fallback chain `uz-cyrl → uz`, `ru → uz`, `en → uz`.
  When a translation is a fallback, the page shows a small notice "Ushbu sahifa hali tarjima qilinmagan".
- **FR‑I18N‑4** `hreflang` alternates using BCP‑47 tags (`uz-Latn`, `uz-Cyrl`, `ru`, `en`, `x-default`),
  language switcher preserving the current path, `Content-Language`.
- **FR‑I18N‑5** Transliteration module handles: digraphs `sh, ch, ng, oʻ, gʻ`, apostrophe `ʼ` (tutuq), `ye/yo/yu/ya`
  rules at word start/after vowels, `ts` in loanwords (`sirk`→`цирк` exceptions list), capitalization, and
  keeps URLs/emails/hashtags untouched. Round‑trip tests on a 200‑word golden corpus.

---

## 6. Public website — information architecture and pages

### 6.1 Global
- Header: top bar (date in Uzbek, `LIVE` badge with time of last ingested post, language switcher, theme
  toggle, search), logo **EDUCORE** + tagline, primary nav: **Bosh sahifa · Muassasalar · Yangiliklar ·
  Taʼlim (mega: Yoʻnalishlar, Qabul, Talabalar, Kursantlar) · Kasblar · Tadbirlar · Motivatsiya · Analitika ·
  Murojaat**. Sticky, collapses to drawer on mobile.
- Footer: five institutions (logo, name, Telegram link, website), site map, contacts, legal pages,
  "Manba: rasmiy Telegram kanallari" note, copyright.
- Every page: breadcrumbs (JSON‑LD `BreadcrumbList`), `<title>`, meta description, canonical, OG/Twitter
  cards, `hreflang`, skip‑link, print stylesheet.
- HTMX: navigation is full page; partial updates for live panel, filters, infinite scroll, search
  suggestions, chart data loads. `hx-boost` on nav links with `hx-push-url`. Skeletons while loading.

### 6.2 Home `/`
Layout follows the timeshighereducation.com homepage (ADR‑029): grey page, full‑width column (ADR‑030), flat white 16 px cards.
0. **Intro** (ADR‑028/029): two‑line headline with the first word in the brand gradient, one‑sentence lead, LIVE badge;
   an analytics announcement banner (3 mini stats); 8 section feature cards in a 4 × 2 grid (Yangiliklar, Muassasalar,
   Yoʻnalishlar, Qabul, Kasblar, Tadbirlar, Analitika, Murojaat) with an outline icon and a long arrow.
1. **Hero band** ("Soʻnggi yangiliklar"): the 4 selected articles as equal image cards (16:10 cover, bold title,
   meta `date • category`). Selection: `is_pinned` > `is_featured` (valid) > highest `importance` in 24 h.
2. **KPI strip** (5 tiles with sparklines, 30 days): Muassasalar (5), Bugungi yangiliklar, Yaqin tadbirlar,
   Yoʻnalishlar, Kasblar. Tiles link to sections.
3. **Jonli lenta** (live panel): latest 12 published articles across all sources; filter chips
   `Barchasi · FVV · IIV · DBQ · HMQA · JXU` (institution `abbreviation`); HTMX poll every `live_panel_refresh_seconds`; `aria-live=polite`;
   new items slide in with a subtle highlight; shows time‑ago and source badge.
4. **Muassasalar** (THE "partner" cards): five cards (logo, short and full name, 3 KPIs: yangiliklar 30 kun / yoʻnalishlar /
   yaqin tadbirlar, 30‑day sparkline, link to profile).
5. **Charts band** (next to the live panel): "Faollik dinamikasi" (12 months, one line per institution, fixed colors, legend + direct
   end labels, crosshair tooltip) and "Mavzular taqsimoti" (last 30 days by category; horizontal bar, single
   hue). Table view toggle on each chart.
6. **Taʼlim va qabul**: open admissions (countdown to `ends_at`), top programs by institution (tabs), CTA to Qabul.
7. **Kursantlar va talabalar**: latest 6 articles in `kursantlar`/`talabalar` + hub links.
8. **Kasblar**: 5 dark profession cards (cover or icon, summary, institution dots, white name label) + an
   "all professions" card; followed by a gradient profession search banner (keyword + institution).
9. **Tadbirlar**: next 6 events as text items (title, date and time, institution link).
10. **Motivatsiya**: story carousel (quote, person, institution) with round prev/next buttons.
11. **Murojaat CTA** banner (the analytics teaser is the intro banner; Qabul is covered by block 6).
Caching: home fragments cached 30–60 s (Redis), invalidated on publish.

### 6.3 Institutions
- `/muassasalar/` — list in THE's rankings "wallpaper" layout (ADR‑031): white sticky section sub‑nav, rotating
  featured‑institution banner, two sticky navy side rails with red stat badges computed from platform data
  (activity ranks, programs, events, verified metrics only; a strip under the banner below 1280 px), and a white
  panel with a gradient H1, wide institution cards, comparison/analytics/programs cards and the address table
  (Leaflet is **not** used; static map image or OpenStreetMap iframe is optional; default: address + link).
- `/muassasalar/<slug>/` — profile with brand color header, logo, full name, parent body, founded, contacts,
  Telegram subscribers; tabs (server‑rendered sub‑routes): **Umumiy** (description, mission, KPIs from
  `InstitutionMetric`, charts: 12‑month news dynamics, category mix, posting‑hour heatmap), **Yoʻnalishlar**
  (`/yonalishlar/`), **Qabul** (`/qabul/`), **Talabalar va kursantlar** (`/hayot/` — tagged articles + FAQ),
  **Yangiliklar** (`/yangiliklar/` — filtered list), **Tadbirlar** (`/tadbirlar/`), **Aloqa** (`/aloqa/`).
- `/muassasalar/taqqoslash/` — comparison table (metrics × institutions) + grouped bar chart per metric
  (one chart per metric, no dual axes) + radar of normalized indicators; export CSV.

### 6.4 News and articles
- `/yangiliklar/` — grid/list with filters: institution (chips), category, date range, sort; search box;
  infinite scroll (HTMX, `hx-trigger="revealed"`), 24 per page; "Yangilangan" badges; RSS link.
- `/yangiliklar/<slug>/` — article: category + institution chips, title, lead, meta (date, reading time,
  views), cover (WebP srcset, lightbox), body, gallery, tags, **Manba block** ("Ushbu maqola … rasmiy Telegram
  kanalidagi xabar asosida tayyorlandi. [Asl xabarni koʻrish →]" listing all sources), share buttons,
  related articles (same cluster/category/institution), prev/next. JSON‑LD `NewsArticle`.
  `archived` → 410 page with link to institution news; `review/draft` → 404 for public, preview for staff.
- `/maqolalar/` and `/maqolalar/<slug>/` — long‑form (`analysis|digest`) with table of contents.

### 6.5 Education
- `/yonalishlar/` — catalog: filters institution/level/form; cards → `/yonalishlar/<institution>/<slug>/`
  (details table, requirements, related professions, related admission, related news).
- `/qabul/` — per‑institution admission cards with timeline (announced/open/closed), requirements,
  documents, quota, apply link, contact; FAQ block; latest `qabul` articles.
- `/talabalar/` and `/kursantlar/` — hubs: intro (Page), FAQ, latest tagged articles, related events,
  motivation stories, useful contacts (dormitory, etc.).

### 6.6 Professions `/kasblar/`, `/kasblar/<slug>/`
Catalog with search and institution filter; detail: summary, responsibilities, requirements, education
path (which institution/program), rank system, work places, related articles, CTA to programs.

### 6.7 Events `/tadbirlar/`, `/tadbirlar/<slug>/`
List (upcoming/past toggle, institution filter) + month calendar view (server‑rendered grid); detail with
add‑to‑calendar (`.ics` download), map link, source article. `Event` JSON‑LD.

### 6.8 Motivation `/motivatsiya/`, `/motivatsiya/<slug>/`
Story cards with large quotes; detail page; related institution.

### 6.9 Analytics `/analitika/`
Filters (row above charts): date range (30/90/365 days, custom), institution multiselect. Charts:
1. Faollik dinamikasi — daily/weekly posts per institution (line, fixed colors).
2. Kategoriyalar taqsimoti — horizontal bars per institution (small multiples, one hue).
3. Muassasalar taqqoslami — grouped bars per metric (separate charts per metric).
4. Nashr vaqti xaritasi — weekday × hour heatmap (sequential, one hue).
5. Faollik koʻrsatkichlari — avg Telegram views/forwards per post per institution (bars).
6. Trend mavzular — top 15 tags (30 days) with change vs previous period.
7. Qabul jadvali — timeline of admissions per institution.
8. KPI tiles with sparklines; every chart has a table view and CSV download; data via `/analitika/data/<chart>/`.

### 6.10 Appeals `/murojaat/`
Form (institution, topic, full name, phone `+998…` validated, email optional, message ≥ 20 chars,
attachment optional, consent checkbox, Turnstile), rate limit 5/hour/IP, honeypot field, success page
with tracking code and expected SLA text; `/murojaat/kuzatish/` (enter code) → status timeline and
public replies. Email confirmation when email given. Institution contacts sidebar. Moderators get a
Telegram/email alert on new appeals.

### 6.11 Search `/qidiruv/?q=`
PostgreSQL FTS (`unaccent` + `simple` config + `pg_trgm` similarity fallback) over articles, programs,
professions, events, institutions, FAQ; grouped results; suggestions via HTMX (`hx-trigger="keyup changed delay:300ms"`);
query normalization (Cyrillic → Latin translit) so both scripts match; rate‑limited 30/min/IP.

### 6.12 Other pages
`/biz-haqimizda/`, `/aloqa/`, `/maxfiylik-siyosati/`, `/foydalanish-shartlari/` (Pages), `/rss/`,
`/rss/<institution-slug>/`, `/rss/kategoriya/<slug>/`, `/sitemap.xml` (sections + alternates),
`/robots.txt`, `/humans.txt`, `/manifest.webmanifest` (PWA installable, no offline), `/healthz`
(`{"status":"ok"}` if DB + Redis ok; served by `HealthMiddleware` before `SecurityMiddleware`/`CommonMiddleware`,
any `Host`, never redirected), `/readyz` (also checks migrations applied; detailed JSON incl. ingestor heartbeat
age and per‑source status only for `METRICS_IP_ALLOWLIST`/staff), `/metrics` (IP allowlist), custom
404/500/410/503 (maintenance) pages.

---

## 7. Design system

### 7.1 Principles
Official, premium, data‑first — visual language after timeshighereducation.com (ADR‑028): black chrome (header,
footer), white canvas, bold sans headlines, one violet accent, a blue‑pink‑orange gradient used sparingly, rounded
image tiles, section headers with a "Barchasi →" link. 8‑pt spacing, 12‑column grid (max 1320 px), generous
whitespace around numbers. Everything must work in light and dark, on 360 px phones, with keyboard only.

### 7.2 Tokens (Tailwind 4 `@theme` in `assets/css/input.css`)
- Page `--color-page: #F2F2F2`, cards `--color-surface: #FFFFFF`, `--color-surface-2: #F2F2F2`,
  `--color-line: #E2E2E2`; dark: `#0B0B0D`, `#18181B`, `#232326`, `#2E2E33`. Header `#000000` (56 px, sticky,
  `0 5px 5px rgb(0 0 0 / .1)`), footer `#09090B`, in both themes. Logo badge red `#E41C38`.
- Ink: `#232323` body, `#3A3A3A` headings, `#6B6B6B` secondary; dark: `#E4E4E7`, `#FAFAFA`, `#B0B0B0`.
- Layout: full width with 16/32/48 px side gutters (ADR‑030); 24 px grid gaps; 80 px between
  home sections; cards flat at rest, `0 8px 24px rgb(0 0 0 / .08)` + 2 px lift on hover; transitions 0.2 s.
- Brand: indigo `#272457` (900, table heads, panels), `#432EA7` (800), violet accent `#6933F7` (700: links, primary
  buttons, CTA; dark accent `#A78BFA`), `#F0EBFF` (100). Gradient `linear-gradient(225deg, #4352FF 15%, #DE1B7C 86%,
  #FE4537 99%)` for the intro headline, logo mark, active‑nav underline and footer bar only.
- Status: success `#1B7F4C`, warning `#B7791F`, danger `#B42318`, info `#1F55B0` — always icon + label.
- Radius 8/16/24; shadows `sm`/`md` low‑alpha; motion 150–300 ms; `prefers-reduced-motion` respected.
- Typography: UI, body and headlines **Open Sans** (variable 300–800; body 16/24, H1 48/60 bold, section
  titles 26/600, card titles 24/600, meta 12); **Source Serif 4** only for motivation quotes;
  mono **JetBrains Mono** for codes — all self‑hosted woff2 in `static/fonts` (download via `make fonts`),
  `font-display: swap`. Scale: 12/14/16/18/20/24/30/36/48/60.
- Uzbek typography: use `ʻ` (U+02BB) for oʻ/gʻ and `ʼ` (U+02BC) for tutuq belgisi in all UI copy and content;
  sanitizer normalizes `'`, `’`, `‘`, `` ` `` inside Uzbek words to these.

### 7.3 Components (`templates/components/`)
`header`, `mega_nav`, `mobile_drawer`, `live_badge`, `feature_card` (title, text, outline icon, long arrow),
`kpi_tile` (value, label, delta, sparkline),
`article_card` (hero / standard / compact), `institution_card`, `institution_badge` (dot + name),
`category_chip`, `source_attribution`, `chart_card` (title, description, filters slot, canvas, table toggle,
CSV link), `timeline`, `event_row`, `event_calendar`, `profession_card`, `program_table`, `story_card`,
`breadcrumbs`, `pagination`, `infinite_scroll_sentinel`, `search_box`, `language_switch`, `theme_toggle`,
`appeal_form`, `status_badge`, `skeleton`, `toast`, `gallery`, `lightbox`, `share_buttons`, `toc`,
`empty_state`, `notice` (untranslated fallback), `footer`.

### 7.4 Charts (Apache ECharts 5, `static/js/charts.js`)
- One shared theme (`educore-light`, `educore-dark`) registered from CSS variables; charts re‑render on
  theme change. Grid/axes recessive (`#E5E7EB` / `#1F2A44`), 2 px lines, ≥ 8 px markers, 4 px rounded bar
  ends, 2 px gap between stacked segments, tooltips as crosshair (line) or per‑mark (bar/heatmap).
- **Institution categorical palette (validated for CVD and contrast in light and dark; fixed order =
  `Institution.order`; never re‑assigned when a filter hides a series):**

  | order | institution | color | text color |
  |---|---|---|---|
  | 1 | FVV Akademiyasi | `#E4552F` | `#B93A1E` |
  | 2 | IIV Akademiyasi | `#2B6FD6` | `#1F55B0` |
  | 3 | Bojxona instituti | `#1FA463` | `#177A49` |
  | 4 | Huquqni muhofaza qilish akademiyasi | `#9C4DC4` | `#7A36A0` |
  | 5 | Jamoat xavfsizligi universiteti | `#0E97A5` | `#0B7381` |

  Changing any of these requires re‑validation (see `docs/DECISIONS.md` ADR‑007) — do not eyeball.
- Sequential (heatmaps, single‑measure bars): violet ramp `#F0EBFF → #272457` (light), `#2A2440 → #C4B5FD` (dark).
- Never dual axes; two measures → two charts. Legend always for ≥ 2 series plus direct end‑labels for ≤ 4;
  a table view for every chart; values/labels in ink colors, never series colors.
- Sparklines: inline SVG (no ECharts) for KPI tiles and cards.

### 7.5 Accessibility & quality gates
WCAG 2.1 AA: contrast, focus visible, landmark roles, alt text (AI caption fallback: institution + date),
`aria-live` for live panel, keyboard‑navigable menus, form errors linked with `aria-describedby`,
reduced motion. Lighthouse mobile ≥ 90 across four categories on `/` and an article page.

---

## 8. Admin & editorial panel (`django-unfold`, path from `ADMIN_URL_PATH`)

- **Dashboard** (index): today's numbers (incoming posts, processed, needs review, published, failed),
  AI cost today/month vs budget, ingestor status (heartbeat age, per‑source status/lag/last message),
  dead outbox count, open appeals, 14‑day chart of ingested vs published.
- **Tahririyat**: Articles list with filters (status, institution, category, ai_generated, needs_refresh,
  language translation status), preview link, inline sources & media, actions: publish, unpublish/archive,
  send to review, regenerate, re‑translate (`ru`, `en`), feature/pin, duplicate‑merge into another article.
  Editing `body` uses a simple rich editor (TinyMCE via `django-tinymce` or Unfold's built‑in WYSIWYG if available;
  sanitized on save). Side panel shows original Telegram text and link.
- **Telegram**: Sources (status, counters, actions: resolve/refresh info, backfill N, disable), Posts (raw JSON
  viewer, media thumbnails, processing status, actions: reprocess, skip), Media (status, regenerate derivatives),
  Outbox (unprocessed/dead, retry).
- **AI**: Runs (stage, model, tokens, cost, duration, status, output viewer), Budget days, Clusters.
- **Content**: Categories, Tags, Events, Admissions, Programs, Professions, Stories, Pages, FAQ, Institutions,
  Contacts, Metrics (with `needs_verification` filter and bulk "mark verified").
- **Murojaatlar**: inbox with status workflow, assignment, reply (creates `AppealMessage`, emails applicant
  when email given), internal notes, CSV export, SLA overdue filter (> 15 working days).
- **Analitika**: DailyStat/InstitutionDailyStat browse, "rebuild stats" action.
- **Sozlamalar**: SiteSetting singleton; Users/Groups; 2FA devices.
- Permissions per role as in `apps/accounts/roles.py`; all actions logged (`LogEntry` + simple‑history).

---

## 9. Public API (`django-ninja`, `/api/v1/`, OpenAPI `/api/docs`)

Read‑only, JSON, CORS allowlist, django‑ninja built‑in throttling 60/min/IP (`/appeals` 5/hour), ETag + `Cache-Control`.
Endpoints: `GET /institutions`, `/institutions/{slug}`, `/articles?institution=&category=&q=&lang=&page=`,
`/articles/{slug}`, `/events?upcoming=1`, `/programs?institution=`, `/professions`, `/admissions`,
`/stories`, `/stats/overview`, `/stats/activity?days=90&institution=`, `/live` (latest 12),
`/search?q=`; `POST /appeals` (same validation and Turnstile as the form). Versioned schemas in
`apps/api/schemas.py`; language via `?lang=` or `Accept-Language`.

---

## 10. Security & privacy (NFR)

- **NFR‑SEC‑1** Production settings: `DEBUG=False`, `SECURE_SSL_REDIRECT`, HSTS 1 year + preload,
  secure/HttpOnly/SameSite=Lax cookies, `SECURE_PROXY_SSL_HEADER`, `X_FRAME_OPTIONS=DENY`, `Referrer-Policy`,
  `Permissions-Policy`, CSP (nonce‑based scripts, `img-src 'self' data:`, no third‑party except Turnstile),
  `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS` from env; `manage.py check --deploy` must be clean.
- **NFR‑SEC‑2** Admin: non‑default path, mandatory TOTP 2FA, `django-axes` (`AXES_IPWARE_PROXY_COUNT=1`),
  session timeout 12 h, password validators, staff IP allowlist optional (`ADMIN_IP_ALLOWLIST`).
- **NFR‑SEC‑2b** Client IP: `TrustedProxyMiddleware` (first in the stack) sets `REMOTE_ADDR` from the first
  `X-Forwarded-For` hop only when the direct peer is the Caddy container (`TRUSTED_PROXY_CIDRS`, default the
  compose network); all rate limits, axes, IP allowlists and page‑view hashing use `REMOTE_ADDR` afterwards.
  `/metrics` allowlist includes the compose subnet so Prometheus can scrape.
- **NFR‑SEC‑2c** CSP with the Alpine CSP build: `script-src 'self' 'nonce-…'` (no `unsafe-eval`, no `unsafe-inline`),
  `htmx.config.allowEval=false`, `htmx.config.inlineScriptNonce` set from the request nonce; report‑only for the
  first week in prod, then enforced.
- **NFR‑SEC‑3** Input: all AI/editor HTML sanitized with `nh3`; uploads mime‑sniffed and size‑limited;
  appeal form rate‑limited + honeypot + Turnstile; search rate‑limited; API rate‑limited.
- **NFR‑SEC‑4** Secrets only via env; Telegram session file and `.env` are `chmod 600`, in volumes, excluded from
  images; ops bot token separate from Telegram user session. `pip-audit` and Trivy in CI; Dependabot weekly.
- **NFR‑SEC‑5** Privacy: no tracking cookies; page views via salted daily hashes; appeals PII visible only to
  `moderator`/`admin`; `anonymize_appeals` command anonymizes closed appeals older than 24 months; privacy
  policy page; Telegram content republished with attribution and link (official public sources).
- **NFR‑SEC‑6** Containers run non‑root, read‑only root FS where possible, resource limits, DB/Redis not
  published to the host in prod, Caddy the only public listener (80/443).

## 11. Performance & reliability (NFR)

- **NFR‑PERF‑1** TTFB < 300 ms (cached) / < 800 ms (uncached) for home and article pages on a 4 vCPU VPS;
  Lighthouse mobile ≥ 90; images WebP with `srcset`, lazy loading; static via WhiteNoise (hashed, gzip/brotli)
  behind Caddy; fragment caching with explicit invalidation on publish/edit.
- **NFR‑PERF‑2** DB: connection pooling via Django `OPTIONS["pool"]` **only for the `web` process**
  (`DATABASE_POOL=true`; requires `CONN_MAX_AGE=0` — never put `conn_max_age` in `DATABASE_URL`); worker, beat and
  ingestor use plain connections (psycopg pool is not fork‑safe under Celery prefork). All list queries ≤ 8 queries
  (asserted in tests with `django_assert_num_queries`), indexes as in §2.
- **NFR‑REL‑1** Post‑to‑publication latency ≤ 60 s (p95) in auto mode with media ≤ 20 MB.
- **NFR‑REL‑2** No data loss on process crash: ingestion transactions atomic; outbox at‑least‑once; Celery
  `acks_late=True`, `task_reject_on_worker_lost=True`, `broker_transport_options={"visibility_timeout": 3600}`,
  in‑task retries with exponential backoff (Celery `max_retries=5`, ≤ 10 min each); the outbox `locked_until` is
  renewed by the running task every 2 min so the relay never re‑dispatches a live task; outbox `attempts`
  increments only on terminal task failure and the row is `is_dead` after 3 terminal failures (visible in admin).
- **NFR‑REL‑3** Restart safety: ingestor `catch_up=True` + gap check; beat schedule in DB (`django-celery-beat`).
- **NFR‑REL‑4** Backups nightly (DB + media + session) with 7/30‑day retention, restore drill documented.
- **NFR‑OBS‑1** JSON logs with request id/post id; Prometheus metrics (`/metrics` on `web`, `PROMETHEUS_MULTIPROC_DIR`
  on tmpfs): request metrics from `django-prometheus` plus a **custom collector** that computes gauges at scrape
  time from DB/Redis (outbox unprocessed/dead, ingestor heartbeat age, per‑source status, AI cost today, posts
  ingested per source, budget remaining); task durations and queue depth come from `celery-exporter`; alerts via ops bot.

## 12. Seed content requirements

`seed_all` is **create‑only**: `get_or_create` by natural keys (slug/username/key); it never overwrites rows
that already exist (owner edits in admin survive every deploy), except reference rows it owns (roles/permissions
via `sync_roles`, beat schedule entries) which are synced idempotently. `SiteSetting` is created once with env
defaults. Running it twice changes nothing. It creates: 5 institutions with contacts, metrics
placeholders and brand assets (SVG placeholder logos with abbreviation until real logos are uploaded);
5 sources; 16 categories; ~12 tags; ≥ 20 professions (e.g., yongʻin xavfsizligi muhandisi, qutqaruvchi,
bojxona inspektori, tergovchi, tezkor‑qidiruv xodimi, prokuror yordamchisi, kriminalist‑ekspert,
kiberxavfsizlik mutaxassisi, huquqshunos, jamoat xavfsizligi inspektori, patrul‑post xizmati xodimi,
migratsiya xizmati xodimi, yoʻl harakati xavfsizligi inspektori, favqulodda vaziyatlar dispetcheri,
ekologik nazorat inspektori, bojxona kinologi, sudmed ekspert yordamchisi, profilaktika inspektori,
psixolog, IT‑forensika mutaxassisi) with realistic Uzbek content flagged `needs_verification=True`;
≥ 4 programs per institution (levels vary) flagged `needs_verification=True`; Pages (about, contact,
privacy, terms); ≥ 15 FAQ; SiteSetting defaults. `seed_demo` adds ~40 realistic sample Telegram posts
(fixtures in `fixtures/telegram_posts.json`, with placeholder images generated by Pillow) and runs the
pipeline with `AI_PROVIDER=mock` so every page renders with data offline.

## 13. Acceptance scenarios (must be automated where feasible)

| ID | Scenario | Expected |
|---|---|---|
| AS‑1 | Post text+3 photos to a test channel registered as a source | One post, 3 media, outbox event, article published ≤ 60 s with cover + gallery + attribution |
| AS‑2 | Edit that post's text | `edited` event; article regenerated; history entry; "Yangilangan" badge |
| AS‑3 | Delete the post | article `archived`; 410 page; removed from lists/sitemap/RSS |
| AS‑4 | Same news posted by two institutions within 1 h | one article, two sources, both institutions listed |
| AS‑5 | Post "Assalomu alaykum!" with a sticker | `skipped:short_text` (triage rule), no article |
| AS‑6 | Stop the ingestor for 5 min | ops alert "ingestor heartbeat stale" within 4 min; sources `offline`; on restart, "recovered" alert and missed posts ingested (catch‑up/gap check) |
| AS‑7 | AI provider returns 500 on every call | task retried 5 times with backoff, then terminal failure; after 3 terminal failures the outbox row is dead and post `failed`; visible in admin; `ai_reprocess` fixes it |
| AS‑8 | Daily budget exhausted | posts stay `queued`; alert; processed next day |
| AS‑9 | Submit appeal with attachment | tracking code; email; visible in inbox; status update visible on tracking page |
| AS‑10 | Switch to `/ru/` on an article without translation | uz content shown with notice; `hreflang` correct |
| AS‑11 | `make up` on clean clone + `make seed-demo` | site fully browsable offline in < 10 min |
| AS‑12 | `docker compose -f compose.prod.yaml up -d` on VPS | TLS, healthz, admin 2FA enforced, backups scheduled |
