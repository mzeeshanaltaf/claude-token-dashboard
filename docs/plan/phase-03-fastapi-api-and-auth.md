# Phase 03: FastAPI API & auth

**Goal:** build the FastAPI backend that serves every existing dashboard endpoint from Postgres, with the same JSON shapes, plus server-side pagination and single-admin login. The new-feature endpoints (activity, session insights, tools insights, search, export) belong to **phase 06**, so leave them out here.

## Entry criteria

- Phase 02 is `done`: the real schema holds the migrated data.

## Environment check

```bash
cd backend && uv run pytest
uv run claude-lens status
```

## Read first

- `token_dashboard/server.py`: every route, `_cost_by_key`, `_cost_breakdown_by_key`, the overview cost rollup (`:152-174`) and `_make_pricing_loader`
- `token_dashboard/db.py:219-504`: every query to port
- `token_dashboard/tips.py`: the rules to port
- `tests/test_queries.py`, `tests/test_server.py`, `tests/test_tips.py`, `tests/test_end_to_end_totals.py`

## Tasks

### Queries (`db/queries/*.py`)
- [x] Port every `db.py` query function. Each takes a connection or pool, keeps its current parameters, and returns dicts. Dialect changes:
  - `?` becomes `%s`;
  - `INSERT OR REPLACE` becomes `ON CONFLICT … DO UPDATE`;
  - `SUM(CASE WHEN …)` becomes `COUNT(*) FILTER (WHERE …)`;
  - `substr(timestamp,1,10)` becomes `(timestamp AT TIME ZONE %(tz)s)::date`. The timezone comes from `settings.timezone` and defaults to `UTC`.
- [x] Replace the N+1 cwd lookups in `project_summary`, `recent_sessions` and `project_sessions` with one query: `SELECT project_slug, array_agg(DISTINCT cwd) … GROUP BY project_slug`. Then call `core.names.best_project_name`.
- [x] `sessions` and `prompts` get server-side `page`, `page_size` (max 200), `sort` (from a whitelist of columns), `q` (ILIKE on the title or prompt), `project` and `model`. They return `{items, total, page, page_size}`.
- [x] **Fix:** the prompt cost is the full assistant-turn cost (all 5 token types), not cache reads only.
- [x] `core/tips.py`: port the 4 rule sets to Postgres. `_is_dismissed` uses `dismissed_at > now() - interval '14 days'`.
- [x] Plan get/set via the `settings` table. Also add `timezone` get/set.

### API (`api/`)
- [x] `api/main.py`:
  - on startup, create the pool, run `migrate`, and bootstrap the admin if `users` is empty (from `ADMIN_USERNAME`/`ADMIN_PASSWORD`; refuse to start if both are missing and there are no users);
  - mount routers under `/api`; add `GET /api/health`, which needs no auth.
- [x] Routers keep their current JSON shapes. Reuse the `_cost_by_key` and `_cost_breakdown_by_key` logic in a `core/costs.py`. The routes:
  - `overview`, `daily`, `by-model`, `tools`, `skills`;
  - `projects`, `projects/{slug}/sessions`;
  - `sessions`, `sessions/{id}`;
  - `prompts`;
  - `tips`, `POST tips/dismiss`;
  - `GET/POST plan`, `GET/POST settings`;
  - `sync-status`: the last run per machine plus its status.
- [x] `skills`: `tokens_per_call` comes from the `skill_catalog` table, not the filesystem.
- [x] Pricing comes from `backend/pricing.json`, reloaded when its mtime changes (port `_make_pricing_loader`).
- [x] Pydantic response models for the main endpoints, so OpenAPI documents them; phase 04 generates TS types from them.

### Auth (`api/auth.py`, `api/deps.py`)
- [x] `POST /api/auth/login {username,password}`:
  - argon2 verify via `pwdlib`;
  - on success, create 32 random bytes as the token, store `sha256(token)` in `auth_sessions` with a 7-day expiry, and set the cookie `cl_session` (HttpOnly, SameSite=Lax, `Secure` when `COOKIE_SECURE=true`, Path=/).
- [x] `POST /api/auth/logout`, `GET /api/auth/me`, and `POST /api/auth/password {current,new}`. A password change revokes every other session.
- [x] `current_user` dependency on every router except `health` and `auth/login`. It slides the expiry forward when less than half the lifetime is left.
- [x] Lockout: 5 failures per (IP, username) within 15 minutes returns 429 (in-memory store; there's only one container). Use `X-Forwarded-For` only when it comes from a trusted proxy (`TRUST_PROXY=true`).
- [x] CSRF: for non-GET requests, require `Content-Type: application/json`, and an `Origin` header (if present) whose host matches `Host`/`X-Forwarded-Host`.
- [x] CLI `claude-lens set-password <username>`, which prompts via `getpass`.

### Tests
- [x] Port `test_queries`, `test_server` (now FastAPI `TestClient`), `test_tips` and `test_end_to_end_totals` onto the throwaway-schema fixture.
- [x] Auth tests:
  - 401 without a cookie; login and access works;
  - a wrong password returns 401; the 6th attempt returns 429;
  - logout revokes the session; a password change revokes the other sessions.

## Exit criteria

- `uv run pytest` is green.
- With `uv run uvicorn claude_lens.api.main:app --port 8000` running against the real schema:
  - `curl -i localhost:8000/api/overview` returns **401**;
  - log in with `curl -c jar`, then `curl -b jar /api/overview` returns 200;
  - **its totals match the old app's** `/api/overview` for `range=all` (run the old app on 8080 side by side). Record both numbers.
- `/docs` (OpenAPI) lists every endpoint.

## Handoff notes to capture

- The final endpoint list and any shape changes (there should be none except pagination envelopes, which phase 05 must know about).
- How the admin was seeded locally (env var names only).

## Outcome

Done 2026-11-22.
- `uv run pytest`: **235 passed**.
- Live against the real schema: `/api/overview` returns 401 without a cookie and 200 after `curl -c jar` login. Its totals match the old app's `range=all` on all 15 fields (cost **$6,438.7082** on both). `/docs` lists 20 paths.
- Shape changes beyond the pagination envelopes are listed in HANDOFF.md § Decisions. They are additive or type-only: parsed `tool_calls_json`, boolean `is_sidechain`, extra cost and token fields, and `last_active`.
- The admin was seeded from `ADMIN_USERNAME`/`ADMIN_PASSWORD` set as process env vars.
