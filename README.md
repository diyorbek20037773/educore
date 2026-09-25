# EDUCORE

**Educore** — Oʻzbekiston Respublikasining beshta huquqni muhofaza qilish taʼlim muassasasi
(FVV Akademiyasi, IIV Akademiyasi, Bojxona instituti, Huquqni muhofaza qilish akademiyasi, Jamoat xavfsizligi
universiteti) rasmiy Telegram kanallarini real vaqtda yigʻib, AI tahririyati orqali maqolaga aylantirib,
Times Higher Education uslubidagi rasmiy dashboard‑sayt sifatida taqdim etuvchi platforma.

Stack: Django 5.2 LTS · PostgreSQL 17 + pgvector · Redis 7 · Celery · Telethon · Anthropic API ·
HTMX + Alpine (CSP build) + Tailwind 4 · Docker Compose · Caddy.

## Quick start (development)

Prerequisites: Docker Desktop (or Docker Engine + compose plugin), Git and GNU make.
Everything else (Python, uv, Tailwind binary, PostgreSQL, Redis) runs inside containers.

```bash
make up          # creates .env from .env.example if missing, builds, migrates, starts the stack
make seed-demo   # reference data + demo articles (mock AI, works offline)
make test        # test suite inside the web container
make lint        # ruff check + format check
```

| URL | What |
|---|---|
| http://localhost:8100/ | public site |
| http://localhost:8100/boshqaruv-7f3a9c/ | admin (create a user with `make createsuperuser`; 2FA is mandatory) |
| http://localhost:8100/healthz | liveness (`{"status": "ok"}`) |
| http://localhost:8125/ | Mailpit (outgoing e-mail in dev) |

Host ports are configurable in `.env` (`EDUCORE_WEB_PORT`, `EDUCORE_DB_PORT`, `EDUCORE_MAILPIT_PORT`) — see ADR-014.
Run `make help` for every command.

## Documentation

| File | Purpose |
|---|---|
| `CLAUDE.md` | Project constitution (stack, rules, commands, workflow, Definition of Done) |
| `PROMPT.md` | Kickoff and resume prompts for Claude Code |
| `docs/TZ_UZ.md` | Toʻliq texnik topshiriq va tushuntirish — oʻzbek tilida (egasi uchun) |
| `docs/SPEC.md` | Functional & technical specification (binding) |
| `docs/ARCHITECTURE.md` | System design, ingestion, outbox, failure modes |
| `docs/AI_PIPELINE.md` | AI editorial pipeline: stages, schemas, prompts, guardrails, cost |
| `docs/DEVOPS.md` | Docker, compose, CI/CD, VPS, backups, monitoring, hardening |
| `docs/PHASES.md` | Ordered execution plan with acceptance checks |
| `docs/PROGRESS.md` | Living progress checklist |
| `docs/DECISIONS.md` | Architecture decision records |

Secrets live only in `.env` (never committed). `.env.example` is the complete contract of every variable.
