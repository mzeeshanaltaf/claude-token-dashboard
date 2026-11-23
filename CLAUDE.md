# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Redesign status

This repo was rebuilt as **Claude Lens** in eight phases (00–07). The plan, the decisions made with the user and the per-session log live in [docs/plan/](docs/plan/README.md). Until the redesign is declared complete, read `docs/plan/README.md` and `docs/plan/HANDOFF.md` before any larger change, and add a session log entry to `HANDOFF.md` afterwards.

## Project overview

**Claude Lens**: usage, cost & workflow analytics for Claude Code. A local collector reads the JSONL transcripts Claude Code writes to `~/.claude/projects/` and pushes them to Postgres. A login-protected web app on the VPS turns them into per-prompt cost, daily and per-project spend, cache analytics, activity heatmaps, a deep session view (context growth, tool timeline, subagents), tool/file insights, Cmd+K search, CSV export and a rule-based tips engine.

Production: `https://claude-lens.zeeshanai.cloud` (Coolify on the Hostinger VPS).

## Architecture

```
Windows PC                         Hostinger VPS (Coolify, docker-compose)
collector (daily task) --psycopg--> Postgres (schema claude_dashboard) <-- backend  FastAPI :8000 (internal only)
~/.claude/projects/*.jsonl                                                    ^ /api/* proxy
                                   browser --HTTPS--> frontend Next.js :3000 -+
```

- **Collector** (`backend/claude_lens/collector/`, CLI `claude-lens scan`): incremental (per-file mtime + byte offset in `files`), batched `COPY` into temp staging tables, one transaction per ~5,000 lines. Also uploads the local skill catalog. Runs daily from the Windows Scheduled Task `Claude Lens - Daily Sync` (`scripts/install_daily_scan.ps1`).
- **Backend** (`backend/claude_lens/api/`): FastAPI + psycopg 3 pool, raw SQL, no ORM. Single admin login with server-side sessions (`cl_session` cookie, argon2). Applies migrations on startup.
- **Frontend** (`frontend/`): Next.js 16 App Router + shadcn/ui + TanStack Query/Table + Recharts. A catch-all route handler proxies `/api/*` to `BACKEND_URL` at request time, so the browser sees one origin.

## Layout

```
backend/    pyproject.toml (uv), Dockerfile, pricing.json, claude_lens/, tests/
  claude_lens/config.py          env + tiny .env.local loader
  claude_lens/core/              pure logic: pricing, costs, names, tips, activity, csv_export, session_insights
  claude_lens/db/                pool, migrate, migrations/NNN_*.sql, queries/*.py
  claude_lens/collector/         parse, ingest, skills_catalog, migrate_sqlite
  claude_lens/api/               main, auth, deps, security, schemas*, routers/*
  claude_lens/cli.py             claude-lens scan | status | migrate-sqlite | set-password
frontend/   Next.js app (output: "standalone"), Dockerfile
scripts/install_daily_scan.ps1   the Windows scheduled task
docker-compose.yml               production (Coolify); docker-compose.local.yml for a local smoke test
docs/                            KNOWN_LIMITATIONS.md, plan/, images/
```

More detail: [backend/README.md](backend/README.md) (collector, API, endpoints) and [frontend/README.md](frontend/README.md) (proxy, conventions, page patterns).

## Data source

Claude Code writes one JSONL file per session to `~/.claude/projects/<project-slug>/<session-id>.jsonl`. Each line is a message record; usage fields live at `message.usage` and the model at `message.model`. History older than the transcripts on disk was copied once from the old Token Dashboard SQLite file (`~/.claude/token-dashboard.db`, kept as a backup; never delete it).

## Conventions

- **Self-hosted, no third-party telemetry.** User data goes only to the user's own Postgres and VPS. No analytics, no outbound calls with user data. Tests run offline except the `db`-marked ones, which use a throwaway schema.
- **Minimal, justified deps.** Every new dependency (Python or npm) needs a reason that a few lines of our own code can't cover. Mention it in the PR / handoff.
- **SQL parameter binding always.** User-reachable values go through `%s` placeholders. Any f-string or `psycopg.sql` composition may interpolate only internal, caller-controlled values (column names, sort keys from an allowlist, `sql.Identifier` for the schema).
- **Only the `claude_dashboard` schema.** Never write to the user's Postgres outside it (`DB_SCHEMA`). Tests create and drop `claude_lens_test_<random>` schemas.
- **Small files with clear responsibilities.** If a file grows past ~400 lines or accretes three distinct concerns, split it.
- **Streaming-snapshot dedup.** Claude Code writes each assistant message 2–3 times while it streams. `(session_id, message_id)` is the dedup key, not `uuid`; the last occurrence wins. See `backend/claude_lens/collector/ingest.py` before touching ingest or any query that joins `messages`.
- **Never print or commit secrets.** `DATABASE_URL`, passwords and tokens live in `.env.local` (git-ignored) and in Coolify's env settings. Refer to them by name.
- **Next.js hydration.** Client components that read `localStorage`, the clock or `window` while rendering must be mounted client-only (`next/dynamic` with `ssr: false`, see `components/shell/client-only.tsx`) or use `useSyncExternalStore`.

## Customizing

Env vars are listed in [.env.example](.env.example) and README.md § Configuration. Pricing lives in `backend/pricing.json` (reloaded when it changes).

## Known limitations

See [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md). Summary: the data is only as fresh as the last sync; skills token counts come from the catalog the collector uploads; rows migrated from SQLite have no `tool_use_id`, so tool errors are only known for calls ingested since.

## Verifying changes

```bash
cd backend && uv run pytest                 # full suite (~10 min over the network; -m "not db" for offline only)
cd frontend && pnpm lint && pnpm build      # also pnpm typecheck
docker compose --env-file .env.local -f docker-compose.yml -f docker-compose.local.yml up --build   # http://localhost:3002
curl https://claude-lens.zeeshanai.cloud/api/health
```

## Git remotes

This repo is a fork. `origin` points to the upstream `nateherkai/token-dashboard`, which is read-only for us (pushing there fails with a 403). Push to the fork instead — the `mzeeshanaltaf` remote (`mzeeshanaltaf/claude-token-dashboard`), which local `main` already tracks:

```bash
git push mzeeshanaltaf main   # or plain `git push`
```

Never push to `origin`.
