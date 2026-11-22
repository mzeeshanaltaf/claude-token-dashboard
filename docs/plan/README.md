# Claude Lens: redesign plan

This plan rebuilds **Claude Token Dashboard** as **Claude Lens** ("Usage, cost & workflow analytics for Claude Code"). It has three parts:

- a Next.js + shadcn frontend;
- a FastAPI backend;
- a Postgres database on the Hostinger VPS.

The app is login-protected and deployed with Coolify.

The work is split into 8 phases (00–07). Each phase is implemented in its **own Claude Code session**. Before writing any code, every session follows the [Session handoff protocol](#session-handoff-protocol) below.

## Files in this folder

| File | Purpose |
|---|---|
| `README.md` | This file: decisions, architecture, the phase index and the handoff protocol. **Read it first, every session.** |
| `HANDOFF.md` | The living state: phase status table, the current baton, and the session log. **Read it second, and update it last.** |
| `phase-00-repo-hygiene-and-backend-scaffold.md` … `phase-07-deployment-docs-and-cleanup.md` | One spec per phase: goal, entry criteria, tasks, exit criteria. |

## Phase index

| # | Phase | Delivers |
|---|---|---|
| 00 | [Repo hygiene & backend scaffold](phase-00-repo-hygiene-and-backend-scaffold.md) | `.gitignore` fix, the `backend/` uv project, pure modules ported with their tests |
| 01 | [Postgres schema & batched collector](phase-01-postgres-schema-and-collector.md) | migrations, batched JSONL ingest, skill catalog upload, `sync_runs` |
| 02 | [SQLite migration & daily sync task](phase-02-sqlite-migration-and-daily-sync.md) | a one-time copy of all history into Postgres with a parity check; the scheduled task moved to Postgres |
| 03 | [FastAPI API & auth](phase-03-fastapi-api-and-auth.md) | every existing endpoint ported, server-side pagination, the single-admin login |
| 04 | [Frontend shell & login](phase-04-frontend-shell-and-login.md) | Next.js + shadcn app, API proxy, login page, sidebar shell, date range, privacy blur |
| 05 | [Frontend core pages](phase-05-frontend-core-pages.md) | the redesigned Overview, Prompts, Sessions, Projects, Skills, Tips and Settings pages |
| 06 | [New features](phase-06-new-features.md) | Activity insights, Deep session view, the Tools page, Cmd+K search, CSV export |
| 07 | [Deployment, docs & cleanup](phase-07-deployment-docs-and-cleanup.md) | Docker, the Coolify deploy, rewritten README/CLAUDE.md, the old app removed |

Each phase depends on the ones before it. Phases 05 and 06 can be swapped if needed: 06's backend endpoints only depend on 03.

## Decisions (already made with the user; don't re-litigate)

| Topic | Decision |
|---|---|
| Name | **Claude Lens**. Python package `claude_lens`, CLI `claude-lens`. |
| Frontend | Next.js (latest stable, App Router, TypeScript), Tailwind v4, shadcn/ui, shadcn charts (Recharts), TanStack Query + TanStack Table. Dark theme by default, light theme available. |
| Backend | FastAPI, Pydantic v2, **psycopg 3** (sync) with `psycopg_pool`. **Raw SQL, no ORM.** Managed with `uv` + `pyproject.toml`. |
| Database | The user's Postgres on the Hostinger VPS. `DATABASE_URL` is in `.env.local` at the repo root. **All tables go in the `claude_dashboard` schema**, set via `search_path`. |
| Data flow | Transcripts live on the user's Windows PC, and the dashboard runs on the VPS. A **local collector** pushes to Postgres directly over psycopg. The 30-second rescan loop, `/api/scan` and the SSE stream are dropped; the UI shows "last synced …" instead. |
| Sync cadence | **Daily** (Windows Scheduled Task, 13:00 by default, StartWhenAvailable). Manual `claude-lens scan` is available any time. |
| Users | **Single admin**, created on first boot from `ADMIN_USERNAME`/`ADMIN_PASSWORD`. No sign-up. Change password in Settings; `claude-lens set-password` for recovery. |
| Auth mechanism | Server-side sessions in Postgres (only the sha256 of each token is stored), cookie `cl_session` (HttpOnly, Secure, SameSite=Lax, 7-day sliding expiry), argon2 via `pwdlib`, lockout after 5 failures for 15 minutes. |
| New features in scope | **Activity insights**, **Deep session view**, **Search & export**. (Spend control, i.e. budget and forecast, was **not** selected.) |
| Old app | Kept working until phase 07, then removed (`token_dashboard/`, `web/`, `cli.py`, `start_dashboard.bat`). The local SQLite file is never deleted; it stays as a backup. |
| Git | Push to the `mzeeshanaltaf` remote only, **never `origin`** (see the root `CLAUDE.md`). Commit only when the user asks. |

## Architecture

```
Windows PC                                     Hostinger VPS (Coolify, docker-compose)
┌───────────────────────────┐  psycopg/5432   ┌───────────────┐   ┌────────────────────────┐
│ collector (daily task)    │ ──────────────▶ │ Postgres      │◀──│ backend  FastAPI :8000 │ internal only
│ ~/.claude/projects/*.jsonl│  batched COPY   │ schema        │   └───────────▲────────────┘
│ ~/.claude/skills (catalog)│                 │ claude_dashboard│             │ /api/* proxy
└───────────────────────────┘                 └───────────────┘   ┌───────────┴────────────┐
                                               browser ─HTTPS──▶  │ frontend Next.js :3000 │ public domain
                                                                  └────────────────────────┘
```

The browser only ever talks to Next.js. A catch-all Route Handler (`frontend/app/api/[...path]/route.ts`) proxies requests to `BACKEND_URL` at **runtime** and passes cookies through both ways. Because the browser sees one origin, there's no CORS to configure, and the backend URL isn't baked in at build time.

### Target repo layout

```
backend/
  pyproject.toml, Dockerfile, pricing.json
  claude_lens/
    config.py                 env + tiny .env.local loader
    core/  pricing.py names.py tips.py
    db/    pool.py migrate.py migrations/NNN_*.sql queries/*.py
    collector/ parse.py ingest.py skills_catalog.py migrate_sqlite.py
    api/   main.py auth.py deps.py routers/*.py
    cli.py                    claude-lens scan | migrate-sqlite | status | set-password
  tests/
frontend/                     Next.js app (output: "standalone"), Dockerfile
scripts/install_daily_scan.ps1
docker-compose.yml, .env.example
```

## Facts established during planning (2026-11-22)

- The local SQLite DB at `~/.claude/token-dashboard.db` is 257 MB and holds:
  - **235,402 messages**, **159,328 tool_calls** and **1,085 sessions**, from 2026-02-27 to 2026-11-20;
  - **1,280 tracked files, 75 of which no longer exist on disk.** History therefore has to be **copied** from SQLite; rescanning the JSONLs would lose it.
- `~/.claude/projects` is about 2.6 GB across 59 project folders. `cleanupPeriodDays` is set to 1000.
- Postgres is publicly reachable on port 5432 from the PC, so the collector connects to it directly. The round-trip to the VPS dominates over the network, so ingest **must be batched** (COPY into staging tables), never one `execute()` per line.
- **The original `.gitignore` didn't cover `.env.local`.** Phase 00 fixes this first.
- **Bug to fix in the port.** `/api/prompts` prices only cache-read tokens (`token_dashboard/server.py:181`). The new prompt cost is the full cost of the assistant turn.
- **Hydration rule** (from the user's global CLAUDE.md): any client component that uses `localStorage`, `Date.now()`, `crypto.randomUUID()` or `window` during render or state init must be mounted with `next/dynamic(..., { ssr: false })`. Otherwise you get dead UI.
- **Shell rule** (from the user's global CLAUDE.md): never write files with shell heredocs or here-strings on this machine. Use the Write and Edit tools.
- Toolchain on the PC: Python 3.12.7, uv 0.8.3, Node 24.12, pnpm 10.5.

---

## Session handoff protocol

Every phase runs in a fresh session with no memory of earlier ones. This protocol is how context carries over between them.

### Kickoff prompt (the user pastes this into a new session)

```
Implement phase NN of the Claude Lens redesign. Follow the session handoff
protocol in docs/plan/README.md.
```

### A. Session start: orient before touching code

1. **Read** `docs/plan/README.md` (this file), then `docs/plan/HANDOFF.md`, then the phase file for this session.
2. **Check the entry criteria** in the phase file against `HANDOFF.md`:
   - every earlier phase must be marked `done`, and its exit criteria met;
   - if an earlier phase is `in-progress` or `blocked`, **stop** and tell the user before starting the new one.
3. **Check the repo state:**
   - run `git status` and `git log --oneline -10`;
   - confirm the last commit matches the "Last commit" field in HANDOFF.md;
   - if there are uncommitted changes nobody recorded, ask the user how to treat them.
4. **Check the environment** with the phase's "Environment check" commands (for example, the backend tests pass and Postgres is reachable). If they fail, record this in HANDOFF.md and stop.
5. **Read the "Notes for the next session"** in the latest HANDOFF.md log entry. They override anything in the phase file they contradict, because they reflect what actually happened.
6. **Mark the phase** `in-progress` in the HANDOFF.md status table, with the date.
7. **Tell the user** in 3–5 lines: what you understood the phase to deliver, anything unexpected you found, and your first step. Then start.

### B. During the session

- Work through the phase's task checklist and tick boxes (`- [x]`) in the phase file as you go. That way, if a session dies, the next one can see where it stopped.
- If a decision **deviates from the plan**, ask the user when the decision is theirs. Then record it in the "Decisions & deviations" section of HANDOFF.md, and edit any later phase files it affects.
- Don't do work belonging to later phases. If something is needed early, write it down as a note instead.
- Keep `README.md`'s Decisions table authoritative. Change it only when the user changes a decision.

### C. Session end: hand off

Do this even when the phase is unfinished:

1. **Verify:** run the phase's exit-criteria checks and record the real results (copy the counts and pass/fail lines).
2. **Update HANDOFF.md:**
   - set the phase's row in the status table to `done`, `in-progress` or `blocked`;
   - replace the **Baton** section: current phase, last commit, what works, what doesn't, the exact next step;
   - add a **Session log** entry using the template in HANDOFF.md. Include the files created or changed, commands to rerun, gotchas found, and concrete notes for the next session;
   - add new environment facts (ports, env var names, versions installed), **never secrets**.
3. **Update the phase file:** make sure the ticked boxes match reality, and add a short "Outcome" line at the end.
4. **Commit:** suggest a commit message (conventional commits, e.g. `feat(collector): batched postgres ingest`). Commit or push only if the user agrees, and push only to `mzeeshanaltaf`.
5. **Tell the user** that the phase is done (or what is left), and give them the kickoff prompt for the next phase.

### Rules that apply in every session

- Never print, log, commit or write `DATABASE_URL`, passwords or tokens into docs. Refer to them by env var name.
- Never write to the user's Postgres outside the `claude_dashboard` schema. Tests use a throwaway `claude_lens_test_<random>` schema and drop it afterwards.
- Never delete `~/.claude/token-dashboard.db` or any JSONL transcript.
- The old app (`python cli.py dashboard`) must keep working until phase 07 removes it.
