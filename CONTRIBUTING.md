# Contributing

Thanks for considering a contribution! Claude Lens is a FastAPI backend + local collector (`backend/`) and a Next.js frontend (`frontend/`). See the [README](README.md) for setup and [`CLAUDE.md`](CLAUDE.md) for the architecture.

## Running the checks

```bash
cd backend
uv sync
uv run pytest -m "not db"     # offline tests, a few seconds
uv run pytest                 # full suite; DB tests need TEST_DATABASE_URL or DATABASE_URL

cd frontend
pnpm install
pnpm typecheck && pnpm lint && pnpm build
```

DB tests create a throwaway `claude_lens_test_<random>` schema, truncate it before each test and drop it at the end. They never touch `claude_dashboard`. Without a database URL they are skipped.

If you're fixing a bug, add a failing test first. If you're adding a feature, add a test that exercises the happy path.

## Running it locally

```bash
cd backend && COOKIE_SECURE=false TRUST_PROXY=true uv run uvicorn claude_lens.api.main:app --port 8000
cd frontend && pnpm dev       # http://localhost:3000
```

After changing the API, regenerate the frontend's types with `pnpm gen:api` (needs the backend on :8000).

## Where things go

- **A new API endpoint:** SQL in `backend/claude_lens/db/queries/<area>.py`, pure shaping in `core/`, the route in `api/routers/<area>.py`, its response model in `api/schemas*.py`, tests in `backend/tests/`. Mount new routers in `api/main.py` behind the login dependency.
- **A schema change:** a new `backend/claude_lens/db/migrations/NNN_<name>.sql`. Migrations run on API startup and before every `claude-lens scan`. Never edit an applied migration.
- **Collector changes:** `collector/parse.py` (one JSONL record → rows) and `collector/ingest.py` (batching, staging, dedup). Keep `(session_id, message_id)` as the dedup key.
- **A new page:** `frontend/components/<page>/<page>-page.tsx`, with `app/(dashboard)/<route>/page.tsx` only setting metadata. Reuse `DataTable`, `SectionCard`, `KpiCard`, `FilterBar` and the chart components; see `frontend/README.md` § Page patterns.

## Code style

- **Minimal, justified deps.** Explain in the PR why a new Python or npm package is worth it.
- **SQL: parameter binding always.** User-reachable values go through `%s` placeholders; only internal, allowlisted values (column names, sort keys, `sql.Identifier`) may be composed into SQL.
- **Small focused files.** If a file creeps past ~400 lines or takes on distinct concerns, split it.
- **Frontend:** use the design tokens and shadcn components; mark sensitive text with `blur-sensitive`; anything that reads browser-only state while rendering must be client-only (see `frontend/README.md` § Conventions).
- **Docstrings explain *why*, not *what*.**

## Opening a pull request

1. Fork the repo.
2. Create a branch: `git checkout -b feat/<short-description>` or `fix/<short-description>`.
3. Make the change. Add or update tests.
4. Run the checks above; they must be green.
5. Commit with a conventional-commit message: `feat: add X`, `fix: handle Y`, `docs: update Z`.
6. Push and open a PR against `main`. Describe the user-visible change.

## Ideas that would help

- Broadening the skills catalog to project-local `.claude/skills/` directories.
- Multi-machine filters in the UI (rows already carry a `machine` label).
- Budgets and a burn-rate forecast.
- A GitHub Actions workflow that runs the offline tests and the frontend build on every PR.

## What we're not looking for

- Telemetry, analytics, or any outbound call with user data. Claude Lens is self-hosted and stays that way.

## License

By contributing, you agree your contribution is licensed under the [MIT License](LICENSE).
