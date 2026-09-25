# EDUCORE — AI Editorial Pipeline

The pipeline turns a raw Telegram post into a publishable, structured, multilingual article **without
inventing facts**. It is deterministic where it can be (transliteration, rules, embeddings) and uses LLM
calls only where judgment is needed. Every LLM call is schema‑validated, logged with cost, and idempotent.

---

## 1. Provider abstraction (`apps/ai/providers/`)

```python
class AIProvider(Protocol):
    name: str
    def complete_json(self, *, model: str, system: str, user: str, schema: type[BaseModel],
                      max_tokens: int, temperature: float = 0.2, timeout: float = 60.0) -> JSONResult: ...
    def complete_text(self, *, model: str, system: str, user: str, max_tokens: int) -> TextResult: ...

@dataclass
class JSONResult:  data: dict; input_tokens: int; output_tokens: int; request_id: str | None; raw: str
```

- `AnthropicProvider`: uses the `anthropic` SDK. Structured output is obtained by declaring a single tool
  whose `input_schema` is `schema.model_json_schema()` and forcing it with `tool_choice={"type":"tool","name":…}`;
  the tool input is validated with Pydantic (`model_validate`). If the installed SDK exposes a native
  structured‑output/JSON‑schema option, it may be used instead — validation with Pydantic stays mandatory.
  Prompt caching: the long system prompt is sent as a cacheable block (`cache_control: ephemeral`); it only pays
  off above the model's minimum cacheable prefix (Haiku needs a longer prefix than Sonnet), so the cost model below
  assumes **no** cache savings.
  Errors: `RateLimitError`, `APIConnectionError`, 5xx, timeouts → `ProviderTransientError` (retryable);
  4xx (except 429) → `ProviderPermanentError` (fail fast, to review).
- `MockProvider` (`AI_PROVIDER=mock`): deterministic outputs derived from the input text (title = first
  sentence, category by keyword table, confidence 0.9, fact‑guard pass, translations = prefixed copies).
  Used in dev, tests, `seed_demo`. Must exercise every schema field.
- Model selection: `AI_MODEL` (drafting, translation, digest) and `AI_MODEL_FAST` (triage assist,
  classify/extract, fact‑guard, dedupe confirm). Defaults in `.env.example`: `claude-sonnet-5`,
  `claude-haiku-4-5-20251001`. Model ids never appear in code.

Embeddings (`apps/ai/embeddings.py`): `intfloat/multilingual-e5-small` is **not** in fastembed's built‑in
model list, so register it once at import time:
```python
from fastembed import TextEmbedding
from fastembed.common.model_description import PoolingType, ModelSource
TextEmbedding.add_custom_model(
    model="intfloat/multilingual-e5-small", pooling=PoolingType.MEAN, normalization=True,
    sources=ModelSource(hf="intfloat/multilingual-e5-small"), dim=384, model_file="onnx/model.onnx",
)
```
then `TextEmbedding(model_name=EMBEDDING_MODEL, cache_dir=…)` as a lazy singleton, only in `worker-ai`
(`-c 1`; model files pre‑downloaded in the Docker image and cached in volume `fastembed_cache`); input =
`"query: " + normalized text` per e5 convention; output float32[384], L2‑normalized. If the fastembed API
for custom models differs in the installed version, adapt and record an ADR — do not switch the model
(the 384‑dim `VectorField` is a migration). `FakeEmbedding` for tests: feature‑hashed bag of character
trigrams (2^12 buckets folded to 384 dims, L2‑normalized) so near‑identical texts get cosine ≥ 0.9 and unrelated
texts < 0.5 — the dedupe tests depend on this.

Pricing (`apps/ai/pricing.py`, USD per 1M tokens, env‑overridable `AI_PRICING_JSON`):
`claude-sonnet-5: in 2 / out 10`, `claude-haiku-4-5-20251001: in 1 / out 5`, `claude-opus-5-5: in 4 / out 20`.
Unknown model → cost 0 with a warning log (never crash).

---

## 2. Stages of `ai.process_post`

| # | Stage | Kind | Model | Output |
|---|---|---|---|---|
| 1 | load | DB | — | post, media, source, institution, site settings |
| 2 | triage | rules | — | continue / `skipped:<reason>` |
| 3 | normalize | rules | — | clean text, script detection (Latin/Cyrillic), link/hashtag extraction, boilerplate removal |
| 4 | extract | LLM | FAST | `Extraction` (language, content_type, category, audience, importance, entities, structured data) |
| 5 | embed | local | — | 384‑d vector on post |
| 6 | dedupe | pgvector + LLM | FAST (confirm only) | attach to existing cluster/article or create cluster |
| 7 | generate | LLM | MAIN | `Draft` (title, lead, body_html, seo, tags, confidence) |
| 8 | fact_guard | LLM | FAST | `FactCheck` (pass/fail, unsupported claims, risk flags) → one regeneration with feedback |
| 9 | media_select | rules | — | cover + gallery + alt texts |
| 10 | structured_upsert | rules | — | Event / Admission / Story / Program / Profession drafts |
| 11 | publish_policy | rules | — | `published` or `review` (+reason) |
| 12 | post_publish | tasks | — | uz‑cyrl translit, queue ru/en translations, bump caches, sitemap, alerts, stats |

### 2.1 Triage rules (no LLM)
Skip with reason (`skipped:deleted|empty|short_text|sticker_only|service|link_only|forward_short|duplicate_hash`)
when: post deleted; no text and no media; text < 12 words **and** no photo/video;
only emojis/stickers; service messages (pinned, joined); pure link to external site with < 12 words;
`is_forwarded` from a non‑institution source **and** text < 30 words; exact duplicate `content_hash` from
the same source within 7 days. Everything else continues. Skips are visible in admin and can be forced
through `ai_reprocess --force`.

### 2.2 Normalize
- Strip channel signature lines (`@username`, "Rasmiy kanal", trailing link blocks) using per‑source regexes
  stored in `TelegramSource.signature_patterns` (JSON list, editable in admin), plus generic patterns.
- Map extraction `content_type` to `Article.content_type`: `congratulation|advertisement|service → announcement`
  (original kept in `ai_meta.extracted_content_type`); everything else 1:1.
- Detect script: Cyrillic ratio > 0.6 → `uz-cyrl` or `ru` (LLM decides which; normalizer only flags script).
- Keep hashtags as candidate tags (`#kursantlar` → `kursantlar`), links as `links`.
- Build `source_text` (for prompts) = cleaned text + list of media descriptors ("[photo 1/3]", "[video 45 s]").

### 2.3 Extraction schema (`apps/ai/schemas.py`)
```python
class Person(BaseModel):  name: str; role: str | None = None
class EventData(BaseModel):  title: str; starts_at: datetime | None; ends_at: datetime | None; location: str | None; is_online: bool = False; kind: Literal["seminar","konferensiya","ochiq_eshiklar","tanlov","sport","madaniy","uchrashuv","boshqa"]
class AdmissionData(BaseModel): year: int; title: str; starts_at: date | None; ends_at: date | None; programs: list[str]; requirements: str | None; documents: str | None; quota: int | None; apply_url: str | None
class StoryData(BaseModel): person_name: str; person_role: str | None; quote: str | None
class ProgramData(BaseModel): name: str; level: str | None; duration_years: float | None
class ProfessionData(BaseModel): name: str; summary: str | None
class Extraction(BaseModel):
    language: Literal["uz","uz-cyrl","ru","en","mixed","other"]
    content_type: Literal["news","event","admission","program","profession","story","announcement","congratulation","advertisement","service","other"]
    category_slug: str                      # must be one of the seeded slugs (validator)
    audience: list[Literal["applicants","students","cadets","staff","public"]]
    importance: int = Field(ge=1, le=5)
    is_low_value: bool
    low_value_reason: str | None = None
    summary_uz: str = Field(max_length=300)  # one sentence, uz‑Latn
    tags: list[str] = Field(max_length=8)
    persons: list[Person] = []
    organizations: list[str] = []
    places: list[str] = []
    dates: list[str] = []                    # ISO‑8601 when resolvable, else literal
    event: EventData | None = None
    admission: AdmissionData | None = None
    story: StoryData | None = None
    program: ProgramData | None = None
    profession: ProfessionData | None = None
```

### 2.4 Dedupe
1. Candidates: posts from **other** sources with `published_at` within ±72 h, `embedding <=> vector < 0.14`
   (cosine distance; i.e., similarity ≥ 0.86), limit 5, ordered by distance. Same‑source candidates only when
   similarity ≥ 0.97 (repost).
2. If any candidate has a cluster with a canonical article → LLM confirm (`DedupeVerdict{same_event, confidence, adds_new_info, reason}`)
   on the pair of texts. If `same_event` and `confidence ≥ 0.7`: attach post to cluster; add `ArticleSource`;
   if `adds_new_info` → set `needs_refresh=True` and regenerate the canonical article with all sources
   (once per new source). Stage ends; **no new article**.
3. Else create a new `EventCluster` (embedding = post embedding) and continue.

### 2.5 Draft schema
```python
class Draft(BaseModel):
    title: str = Field(max_length=90)
    lead: str = Field(max_length=220)
    body_html: str                          # allowed tags only (sanitized after)
    seo_title: str = Field(max_length=60)
    seo_description: str = Field(max_length=160)
    tags: list[str] = Field(max_length=6)
    reading_time_min: int = Field(ge=1, le=30)
    confidence: float = Field(ge=0, le=1)   # model's self‑assessment that the draft is faithful & complete
    notes: str | None = None                # anything the editor should know (ambiguities, missing dates)
```
Length policy: source < 60 words → 120–200 words; 60–200 → 200–400; > 200 → 300–600. Never pad.
Length limits on `title/lead/seo_*` are enforced with a `mode="before"` validator that truncates at a word
boundary (adding "…") instead of rejecting — LLMs miss exact character counts often; enums and structure stay strict.

### 2.6 Fact‑guard schema
```python
class FactCheck(BaseModel):
    verdict: Literal["pass","fail"]
    unsupported_claims: list[str]           # sentences/claims not supported by the source text or institution profile
    risk_flags: list[Literal["private_person_pii","minor","graphic","legal_case_named_suspect","political","medical","unverified_number","other"]]
    suggested_fixes: str | None = None
```
`fail` → regenerate once with `unsupported_claims` fed back ("remove or rephrase these"); second `fail` →
`review` with reason `fact_guard_failed`. Any `risk_flags` → `review` (never auto‑publish) with the flags listed.

### 2.7 Media select
Cover = largest photo (by width) of the post; gallery = remaining photos in order; video → poster frame as
cover if no photo; documents listed as attachments (name, size) — not embedded. Alt text: `"{institution short
name}: {title}"`. If no visual media → institution placeholder cover (SVG with abbreviation and brand color).

### 2.8 Structured upsert
Only when `content_type` matches and extraction has the object with required fields:
- `event` → `Event` (`is_published=True` if `starts_at` resolvable and in the future or within 7 days past;
  `needs_verification=True`), linked to article and source post; dedupe by (`institution`, `title` similarity ≥ 0.9, same day).
- `admission` → `Admission` (`is_published=True`, `status` from dates), dedupe by (`institution, year, title`).
- `story` → `Story` (`is_published=True`).
- `program`/`profession` → **unpublished** drafts with `needs_verification=True` (editor decides).

### 2.9 Publish policy
```python
def decide(draft, extraction, factcheck, settings) -> Decision:
    if settings.publish_mode == "off":     return Decision("draft", "publish_mode_off")
    if settings.publish_mode == "review":  return Decision("review", "publish_mode_review")
    if factcheck.verdict != "pass":        return Decision("review", "fact_guard_failed")
    if factcheck.risk_flags:               return Decision("review", "risk:" + ",".join(factcheck.risk_flags))
    if extraction.is_low_value:            return Decision("review", "low_value")
    if extraction.content_type in {"advertisement","service"}: return Decision("review", "content_type")
    if extraction.importance < 2:          return Decision("review", "importance")
    if draft.confidence < settings.publish_confidence_threshold: return Decision("review", "confidence")
    return Decision("published", "auto")
```
`published_at = post.published_at` (keeps chronological order for backfill), `source_published_at` same.

### 2.10 Translations
- `uz-cyrl`: `translit.to_cyrillic()` on title/lead/body (HTML‑aware: text nodes only) at publish time, synchronous.
- `ru`, `en` (per `ai_translate_to`): `ai.translate_article(article_id, lang)` on queue `ai`, MAIN model,
  `Translation{title, lead, body_html, seo_title, seo_description}`; HTML structure must be preserved
  (validator compares tag sequence; mismatch → retry once → `translation_status[lang]="failed"`).
  Editors can mark a language `manual` to stop AI overwrites.

### 2.11 Weekly digest (`ai.weekly_digest`, Monday 07:00 Asia/Tashkent)
Input: titles+leads of the week's published articles per institution (max 60). Output: `analysis` article
"Haftalik sharh: {date range}" with sections per institution, to `review`. Uses MAIN model.

---

## 3. Prompts (`apps/ai/prompts/v1/*.md`, `PROMPT_VERSION = "v1"`)

Prompts are Markdown files loaded at import; `{{placeholders}}` are filled by a single regex substitution
(`re.sub(r"\{\{(\w+)\}\}", …)`) — never `str.format` or `string.Template`, because prompts contain JSON braces.
Every placeholder in the files below uses the double‑brace form. Changing any prompt text requires bumping
`PROMPT_VERSION` (new AIRun cache keys).

### 3.1 `system_editor.md` (shared system prompt — cacheable)
```
Siz EDUCORE platformasining bosh muharririsiz. EDUCORE — Oʻzbekiston Respublikasining beshta huquqni
muhofaza qilish taʼlim muassasasi (FVV Akademiyasi, IIV Akademiyasi, Bojxona instituti, Huquqni muhofaza qilish
akademiyasi, Jamoat xavfsizligi universiteti) rasmiy Telegram kanallaridagi xabarlarni rasmiy veb‑sayt uchun
maqolaga aylantiradigan rasmiy axborot platformasi.

USLUB QOIDALARI
1. Til: oʻzbek tili, lotin yozuvi. Apostroflar: oʻ va gʻ uchun ʻ (U+02BB), tutuq belgisi uchun ʼ (U+02BC).
2. Uslub: rasmiy, neytral, uchinchi shaxs, xabar (news) janri. Reklama, hissiyot, undov, emoji, clickbait yoʻq.
3. Faqat manbada bor faktlar. Manbada yoʻq sana, raqam, ism, lavozim, sabab yoki natijani QOʻSHMANG.
   Aniq boʻlmagan joyni "maʼlum qilinishicha" yoki "xabar berilishicha" bilan bering, toʻqib chiqarmang.
4. Muassasa nomlari va lavozimlar rasmiy shaklda (profil maʼlumotlaridan foydalaning).
5. Sana formati: "25-sentabr, 2026-yil". Raqamlar: 1 000, 12 500 (boʻsh joy bilan). Foiz: 45 %.
6. Har bir maqola manbaga ishora qiladi: "... {{institution_full_name}}ning rasmiy Telegram kanali xabar berdi".
7. Sarlavha: ≤ 90 belgi, fakt asosida, boʻlishli gap, bosh harf faqat birinchi soʻzda va atoqli otlarda.
8. Lid (kirish): 1–2 gap, ≤ 220 belgi: kim, nima, qachon, qayerda.
9. Matn: 2–5 abzats, kerak boʻlsa h2 kichik sarlavhalar va roʻyxatlar. Ruxsat etilgan HTML teglar:
   p, h2, h3, ul, ol, li, blockquote, strong, em, a (faqat manbadagi havolalar), br.
10. Iqtibos faqat manbada aynan mavjud boʻlsa va blockquote ichida.
11. Shaxsiy maʼlumotlar (telefon, manzil, voyaga yetmaganlar ismi) ni manbada boʻlsa ham qisqartiring/olib tashlang,
    faqat rasmiy aloqa maʼlumotlari (qabul komissiyasi telefoni kabi) qoladi.

MUASSASA PROFILI (ishonchli kontekst, faqat shu doirada foydalaning):
{{institution_profile}}

KATEGORIYALAR (slug: nomi): {{categories}}
```

### 3.2 `extract.md` (user prompt, FAST model)
```
Quyidagi Telegram xabarini tahlil qiling va faqat soʻralgan JSON strukturasini qaytaring.
Qoidalar: category_slug faqat berilgan roʻyxatdan; importance: 1 = ahamiyatsiz (tabrik, shior), 3 = oddiy yangilik,
5 = juda muhim (qabul eʼloni, rahbariyat qarori, yirik tadbir); is_low_value = true agar xabar mazmunsiz
(faqat salomlashish, faqat rasm izohsiz, reklama, takroriy shior) boʻlsa; sanalarni ISO 8601 ga keltiring
(yil koʻrsatilmagan boʻlsa xabar sanasi {{post_date}} yiliga asoslaning); tags 3–8 ta, kichik harf, lotin.
Agar xabar tadbir/qabul/hikoya/yoʻnalish/kasb haqida boʻlsa mos strukturani toʻldiring, aks holda null.

MANBA: {{source_name}} ({{source_username}}), sana: {{post_date}}
MATN:
"""
{{source_text}}
"""
MEDIA: {{media_descriptors}}
```

### 3.3 `generate.md` (user prompt, MAIN model)
```
Quyidagi rasmiy Telegram xabari asosida EDUCORE sayti uchun maqola tayyorlang (Draft JSON).
Kategoriya: {{category_name}}. Kontent turi: {{content_type}}. Auditoriya: {{audience}}.
Aniqlangan obyektlar: {{entities_json}}
Uzunlik: {{length_policy}}.
Eslatma: manbada yoʻq faktlarni qoʻshmang; noaniq joylarni notes maydonida muharrirga yozing;
confidence — maqola manbaga qanchalik sodiq va toʻliq ekanini 0–1 oraligʻida baholang.
{{regeneration_feedback}}

MANBA: {{source_name}} ({{source_username}}), sana: {{post_date}}, havola: {{telegram_url}}
MATN:
"""
{{source_text}}
"""
MEDIA: {{media_descriptors}}
{{additional_sources_block}}
```
`additional_sources_block` (dedupe refresh) lists other institutions' texts with the instruction to
write one article that mentions every institution that reported.

### 3.4 `fact_guard.md` (FAST model)
```
Siz fakt tekshiruvchisiz. MANBA matni va MAQOLA berilgan. MAQOLADAGI har bir daʼvo MANBADA yoki MUASSASA
PROFILIDA tasdiqlanganmi, tekshiring. Manbada yoʻq sana, raqam, ism, lavozim, sabab, natija, sifatlash
(masalan "birinchi marta", "eng yirik") — unsupported_claims ga kiriting. Shaxsiy maʼlumotlar, voyaga yetmaganlar,
ayblanuvchi ismlari, siyosiy bahо, tibbiy maʼlumot yoki tekshirib boʻlmaydigan raqamlar boʻlsa risk_flags ga
mos belgini qoʻying. verdict = "fail" agar kamida bitta unsupported_claims boʻlsa.
MANBA: """{{source_text}}"""
MAQOLA (sarlavha, lid, matn): """{{draft_text}}"""
```

### 3.5 `dedupe_confirm.md`, `translate.md`, `digest.md`
Short, single‑purpose prompts in the same style (ru/en translation prompt: preserve HTML tags exactly,
keep institution names official in the target language, keep numbers/dates, no additions).

---

## 4. Guardrails summary
- Schema validation on every call; on validation error → one retry with the error message appended; then fail.
- `nh3` sanitization of `body_html` after generation and after translation.
- Title/lead length enforced by schema; duplicate titles within 7 days get a suffix from the institution.
- Fact‑guard + risk flags gate auto‑publish; regeneration at most once.
- Budget guard: `AIBudgetDay.usd_spent + estimated_cost > budget` → the task ends normally, post `queued`,
  outbox `locked_until = next 00:05 Asia/Tashkent` (no `attempts` increment, no Celery ETA), alert once per day.
- Timeouts: 60 s per call; max 3 LLM calls for extract/generate/fact‑guard each (incl. retries).
- Never call the provider in tests (`AI_PROVIDER=mock` enforced in `settings/test.py`).

## 5. Cost model (for the owner)
Per live post (typical 150‑word source): extract (Haiku, ~2.5k in / 0.4k out) ≈ $0.005; generate (Sonnet,
~3k in / 0.9k out) ≈ $0.015; fact‑guard (Haiku) ≈ $0.004; ru+en translations (Sonnet, 2 × ~1.5k/1k) ≈ $0.026.
**≈ $0.05 per post**, ≈ $0.025 without translations. 25 posts/day → ≈ $1.3/day → **≈ $40/month**;
backfill 5 × 150 posts ≈ $40 once. Set `AI_DAILY_USD_BUDGET=5` for normal operation and raise it to 50 for the
backfill day (otherwise the 750 backfill posts take ≈ 8 days at $5/day) — documented in the runbook.

## 6. Evaluation ("golden set", `apps/ai/tests/golden/`)
20 real‑style posts (uz‑Latn, uz‑Cyrl, ru; with/without media; album; congratulation; admission; event) with
expected `content_type`, `category_slug`, `is_low_value`. `make ai-eval` runs the extract stage against the
live provider (opt‑in, needs key) and prints accuracy; CI runs it against `MockProvider` only for schema
coverage. Target: ≥ 90 % category accuracy before switching `publish_mode` to `auto` in production.
