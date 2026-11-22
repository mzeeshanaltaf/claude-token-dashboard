# Phase 02: SQLite migration & daily sync task

**Goal:**
1. Copy the complete history from `~/.claude/token-dashboard.db` into the real `claude_dashboard` schema, and prove parity. This is required because 75 scanned transcripts no longer exist on disk.
2. Switch the daily Windows Scheduled Task to run the Postgres collector.

## Entry criteria

- Phase 01 is `done`, and `claude-lens scan` is proven on a test schema.

## Environment check

```bash
cd backend && uv run pytest
uv run claude-lens status          # real schema: expect empty or no runs yet
python -c "import sqlite3,os;c=sqlite3.connect('file:'+os.path.expanduser('~/.claude/token-dashboard.db')+'?mode=ro',uri=True);print(c.execute('select count(*) from messages').fetchone())"
```

## Read first

- `token_dashboard/db.py:11-80`: the SQLite schema (source)
- `backend/claude_lens/db/migrations/001_init.sql`: the target schema
- `scripts/daily_scan.py` and `scripts/install_daily_scan.ps1`: the current task

## Tasks

### One-time migration
- [ ] `collector/migrate_sqlite.py`, `claude-lens migrate-sqlite --sqlite <path> [--machine <name>] [--force]`:
  - Open SQLite **read-only** (`mode=ro` URI).
  - Refuse to run if `messages` in Postgres is non-empty, unless `--force` is passed (which truncates the target tables first).
  - Stream each table in chunks (about 20k rows) through `COPY`:
    - messages: add `machine`; parse ISO text into `timestamptz`; convert `is_sidechain` from int to bool; convert `tool_calls_json` from text to jsonb; leave `prompt_tsv` alone, since it's generated;
    - tool_calls: drop the SQLite `id` and let BIGSERIAL assign one; `tool_use_id` stays null;
    - session_titles, dismissed_tips (epoch to timestamptz);
    - plan becomes `settings` (`k='plan'`, `v` as a JSON string);
    - files: add `machine`, keep `path`, `mtime` and `bytes_read` exactly, so later scans are incremental.
  - Commit per table, and show progress.
  - Run `ANALYZE` at the end.
- [ ] Built-in **parity check**, printed as a table comparing SQLite and Postgres:
  - row counts for messages, tool_calls, session_titles and files;
  - `COUNT(DISTINCT session_id)`;
  - the sums of all 5 token columns;
  - per-model sums.
  Exit non-zero on any mismatch.
- [ ] Run it against the **real** schema. Expected values: 235,402 messages, 159,328 tool_calls, 1,085 sessions (the scanner may have added more since 2026-11-20; record the actual numbers).
- [ ] Right after the migration, run `claude-lens scan` against the real schema. It should only pick up transcripts newer than the SQLite DB's last scan. Record the files and messages it ingested.

### Daily sync task
- [ ] Rewrite `scripts/install_daily_scan.ps1`:
  - task name **`Claude Lens - Daily Sync`**; unregister the old `Claude Token Dashboard - Daily Scan` task if it exists;
  - action: `<repo>\backend\.venv\Scripts\pythonw.exe -m claude_lens.cli scan`, with working directory `<repo>` so `.env.local` is found. Fail clearly if `backend\.venv` is missing ("run `uv sync` in backend first");
  - keep the `-At` (default 13:00) and `-Uninstall` parameters and the StartWhenAvailable, battery, 1-hour-limit and IgnoreNew settings.
- [ ] Logging in the CLI `scan` path (or a thin `claude_lens/collector/daily.py`): a rotating file log at `~/.claude/claude-lens-sync.log` (1 MB, 1 backup); add the stream handler only when `sys.stderr` isn't None, as for pythonw.
- [ ] Delete `scripts/daily_scan.py`, whose logic now lives in the CLI. **Ask the user first:** the old task points to it, but the old task is removed in this same step.
- [ ] Install the task, then trigger it with `Start-ScheduledTask -TaskName 'Claude Lens - Daily Sync'`.

## Exit criteria

- The parity check passes, and the actual numbers are recorded in HANDOFF.md.
- `claude-lens status` shows a successful `sync_runs` row created **by the scheduled task**.
- `Get-ScheduledTask` shows only the new task. The log file has a "scanned N files…" line.
- The old SQLite DB is untouched.

## Handoff notes to capture

- Migration duration and the final row counts.
- The machine name recorded (this is the `machine` column value).
