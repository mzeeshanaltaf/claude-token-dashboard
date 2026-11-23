# Claude Lens backend

FastAPI API + local collector for Claude Lens. Managed with [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync                       # create .venv and install deps
uv run pytest                 # full suite (DB tests need Postgres, see below)
uv run pytest -m "not db"     # offline tests only
uv run claude-lens --help
```

Configuration is read from environment variables, falling back to `.env.local` / `.env`
at the repo root (see `../.env.example`).

## Collector

```bash
uv run claude-lens scan                    # incremental: only new lines since the last run
uv run claude-lens scan --full             # re-read every transcript (idempotent)
uv run claude-lens scan --projects-dir D   # scan another folder (default ~/.claude/projects)
uv run claude-lens status                  # last 5 sync runs + row counts
```

`scan` applies pending migrations, records a `sync_runs` row, ingests transcripts in
batched transactions (about 5,000 lines each, `--batch-lines`), uploads this machine's
skill catalog, and retries database errors 3 times, 60 seconds apart. Rows are tagged
with `CLAUDE_LENS_MACHINE` (default: the hostname). Everything lives in the `DB_SCHEMA`
schema (default `claude_dashboard`).

`scan` also logs to `~/.claude/claude-lens-sync.log` (`CLAUDE_LENS_SYNC_LOG`; rotated at
1 MB, 1 backup), which is the only output when it runs under `pythonw`.

### Daily sync (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_daily_scan.ps1     # daily at 13:00 (-At HH:MM, -Uninstall)
Start-ScheduledTask -TaskName 'Claude Lens - Daily Sync'                    # run it now
```

The task runs `backend\.venv\Scripts\pythonw.exe -m claude_lens.cli scan` from the repo
root, so `uv sync` must have been run here first.

## One-time SQLite migration

```bash
uv run claude-lens migrate-sqlite                       # ~/.claude/token-dashboard.db -> DB_SCHEMA
uv run claude-lens migrate-sqlite --check-only          # re-run only the parity check
uv run claude-lens migrate-sqlite --force               # truncate the migrated tables, re-import
```

The old Token Dashboard SQLite file is opened read-only (`mode=ro`) and read in one
transaction. Every table is streamed through `COPY` (20,000-row chunks, `--chunk`), one
transaction per table, followed by `ANALYZE`. `files` offsets are copied verbatim, so the
next `scan` only reads what changed since the old app's last scan. The command refuses to
run when the schema already has history, unless `--force`. It ends with a parity table:
row counts, distinct sessions, the five token sums overall and per model, tool result
tokens and errors, exact `files` offsets, and the plan. It exits 1 on any mismatch.

## API

```bash
uv run uvicorn claude_lens.api.main:app --port 8000   # OpenAPI docs at /docs
uv run claude-lens set-password admin                 # set/reset a password (creates the user if missing)
```

On startup the API opens a connection pool, applies pending migrations, and — if `users`
is empty — creates the admin from `ADMIN_USERNAME` / `ADMIN_PASSWORD` (it refuses to start
when both the users table and those env vars are empty; once a user exists they are
ignored). For local `http://` use, set `COOKIE_SECURE=false`.

- **Auth:** `POST /api/auth/login {username,password}` sets the `cl_session` cookie
  (HttpOnly, SameSite=Lax, `Secure` unless `COOKIE_SECURE=false`, 7-day sliding expiry;
  only its sha256 is stored). `POST /api/auth/logout`, `GET /api/auth/me`,
  `POST /api/auth/password {current,new}` (revokes every other session). 5 failed logins
  per (IP, username) within 15 minutes → 429. With `TRUST_PROXY=true` the IP is the last
  `X-Forwarded-For` hop.
- **CSRF:** every non-GET request must be `Content-Type: application/json`, and an `Origin`
  header, if sent, must match `Host` or `X-Forwarded-Host`.
- **Endpoints** (all need a login except `health` and `auth/login`/`logout`): `overview`,
  `daily`, `by-model`, `tools`, `skills`, `projects`, `projects/daily`,
  `projects/{slug}/sessions`, `sessions`, `sessions/{id}`, `prompts`, `tips`,
  `POST tips/dismiss`, `POST tips/restore`, `GET/POST plan`, `GET/POST settings`,
  `sync-status`, `health`, and (phase 06) `activity/{calendar,hourly,summary}`,
  `sessions/{id}/insights`, `tools/insights`, `search`, `export/{sessions,prompts,projects}.csv`. Range filters are `since` (inclusive) and `until` (exclusive),
  ISO 8601; no offset means UTC. `overview`, `daily` and `by-model` also take `project`
  (a slug) to scope them to one project.
- **Daily rows** carry `sessions`, `turns`, the token sums, and the day's `cost_usd` plus
  `cost_by_model` (unpriced models are left out). `projects/daily` is
  `[{project_slug, day, cost_usd}]` for the projects list's sparklines.
- **Pagination:** `sessions` and `prompts` take `page`, `page_size` (≤ 200), `sort`, `order`
  (`asc`/`desc`), `q`, `project`, `model`, and return `{items, total, page, page_size}`.
- **Pricing** is read from `backend/pricing.json` and reloaded when its mtime changes.
- **Timezone:** `/api/daily` and `/api/activity/*` bucket days and hours in the
  `timezone` setting (default `UTC`).
- **Activity:** `activity/calendar?metric=cost|tokens&days=365` (one row per active local
  date in the window ending today: `value`, `cost_usd`, `tokens`, `sessions`, `turns`),
  `activity/hourly` (all 168 ISO-weekday × local-hour cells) and `activity/summary`
  (active days, current/longest streak, busiest day, per-active-day averages, top project,
  peak hour). "Tokens" there means input + output + cache writes.
- **Session insights:** `sessions/{id}/insights` → context growth per assistant turn, the
  tool timeline (with `is_error` from the matching `_tool_result`, null without a
  `tool_use_id`), subagents by `agent_id` plus the Agent/Task invocations, files touched
  (Read/Edit/Write), branches, models and duration.
- **Tools insights:** `tools/insights` → per-tool calls, linked calls, errors, error rate and
  result tokens (linked calls only, with a `linked_note`), plus the top 20 files, shell
  commands (Bash + PowerShell) and WebFetch domains.
- **Search:** `search?q=&limit=8` → `prompts` (full text on `prompt_tsv`, ranked, with a
  `ts_headline` snippet whose matches are wrapped in U+E000…U+E001), `sessions` (title
  ILIKE) and `projects` (name or slug).
- **CSV export:** `export/sessions.csv`, `export/prompts.csv` (the list endpoints' filters
  and sort, no page cap) and `export/projects.csv` (range + optional `q`), streamed with
  `Content-Disposition: attachment; filename="claude-lens-<table>-<date>.csv"`. UTF-8
  with a BOM; formula-like text gets a leading `'` and over-long text is cut to fit
  Excel's cell limit (see `core/csv_export.py`).

## Database tests

DB tests use `TEST_DATABASE_URL`, falling back to `DATABASE_URL`. That user must be allowed
to create schemas, so with the dedicated `claude_lens` role in `DATABASE_URL` (production
setup) point `TEST_DATABASE_URL` at a more privileged user. Each test session
creates a throwaway schema `claude_lens_test_<random>`, migrates it, truncates it
before every test, and drops it at the end. Without a URL the DB tests are skipped.
