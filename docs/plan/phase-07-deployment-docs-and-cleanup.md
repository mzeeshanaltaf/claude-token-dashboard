# Phase 07: Deployment, docs & cleanup

**Goal:**
1. Containerise the backend and frontend.
2. Deploy to Coolify on the Hostinger VPS behind HTTPS and login.
3. Rewrite the docs for the new architecture.
4. Remove the old local app.

## Entry criteria

- Phases 00–06 are `done`.
- The user has picked the **domain**, e.g. `lens.<your-domain>`. **Ask at the start of the session if it's not in HANDOFF.md.**

## Environment check

```bash
cd backend && uv run pytest
cd frontend && pnpm build
docker --version   # if Docker Desktop is available, for a local compose test
```

## Read first

- *(from phase 06)*:
  - **Check a CSV export through Coolify's proxy.** `/api/export/*.csv` streams (`StreamingResponse` → the Next proxy passes the body through). After deploying, download a sessions export and compare its row count with the Sessions page total.
  - **Copy `pnpm start` with care.** It prints `"next start" does not work with "output: standalone"`; use `node .next/standalone/server.js` in the image.
  - **Ask the user about `claude-lens scan --full`.** Only 0.26% of tool rows have a `tool_use_id` (rows migrated from SQLite have none), so the Tools page's error rates, the session tool timeline's errors and the `Agent` subagent types are mostly blank. A full scan re-reads the 1,205 transcripts still on disk and links them, without touching rows from the 75 missing files. If it hasn't been run yet, ask the user before running it: it writes to the real schema.
  - The real `timezone` setting is still `UTC`. The Activity page labels its buckets with the zone and links to Settings.

- The **`add-app-to-coolify` skill**. Use it for the Coolify part of this phase.
- The user's global CLAUDE.md section on VPS Docker disk cleanup. A new compose app adds build cache, and the weekly prune cron covers it, so there's nothing to change.
- The root `CLAUDE.md` § Git remotes (push to `mzeeshanaltaf`, never `origin`).
- *(from phase 04)* Frontend build facts:
  - `next.config.ts` already sets `output: "standalone"`;
  - `next/font/google` downloads IBM Plex Sans / JetBrains Mono **during `pnpm build`**, so the image build needs outbound network;
  - `public/` is currently empty (the favicon is `app/icon.svg`); create it, or make the `COPY` conditional;
  - `BACKEND_URL` is read at request time (no build arg needed). Run the backend with `TRUST_PROXY=true` and `COOKIE_SECURE=true`.

## Tasks

### Containers
- [x] `backend/Dockerfile`:
  - a `python:3.12-slim` base with `uv sync --frozen --no-dev`;
  - a non-root user;
  - `CMD uvicorn claude_lens.api.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'`;
  - a `HEALTHCHECK` against `/api/health`;
  - `pricing.json` copied into the image.
- [x] `frontend/Dockerfile`: a multi-stage pnpm build that copies `.next/standalone` and `.next/static` and `public`, runs as a non-root user with `node server.js` on port 3000, and needs **no** build-time secrets.
- [x] Root `docker-compose.yml`:
  - `backend` uses `expose: ["8000"]` only, never `ports`;
  - `frontend` exposes 3000 with `BACKEND_URL=http://backend:8000` and `depends_on: backend` (`condition: service_healthy`);
  - environment is passed as `${VAR}` references only.
- [x] A local smoke test: `docker compose up --build` with `.env.local` values, then log in and click through.

### Coolify deploy (follow the `add-app-to-coolify` skill)
- [x] Create a Docker Compose resource from the GitHub fork `mzeeshanaltaf/claude-token-dashboard`, branch `main`. Assign the domain to the **frontend** service only, with Let's Encrypt SSL.
- [x] Set the env vars in Coolify (never in the repo):
  - `DATABASE_URL`: prefer Postgres's internal Docker hostname if it's a Coolify resource on the same network, otherwise the same URL as `.env.local`;
  - `DB_SCHEMA=claude_dashboard`;
  - `ADMIN_USERNAME`, `ADMIN_PASSWORD` (generate a strong password and give it to the user once; don't record it);
  - `COOKIE_SECURE=true`, `TRUST_PROXY=true`.
- [x] Point DNS for the chosen domain at the VPS. Set up auto-deploy on push, as the skill describes. *(Workflow + Coolify auto-deploy off: done. The two repo secrets must be added by the user; setting them via `gh` was blocked.)*
- [x] Optional hardening, if the user agrees:
  - a dedicated Postgres role limited to the `claude_dashboard` schema, for both the collector and the backend;
  - `sslmode=require`, or a UFW allowlist on 5432 for the home IP.
  - *(Done: the `claude_lens` role owns the schema; the collector and production use it. sslmode/UFW skipped by the user.)*

### Docs
- [x] Rewrite `README.md` for Claude Lens:
  - what it is, with new screenshots in `docs/images/`;
  - the architecture diagram;
  - local dev (backend `uv sync` + `uvicorn`; frontend `pnpm dev`);
  - collector setup (`uv sync`, `.env.local`, `claude-lens migrate-sqlite` for existing users, `install_daily_scan.ps1`);
  - the env var table; deployment on Coolify; the CLI reference.
- [x] Rewrite the root `CLAUDE.md`:
  - project overview; the new architecture and layout;
  - conventions: "minimal, justified deps" replaces "stdlib only"; "self-hosted, no third-party telemetry" replaces "fully local";
  - keep the SQL parameter-binding rule (`%s`), the small-files rule and the streaming-snapshot dedup note (now in `collector/ingest.py`);
  - verifying changes (`uv run pytest`, `pnpm lint && pnpm build`);
  - keep the **Git remotes** section exactly as it is;
  - keep the pointer to `docs/plan/` until the redesign is complete.
- [x] Update `docs/KNOWN_LIMITATIONS.md`:
  - skills tokens come from the catalog the collector uploads;
  - `tool_use_id` is null for migrated rows;
  - the data is only as fresh as the last daily sync.
- [x] Update `CONTRIBUTING.md` for the new layout.

### Cleanup (ask the user before deleting)
- [x] Remove `token_dashboard/`, `web/`, `cli.py`, `start_dashboard.bat`, the old `tests/` (already ported to `backend/tests/`) and the root `pricing.json` (moved to `backend/`).
- [x] Rename the GitHub fork to `claude-lens`? That's the user's call. If they do, update the remote URL and the Coolify source. *(User: keep the current name.)*
- [x] **Keep** `~/.claude/token-dashboard.db` on disk. Tell the user it can be archived once they trust the new app.

## Exit criteria

- On the HTTPS domain:
  - opening any page signed out redirects to `/login`;
  - login works; every page loads real data; logout works.
- `curl https://<domain>/api/overview` without a cookie returns 401. Port 8000 isn't reachable from outside.
- The "Synced" badge shows the time of the last scheduled-task run. Trigger the task, reload, and the badge updates.
- `uv run pytest` and `pnpm build` pass in a clean checkout following only the README instructions.
- HANDOFF.md marks every phase `done`, and its final entry records the URL (not credentials).

## Handoff notes to capture

- The production URL, the Coolify resource name and the services.
- Follow-up ideas the user deferred: the Spend control feature set (budget, burn-rate forecast, plan value) and multi-machine filters in the UI.

## Outcome

Deployed at `https://claude-lens.zeeshanai.cloud` (Coolify project "Claude Lens", compose app `claude-lens`, services `backend` + `frontend`). Smoke test 28/28 and headless Chrome 13/13 on production; clean-checkout `uv run pytest` 265 passed and `pnpm build` clean. Old app removed; README, CLAUDE.md, CONTRIBUTING.md and KNOWN_LIMITATIONS.md rewritten; dedicated `claude_lens` Postgres role created.
