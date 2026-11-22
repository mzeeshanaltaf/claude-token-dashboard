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

## Database tests

DB tests use `TEST_DATABASE_URL`, falling back to `DATABASE_URL`. Each test session
creates a throwaway schema `claude_lens_test_<random>`, migrates it, truncates it
before every test, and drops it at the end. Without a URL the DB tests are skipped.
