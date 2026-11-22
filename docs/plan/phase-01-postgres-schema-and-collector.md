# Phase 01: Postgres schema & batched collector

**Goal:** create the Postgres schema in `claude_dashboard`, and build the local collector (`claude-lens scan`). The collector ingests JSONL transcripts into Postgres **in batches** with the same semantics as today's scanner (incremental offsets, partial-line guard, streaming-snapshot dedup). It also uploads the skill catalog and records a `sync_runs` row.

## Entry criteria

- Phase 00 is `done` in HANDOFF.md.

## Environment check

```bash
cd backend && uv run pytest
uv run python -c "from claude_lens.config import load_settings; import psycopg; s=load_settings(); psycopg.connect(s.database_url).close(); print('pg ok')"
```

## Read first

- `token_dashboard/db.py:11-80` (the current schema) and `:96-140` (the migration notes)
- `token_dashboard/scanner.py:195-310`: `_evict_prior_snapshots`, `scan_file`, `scan_dir`. **These semantics must be preserved.**
- `tests/test_scanner_dedup.py`, `tests/test_scanner_rescan.py`, `tests/test_scanner_walk.py`, `tests/test_scanner_titles.py`

## Tasks

### Schema & migrations
- [ ] `db/pool.py`:
  - a `psycopg_pool.ConnectionPool` factory that sets `search_path` to `DB_SCHEMA` for every connection (via `options=-c search_path=…` or a `configure` callback);
  - a helper for one-off connections, used by the CLI.
- [ ] `db/migrate.py`:
  - `CREATE SCHEMA IF NOT EXISTS <schema>`, then apply `migrations/NNN_*.sql` in order;
  - record each applied migration in `schema_migrations(version, applied_at)`;
  - wrap each migration in a transaction, and take an advisory lock so the API and the collector can't race.
- [ ] `migrations/001_init.sql`:
  - **messages**: the same columns as SQLite, with these changes:
    - `timestamp TIMESTAMPTZ NOT NULL`, `is_sidechain BOOLEAN`, `tool_calls_json JSONB`;
    - new `machine TEXT NOT NULL`;
    - `prompt_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(prompt_text,''))) STORED`, with a GIN index;
    - indexes on session_id, project_slug, timestamp, model, `(session_id, message_id)` and `parent_uuid`.
  - **tool_calls**: `id BIGSERIAL`, the same columns plus `tool_use_id TEXT` and `timestamp TIMESTAMPTZ`; indexes on session_id, tool_name, target and message_uuid.
  - **files**: `(machine, path)` primary key, mtime, bytes_read, `scanned_at TIMESTAMPTZ`.
  - **session_titles**: unchanged.
  - **settings**: `k TEXT PRIMARY KEY, v JSONB`.
  - **dismissed_tips**: `tip_key` PK, `dismissed_at TIMESTAMPTZ`.
  - **skill_catalog**: `(machine, slug)` PK, path, chars, tokens, updated_at.
  - **sync_runs**: id, machine, started_at, finished_at, files, messages, tools, titles, status, error.
  - **users**: id, `username UNIQUE`, password_hash, created_at.
  - **auth_sessions**: token_hash PK, user_id FK, created_at, expires_at.

### Collector
- [ ] `collector/ingest.py`, `scan(projects_root, conn, machine, full=False)`:
  - Walk and skip exactly like `scan_dir`: same mtime/size check, resuming from the stored `bytes_read`, with the offset lookup in `files` keyed by `(machine, path)`.
  - Read new lines with the **partial-line guard** from `scan_file`, and record `end_offset` as the offset after the last full line.
  - For each file (or each chunk of about 5,000 lines in big files), run **one transaction**:
    1. **Dedup within the batch:** keep only the **last** occurrence per `(session_id, message_id)` and per `uuid`.
    2. `COPY` the messages and tool rows into `TEMP` staging tables (`ON COMMIT DROP`).
    3. **Evict older snapshots** already in the DB: `DELETE FROM messages m USING stage s WHERE m.session_id=s.session_id AND m.message_id=s.message_id AND m.uuid<>s.uuid` (and delete their tool_calls first).
    4. `INSERT INTO messages … SELECT … FROM stage ON CONFLICT (uuid) DO UPDATE SET …` (every column).
    5. `DELETE FROM tool_calls WHERE message_uuid IN (stage uuids)`, then insert the staged tool rows.
    6. Upsert the titles; the last one in file order wins.
    7. Upsert the `files` row with the new offset **in the same transaction**.
  - `full=True` ignores the stored offsets and re-reads everything, which backfills `tool_use_id`. The upserts make it idempotent.
- [ ] `collector/skills_catalog.py`: add `upload_catalog(conn, machine)`, which replaces this machine's rows in `skill_catalog`.
- [ ] CLI `claude-lens scan [--full] [--projects-dir]`:
  1. run migrations;
  2. insert a `sync_runs` row with status `running`;
  3. scan;
  4. upload the catalog;
  5. finish the run row with `ok` or `error` plus the message;
  6. print the totals.
  Retry network errors (`psycopg.OperationalError`) up to 3 times, 60 seconds apart.
- [ ] CLI `claude-lens status`: print the last 5 `sync_runs` and the row counts.

### Tests
- [ ] A `backend/tests/conftest.py` fixture:
  - creates a throwaway schema `claude_lens_test_<random>` on `TEST_DATABASE_URL`, falling back to `DATABASE_URL` from `.env.local`;
  - runs migrations into it, yields a connection, then runs `DROP SCHEMA … CASCADE`;
  - skips DB tests when no URL is available.
- [ ] Port the dedup, rescan, walk and titles tests to the Postgres collector. They must assert **the same totals** as the old tests on `tests/fixtures/sample_session.jsonl`.

## Exit criteria

- `uv run pytest` is green, DB tests included.
- Scan a copy of one real project folder (`--projects-dir`) **into a test schema**, twice. The second run must process 0 files.
- Append a duplicate streaming snapshot line to a temp JSONL and re-scan: exactly one row for that `message_id`.
- **Don't** run a full scan into the real `claude_dashboard` schema yet. Phase 02 seeds it from SQLite first, so offsets line up.

## Handoff notes to capture

- How long a single-project scan took over the network, and the batch size you chose.
- Any difference from SQLite semantics you had to accept.
