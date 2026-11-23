# Claude Lens

**Usage, cost & workflow analytics for Claude Code.** A collector on your PC reads the JSONL transcripts Claude Code writes to `~/.claude/projects/` and pushes them to your own Postgres. A login-protected dashboard on your own server turns them into per-prompt cost, daily and per-project spend, cache analytics, activity heatmaps, a deep per-session view, tool and file insights, search, CSV export and a rule-based tips engine.

Self-hosted: your transcripts only ever go to your own database and your own server. No third-party telemetry.

![Overview: est. cost, sessions, prompts and cache hit rate, token composition and daily activity](docs/images/lens_overview.png)

## What's in it

| Page | What it shows |
|---|---|
| **Overview** | Estimated cost, sessions, prompts and cache hit rate with sparklines; token composition (input / output / cache read / cache write, as tokens or cost); daily tokens or cost per model; model mix; top projects, top tools and recent sessions. |
| **Activity** | A 12-month calendar heatmap (cost or tokens per day), an hour × weekday grid, streaks, the busiest day and peak hour. |
| **Prompts** | Every prompt with the full cost of the turn that answered it; search, sort by tokens / cost / recency, a detail sheet with the full text. |
| **Sessions** | Server-paginated, sortable and filterable by project and model. Each session opens a deep view: context growth per turn (with compactions), cost per turn, a tool timeline, subagents, files touched and the turn-by-turn table. |
| **Projects** | Per-project cost with a daily sparkline; each project has its own overview. |
| **Tools** | Calls, result tokens and error rates by tool; the most-read files, shell commands and WebFetch domains. |
| **Skills** | Which skills you invoke and what loading them costs. |
| **Tips** | Rule-based suggestions (repeated reads, oversized tool results, low cache hit rate…), dismissible with undo. |
| **Settings** | Your plan (API / Pro / Max / Max 20x), timezone, sync status per machine, change password. |

Everywhere: a global date range (7d / 30d / 90d / All / custom, kept in the URL), **Cmd/Ctrl+K** search across prompts, sessions and projects, **Export CSV** on Sessions / Prompts / Projects, dark and light themes, and **Cmd/Ctrl+B** to blur prompt text and project names when you share your screen.

| | |
|---|---|
| ![Activity heatmaps](docs/images/lens_activity.png) | ![Tools page](docs/images/lens_tools.png) |
| ![Sessions list (privacy blur on)](docs/images/lens_sessions.png) | ![Projects list (privacy blur on)](docs/images/lens_projects.png) |

## Architecture

```
Windows PC                                     VPS (Coolify, docker compose)
┌───────────────────────────┐  psycopg/5432   ┌──────────────────┐   ┌────────────────────────┐
│ collector (daily task)    │ ──────────────▶ │ Postgres         │◀──│ backend  FastAPI :8000 │ internal only
│ ~/.claude/projects/*.jsonl│  batched COPY   │ schema           │   └───────────▲────────────┘
│ ~/.claude/skills (catalog)│                 │ claude_dashboard │               │ /api/* proxy
└───────────────────────────┘                 └──────────────────┘   ┌───────────┴────────────┐
                                               browser ─HTTPS──▶     │ frontend Next.js :3000 │ public domain
                                                                     └────────────────────────┘
```

- **Collector** (`backend/claude_lens/collector`, `claude-lens scan`): incremental (per-file mtime + byte offset), batched `COPY` into Postgres, de-duplicates streaming snapshots. Runs once a day from a Windows Scheduled Task, or by hand.
- **Backend** (`backend/`): FastAPI + psycopg 3, raw SQL. Single admin login with server-side sessions. Applies its migrations on startup.
- **Frontend** (`frontend/`): Next.js 16 + shadcn/ui + TanStack Query/Table + Recharts. A route handler proxies `/api/*` to the backend at request time, so the browser only ever talks to one origin and the backend is never public.

## Prerequisites

- **Claude Code**, with at least one session run.
- **Postgres** (developed and run on 17) reachable from your PC. All tables live in one schema (`claude_dashboard` by default).
- **Python 3.12** and **[uv](https://docs.astral.sh/uv/)** for the backend and collector.
- **Node 22+** and **pnpm 10** for the frontend.
- **Docker** only for the container smoke test and deployment.

## Local development

```bash
git clone https://github.com/mzeeshanaltaf/claude-token-dashboard.git
cd claude-token-dashboard
cp .env.example .env.local        # then fill in DATABASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD

# backend (from backend/)
cd backend
uv sync
uv run pytest                     # full suite; DB tests use a throwaway schema (-m "not db" to skip them)
COOKIE_SECURE=false TRUST_PROXY=true uv run uvicorn claude_lens.api.main:app --port 8000

# frontend (from frontend/, in a second terminal)
cd frontend
pnpm install
pnpm dev                          # http://localhost:3000
pnpm lint && pnpm build
```

The backend reads `.env.local` from the repo root. On first start it creates the admin user from `ADMIN_USERNAME` / `ADMIN_PASSWORD` (only while the `users` table is empty). The frontend needs no env file: `BACKEND_URL` defaults to `http://localhost:8000`.

To test the production containers locally:

```bash
docker compose --env-file .env.local -f docker-compose.yml -f docker-compose.local.yml up --build
# http://localhost:3002
```

## Collector setup (on the PC with the transcripts)

```powershell
cd backend
uv sync
uv run claude-lens scan            # first run reads every transcript; later runs only new lines
uv run claude-lens status          # last sync runs and row counts
```

**Coming from the old Token Dashboard?** Copy its SQLite history first, because Claude Code deletes old transcripts and a rescan would lose them:

```powershell
uv run claude-lens migrate-sqlite  # ~/.claude/token-dashboard.db -> Postgres, with a parity check
uv run claude-lens scan --full     # then link tool calls to their results for transcripts still on disk
```

**Daily sync (Windows).** Registers the `Claude Lens - Daily Sync` scheduled task (daily at 13:00, or as soon as the PC is back on):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_daily_scan.ps1             # daily at 13:00
powershell -ExecutionPolicy Bypass -File scripts\install_daily_scan.ps1 -At 09:30   # custom time
powershell -ExecutionPolicy Bypass -File scripts\install_daily_scan.ps1 -Uninstall
Start-ScheduledTask -TaskName 'Claude Lens - Daily Sync'                            # run it now
```

It runs `backend\.venv\Scripts\pythonw.exe -m claude_lens.cli scan` from the repo root (so `.env.local` is found) and logs to `~/.claude/claude-lens-sync.log`. The dashboard's "Synced" badge shows when the last run finished.

## Configuration

Set these in `.env.local` locally and in Coolify's environment settings in production. Never commit real values.

| Variable | Used by | Default | Purpose |
|---|---|---|---|
| `DATABASE_URL` | backend, collector | (required) | `postgresql://user:password@host:5432/dbname` |
| `DB_SCHEMA` | backend, collector | `claude_dashboard` | The schema every table lives in |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | backend | (required on first boot) | Creates the single admin while `users` is empty; ignored afterwards. Password ≥ 8 characters |
| `COOKIE_SECURE` | backend | `true` | Set `false` only for plain `http://localhost` |
| `TRUST_PROXY` | backend | `false` (`true` in compose) | Read the client IP from the last `X-Forwarded-For` hop (for the login lockout) |
| `BACKEND_URL` | frontend | `http://localhost:8000` | Where the Next.js proxy sends `/api/*`; read per request, not at build |
| `CLAUDE_PROJECTS_DIR` | collector | `~/.claude/projects` | Transcript folder |
| `CLAUDE_LENS_MACHINE` | collector | hostname | Machine label stored with synced rows |
| `CLAUDE_LENS_SYNC_LOG` | collector | `~/.claude/claude-lens-sync.log` | Rotating sync log |
| `TEST_DATABASE_URL` | tests | `DATABASE_URL` | Postgres for the DB tests (throwaway `claude_lens_test_*` schemas, so this user needs `CREATE` on the database) |

**Recommended: a dedicated database role.** The app only needs to own its schema. Create a login role (no superuser, no `CREATEDB`), `GRANT CONNECT` on the database, and make it the owner of the `claude_dashboard` schema and its tables (`ALTER SCHEMA … OWNER TO`, `ALTER TABLE … OWNER TO`). Use it in `DATABASE_URL` for both the collector and the backend; migrations work without database-level `CREATE` once the schema exists. Keep a more privileged URL in `TEST_DATABASE_URL` for the test suite.

Pricing lives in [`backend/pricing.json`](backend/pricing.json) (per-model rates and plans), sourced from the [Anthropic pricing page](https://platform.claude.com/docs/en/about-claude/pricing). The API reloads it when the file changes.

## Deployment (Coolify)

Production runs as a Docker Compose application on Coolify ([`docker-compose.yml`](docker-compose.yml)): `backend` (FastAPI, `expose` only, never published) and `frontend` (Next.js standalone, the only service with a domain).

1. In Coolify, create a **Docker Compose** application from this repo, branch `main`, compose file `/docker-compose.yml`.
2. Give the **frontend** service the domain, with port 3000 (`https://your.domain:3000`; the port is the container port Traefik routes to). Coolify issues the Let's Encrypt certificate once DNS points at the server.
3. Set the environment: `DATABASE_URL` (on the same server, use the Docker bridge gateway, e.g. `10.0.0.1`, not `localhost`), `DB_SCHEMA`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `COOKIE_SECURE=true`, `TRUST_PROXY=true`. None are needed at build time.
4. Point an `A` record for the domain at the server and deploy.
5. Auto-deploy: [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) calls Coolify's deploy API on every push to `main` (with retries). It needs the repo secrets `COOLIFY_API_TOKEN` (deploy permission) and `COOLIFY_APP_UUID`; Coolify's own "Auto Deploy" stays off.

The backend container applies database migrations when it starts. Both images run as non-root users and have health checks; the frontend starts once the backend is healthy.

## CLI reference

Run from `backend/` with `uv run`, or as `backend\.venv\Scripts\python -m claude_lens.cli`.

```bash
claude-lens scan                       # incremental sync of ~/.claude/projects to Postgres
claude-lens scan --full                # re-read every transcript (idempotent)
claude-lens scan --projects-dir PATH   # another transcript folder
claude-lens status                     # recent sync runs and row counts
claude-lens migrate-sqlite             # one-time copy from the old Token Dashboard SQLite file
claude-lens migrate-sqlite --check-only   # re-run only the parity check
claude-lens set-password USER          # set or reset a password (creates the user; signs out its sessions)
```

## Accuracy note

Claude Code writes each assistant response 2–3 times while it streams (the same API message, snapshotted as the output grows). Claude Lens keeps only the last snapshot per `(session_id, message_id)`, so totals match what the API billed. A tool that sums every JSONL row will show higher numbers. Costs are API-equivalent estimates from `pricing.json`; see [Known limitations](docs/KNOWN_LIMITATIONS.md).

## Security & privacy

- Single admin account; passwords hashed with argon2. Sessions are server-side (only a SHA-256 of the token is stored), in an HttpOnly, Secure, SameSite=Lax cookie with a 7-day sliding expiry. Five failed logins lock that IP + username out for 15 minutes.
- Every non-GET API request must be JSON and same-origin (CSRF guard).
- The backend has no public port; only the Next.js frontend is exposed, over HTTPS.
- No analytics or third-party calls. Fonts are bundled at build time.

## Further reading

- [`backend/README.md`](backend/README.md): collector internals, the API and every endpoint.
- [`frontend/README.md`](frontend/README.md): the proxy, conventions and page patterns.
- [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md): rough edges.
- [`CLAUDE.md`](CLAUDE.md): conventions and architecture for Claude Code sessions.
- [`docs/plan/`](docs/plan/README.md): how the redesign was planned and built, phase by phase.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): how to develop and test.

## Credits

Claude Lens started as a fork of [nateherkai/token-dashboard](https://github.com/nateherkai/token-dashboard), itself inspired by [phuryn/claude-usage](https://github.com/phuryn/claude-usage) (see [`docs/inspiration.md`](docs/inspiration.md)). It has since been rebuilt with a Next.js frontend, a FastAPI backend and Postgres; the transcript parsing, streaming-snapshot dedup, pricing and tips rules carry over from the original.

## License

[MIT](LICENSE).
