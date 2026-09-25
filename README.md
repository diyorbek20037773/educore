# EDUCORE — specification bundle for Claude Code

**Educore** — Oʻzbekiston Respublikasining beshta huquqni muhofaza qilish taʼlim muassasasi
(FVV Akademiyasi, IIV Akademiyasi, Bojxona instituti, Huquqni muhofaza qilish akademiyasi, Jamoat xavfsizligi
universiteti) rasmiy Telegram kanallarini real vaqtda yigʻib, AI tahririyati orqali maqolaga aylantirib,
Times Higher Education uslubidagi rasmiy dashboard‑sayt sifatida taqdim etuvchi platforma.

This folder is **not** the application code. It is the complete specification and operating manual that
Claude Code uses to build the application from scratch, phase by phase, until production.

## Contents

| File | Purpose |
|---|---|
| `CLAUDE.md` | Project constitution read by Claude Code in every session |
| `PROMPT.md` | The single kickoff prompt (and the short resume prompt) |
| `.claude/settings.json` | Pre‑approved commands so Claude Code can work without constant confirmations |
| `docs/TZ_UZ.md` | Toʻliq texnik topshiriq va tushuntirish — oʻzbek tilida (egasi uchun) |
| `docs/SPEC.md` | Functional & technical specification (binding) |
| `docs/ARCHITECTURE.md` | System design, ingestion, outbox, failure modes |
| `docs/AI_PIPELINE.md` | AI editorial pipeline: stages, schemas, prompts, guardrails, cost |
| `docs/DEVOPS.md` | Docker, compose, CI/CD, VPS, backups, monitoring, hardening |
| `docs/PHASES.md` | Ordered execution plan with acceptance checks |
| `docs/PROGRESS.md` | Living progress checklist (Claude Code updates it) |
| `docs/DECISIONS.md` | Architecture decision records |

## Quick start (owner)

1. Create an empty folder, e.g. `educore/`, and copy **everything** from this bundle into it (including the
   hidden `.claude/` folder).
2. Open the folder in VS Code → integrated terminal → `claude` (Claude Code CLI, latest version).
3. Paste the content of `PROMPT.md` (below its first horizontal line) as the first message.
4. Claude Code reads the docs, initializes git, and starts Phase 0. It will report in Uzbek after each phase.
5. When it reaches a human action point (Telegram API keys, Anthropic key, VPS/domain), provide the values in
   `.env` yourself (Claude Code never opens `.env`), then tell it to continue.
6. In any later session: paste the RESUME prompt from the end of `PROMPT.md`.

Prerequisites on your machine: Docker Desktop (or Docker Engine + compose plugin), Git, VS Code, Claude Code.
Everything else (Python, uv, Tailwind binary, PostgreSQL, Redis) runs inside containers.
