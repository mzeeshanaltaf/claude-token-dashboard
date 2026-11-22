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
  `daily`, `by-model`, `tools`, `skills`, `projects`, `projects/{slug}/sessions`,
  `sessions`, `sessions/{id}`, `prompts`, `tips`, `POST tips/dismiss`, `GET/POST plan`,
  `GET/POST settings`, `sync-status`, `health`. Range filters are `since` (inclusive) and
  `until` (exclusive), ISO 8601; no offset means UTC.
- **Pagination:** `sessions` and `prompts` take `page`, `page_size` (≤ 200), `sort`, `order`
  (`asc`/`desc`), `q`, `project`, `model`, and return `{items, total, page, page_size}`.
- **Pricing** is read from `backend/pricing.json` and reloaded when its mtime changes.
- **Timezone:** `/api/daily` buckets days in the `timezone` setting (default `UTC`).

## Database tests

DB tests use `TEST_DATABASE_URL`, falling back to `DATABASE_URL`. Each test session
creates a throwaway schema `claude_lens_test_<random>`, migrates it, truncates it
before every test, and drops it at the end. Without a URL the DB tests are skipped.
