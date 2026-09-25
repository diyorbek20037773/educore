# EDUCORE — Progress (living document)

> Claude Code: update this file after **every** completed task and before every pause. This file plus the
> git history is the source of truth for resuming work after a context reset.

## Current focus
- Phase: **0 — Bootstrap**
- Current task: T0.1
- Last updated: (date, by whom)

## Human actions needed (owner)
| # | Needed for | What exactly | Status |
|---|---|---|---|
| HA0 | Phase 0 | GitHub repository + remote URL; Node ≥ 20 + Chrome on the dev machine (Lighthouse) | pending |
| HA2 | Phase 2 | `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` from https://my.telegram.org → "API development tools"; dedicated phone number; run `make tg-login` and enter the code; a private test channel you administer | pending |
| HA3 | Phase 3 | `ANTHROPIC_API_KEY` (https://platform.claude.com) | pending |
| HA7 | Phase 7 | optional: Turnstile keys, ops bot token + chat id, SMTP, Sentry DSN | pending |
| HA8 | Phase 8 | VPS (Ubuntu 24.04, ≥ 4 vCPU/8 GB/80 GB), domain + DNS A record, GitHub secrets `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `GHCR_PAT`; your `age` public key for backups | pending |
| HA9 | Phase 9 | official About/contact texts; verify seeded programs/professions/metrics in admin | pending |

## Blockers
- none

## Phase checklist

### Phase 0 — Bootstrap
- [x] T0.1 repo + .gitignore — 2026-09-25 · `git init -b main`, `.gitignore` + `.gitattributes` (LF enforced for Docker scripts on Windows)
- [x] T0.2 pyproject + uv lock — 2026-09-25 · 139 pkgs locked (Django 5.2.17, Telethon 1.45.0, Celery 5.6.3, anthropic 1.8.0, fastembed 0.8.1)
- [ ] T0.3 Django project + settings split + apps + custom User
- [ ] T0.4 Dockerfile, entrypoint, compose.yaml, .env.example
- [ ] T0.5 Makefile (all targets exist)
- [ ] T0.6 Celery, beat, health endpoints, logging, metrics
- [ ] T0.7 Tailwind, base.html, vendored HTMX/Alpine/ECharts/Lucide, fonts
- [ ] T0.8 ruff/mypy/pytest/pre-commit/CI/README
- [ ] T0.9 PROGRESS + DECISIONS initialized
- [ ] HA0 received (remote pushed)
- [ ] AC0.1 · [ ] AC0.2 · [ ] AC0.3 · [ ] AC0.4

### Phase 1 — Domain models, seeds, admin
- [ ] T1.1 · [ ] T1.2 · [ ] T1.3 · [ ] T1.4 · [ ] T1.5 · [ ] T1.6
- [ ] AC1.1 · [ ] AC1.2 · [ ] AC1.3

### Phase 2 — Telegram ingestion
- [ ] T2.1 · [ ] T2.2 · [ ] T2.3 · [ ] T2.4 · [ ] T2.5 · [ ] T2.6
- [ ] HA2 received
- [ ] AC2.1 · [ ] AC2.2 · [ ] AC2.3 · [ ] AC2.4

### Phase 3 — AI editorial pipeline
- [ ] T3.1 · [ ] T3.2 · [ ] T3.3 · [ ] T3.4 · [ ] T3.5
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
| — | — | project bootstrapped from the specification bundle |
