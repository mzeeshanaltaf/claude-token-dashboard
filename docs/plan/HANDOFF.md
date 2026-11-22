# Claude Lens: session handoff

The living state of the redesign. Read it at the **start** of every session, after `README.md`, and update it at the **end** of every session. The protocol is in [README.md § Session handoff protocol](README.md#session-handoff-protocol).

## Phase status

| # | Phase | Status | Started | Finished | Notes |
|---|---|---|---|---|---|
| 00 | Repo hygiene & backend scaffold | done | 2026-11-22 | 2026-11-22 | 71 backend tests pass |
| 01 | Postgres schema & batched collector | done | 2026-11-22 | 2026-11-22 | 129 backend tests pass (43 on Postgres); SQLite parity exact on a real project |
| 02 | SQLite migration & daily sync task | not-started | | | |
| 03 | FastAPI API & auth | not-started | | | |
| 04 | Frontend shell & login | not-started | | | |
| 05 | Frontend core pages | not-started | | | |
| 06 | New features | not-started | | | |
| 07 | Deployment, docs & cleanup | not-started | | | |

Status values: `not-started` · `in-progress` · `blocked` · `done`

## Baton (replace this section at the end of every session)

- **Current phase:** 01 is done. Next is 02.
- **Last commit:** `3530e74 feat(collector): postgres schema, migrations and batched ingest` (phase 01), pushed to `mzeeshanaltaf/main`, plus a docs follow-up that records this hash.
- **What works:**
  - `db/pool.py` (`connect()`, `make_pool()`, `set_search_path()`), `db/migrate.py` (`migrate(conn, schema)`, `applied_versions()`), and `db/migrations/001_init.sql` (all 10 tables plus `schema_migrations`);
  - `collector/ingest.py`: `scan(root, conn, machine, full=False, *, batch_lines=5000, progress=None)`;
  - `collector/skills_catalog.py`: `upload_catalog(conn, machine, catalog=None)`;
  - CLI `claude-lens scan [--full] [--projects-dir] [--batch-lines]` and `claude-lens status` (`migrate-sqlite` and `set-password` are still stubs);
  - `cd backend && uv run pytest`: **129 passed** (43 DB tests on a throwaway schema). `uv run pytest -m "not db"`: 86 pass offline in under a second;
  - the old app's 85-test suite still passes.
- **What doesn't / open issues:**
  - the real `claude_dashboard` schema **does not exist yet**. That's intentional: phase 02 creates it, then seeds it from SQLite before any real scan;
  - a run whose final retry also fails can't reach the DB to close its `sync_runs` row. The row stays `running` until a later scan on the same machine marks it `error` (after 6 hours).
- **Exact next step:** start phase 02 with `phase-02-sqlite-migration-and-daily-sync.md`.

## Environment facts

Add facts as you learn them. Never record secrets.

- `DATABASE_URL` is in `.env.local` at the repo root. The target schema is `claude_dashboard`.
- Python 3.12.7, uv 0.8.3, Node 24.12, pnpm 10.5 on the Windows PC.
- Old SQLite: `~/.claude/token-dashboard.db`. Transcripts: `~/.claude/projects`.
- The old scheduled task is named `Claude Token Dashboard - Daily Scan`.
- **`python3` doesn't work on this PC** (it's a Windows Store alias stub). Use `python` (3.12.7) for the old suite: `python -m unittest discover tests`. The old suite has **85** tests, not 68.
- Backend deps resolved by uv on 2026-11-22 (in `backend/uv.lock`):
  - runtime: fastapi 0.165.0, psycopg[binary] 3.3.9, psycopg-pool 3.3.3, pwdlib[argon2] 0.4.2, pydantic 2.14.4 (pydantic-core 2.50.5), uvicorn[standard] 0.54.0, starlette 1.10.0;
  - dev: pytest 9.2.0, httpx 0.28.1.
- `uvicorn[standard]` pulls in `python-dotenv` transitively. We don't use it; `config.py` has its own stdlib loader.
- The machine label default (`socket.gethostname()`) on this PC is `Zeeshan-Desktop`.
- Postgres server is **17** (`server_version_num` 170007). From the PC, a round-trip is **~150 ms** and a new connection takes **~1 s**.
- `TEST_DATABASE_URL` (optional) is used by the backend tests before `DATABASE_URL`. It's listed in `.env.example`.
- The skill catalog on this PC is **570 slugs**.
- SQLite `files.path` strings are exactly `str(Path)` of the `rglob` under `~/.claude/projects` (for example `C:\Users\…\.claude\projects\<slug>\<id>.jsonl`), the same as the new collector produces. Checked on 2026-11-22 against the live SQLite: with its offsets seeded, the collector would **skip 1,202** files, **rescan 3** (they changed since the last old-app scan) and find **75 missing**.

## Decisions & deviations

Record anything decided during implementation that isn't in README.md's Decisions table, with the date and the reason.

- **2026-11-22 (phase 00): `tool_use_id` is set on `_tool_result` rows too.** On those rows it's the block's `tool_use_id`, the same value already stored in `target`. Why: every tool dict now has identical keys, which keeps phase 01's COPY staging uniform. Phase 06 can also join a `tool_use` to its result with `u.tool_use_id = r.tool_use_id`. `target` is unchanged, so it still matches migrated SQLite rows.
- **2026-11-22 (phase 00): `format_for_user` was ported to `core/pricing.py`** along with `load_pricing`, `_tier_from_name` and `cost_for`. It's pure and has tests. Only `get_plan`/`set_plan` were left out.
- **2026-11-22 (phase 00): `DB_SCHEMA` is validated** as a plain SQL identifier (`^[A-Za-z_][A-Za-z0-9_]*$`) in `Settings`. Later phases should still quote it with `psycopg.sql.Identifier` when building `search_path`.
- **2026-11-22 (phase 00): `Settings` hides secrets in its repr.** `database_url` and `admin_password` are `repr=False`, so logging a `Settings` object doesn't leak them.
- **2026-11-22 (phase 01): transactions span files, not one per file.** Records from consecutive files are buffered until about 5,000 lines (`--batch-lines`), then written in one transaction together with every touched file's `files` offset. Big files are split across batches, each committing the offset it reached. Why: at 150 ms per round-trip, about 8 round-trips per transaction would make a 1,280-file scan take ~25 minutes. Walk order and "last wins" are unchanged.
- **2026-11-22 (phase 01): batch shape.** Messages and tool rows go through `COPY` into `TEMP … ON COMMIT DROP` tables (`s_messages` is `LIKE messages`). Titles and file offsets are inlined as `sql.Literal` VALUES in the single merge statement, which saves 4 round-trips per batch.
- **2026-11-22 (phase 01): dedup rule.** Keep the last occurrence per `uuid`, then the last per `(session_id, message_id)`, in walk/file order. Counts returned by `scan()` are records processed **before** dedup, exactly like `scan_dir`.
- **2026-11-22 (phase 01): accepted differences from SQLite.**
  - NUL characters are stripped, and unpaired surrogates become U+FFFD (Postgres text/jsonb reject both).
  - A record is **skipped** if its timestamp doesn't parse as ISO 8601, or its `type` or `uuid` is null, or `parse_record` raises (for example non-numeric usage). SQLite stored these or crashed the scan. Naive timestamps are read as UTC.
  - `prompt_tsv` indexes only the first 100,000 characters of `prompt_text`, because a tsvector over 1 MB makes the insert fail. `prompt_text` itself is stored in full.
  - `tool_calls.is_error` stays `INTEGER` 0/1 (the spec says "same columns"). Only `messages.is_sidechain` became `BOOLEAN`.
- **2026-11-22 (phase 01): retry semantics.** `scan` retries `psycopg.OperationalError` **3 times** after the first attempt (4 attempts in all), 60 seconds apart. Each attempt gets its own `sync_runs` row, and a failed attempt's row is closed as `error` ("connection lost: …") by the next one. `running` rows older than 6 hours on the same machine are closed as "interrupted". Any other exception closes the row as `error` with `Type: message`, with no retry.
- **2026-11-22 (phase 01): test fixture shape.** There's one throwaway schema per pytest **session**, truncated before each test, instead of one schema per test, because each migrate+connect costs about 2 s over the network. DB tests are auto-marked `db`.

## Session log

Add newest entries at the top, using this template:

```
### YYYY-MM-DD: Phase NN, <done | partial | blocked>
- **Did:** …
- **Files:** created … / changed … / deleted …
- **Verification:** <commands run and their real results: test counts, row counts, parity numbers>
- **Commit:** <hash + message, or "uncommitted">
- **Gotchas:** …
- **Notes for the next session:** <concrete, actionable; these override the phase file where they conflict>
```

### 2026-11-22: Phase 01, done
- **Did:**
  - wrote the Postgres schema (`001_init.sql`) and an advisory-locked migration runner;
  - wrote the `search_path` connection helpers and pool factory;
  - wrote the batched collector, keeping the SQLite scanner's skip/offset/partial-line/dedup semantics, plus the skill catalog upload;
  - implemented `claude-lens scan` (with retries and `sync_runs`) and `claude-lens status`;
  - added the throwaway-schema pytest fixtures and ported the dedup, rescan, walk and titles tests, plus robustness, unit, migration, catalog and CLI tests.
- **Files:**
  - created: `backend/claude_lens/db/{__init__,pool,migrate}.py`, `backend/claude_lens/db/migrations/001_init.sql`, `backend/claude_lens/collector/ingest.py`, `backend/tests/helpers.py`, `backend/tests/test_ingest_{dedup,rescan,walk,titles,robustness,unit}.py`, `backend/tests/test_{migrate,skills_upload}.py`;
  - changed: `backend/claude_lens/cli.py`, `backend/claude_lens/collector/skills_catalog.py` (`upload_catalog`), `backend/tests/{conftest,test_cli}.py`, `backend/pyproject.toml` (the `db` marker), `backend/README.md`, `.env.example` (`TEST_DATABASE_URL`), this file and the phase 01 file.
- **Verification:**
  - `cd backend && uv run pytest`: **129 passed** in 170 s. `-m db`: 43 passed. `-m "not db"`: 86 passed in 0.15 s.
  - `python -m unittest discover tests` (old app): **Ran 85 tests, OK**.
  - **Exit check 1:** copied `e--Projects-Claude-Code-1-Applications-ResuMatchAI` (81 MB, 19 JSONL files, 10,715 lines) to the scratchpad and ran `DB_SCHEMA=claude_lens_test_exit… claude-lens scan --projects-dir <copy>` twice.
    - Run 1: `scanned 19 files: 5933 messages, 3760 tool calls, 681 titles in 3 batches; 570 skills in catalog`, 11.3 s wall clock (7.4 s between the `sync_runs` timestamps).
    - Run 2: `scanned 0 files … in 0 batches`, 5.1 s wall clock (2.2 s run). It's mostly connect, migrate check and catalog upload.
  - **Parity:** ran the old `token_dashboard.scanner.scan_dir` on the same copy into a temp SQLite DB. Identical results:
    - scan_dir's own totals: 5,933 / 3,760 / 681 / 19;
    - rows: 3,724 messages, 3,020 tool_calls, 17 titles, 19 files, 17 sessions;
    - all 5 token sums, per-model sums (7 models), tool result tokens and errors, and prompt chars;
    - the uuid sets are identical.
  - **Exit check 2:** appended a copy of a real assistant line (new uuid, same `message.id`, `output_tokens` 999,999) and re-scanned. That scanned 1 file and 1 message. Exactly one row is left for `msg_011Cgv…`, and it's the new snapshot.
  - The exit-check schema was dropped afterwards. `pg_namespace` has no `claude%` schemas left, and `claude_dashboard` was never created.
- **Commit:** `3530e74 feat(collector): postgres schema, migrations and batched ingest`, pushed to `mzeeshanaltaf/main`.
- **Gotchas:**
  - **Postgres collation isn't byte order.** `ORDER BY model` sorts differently from SQLite, which broke a naive list comparison in the parity check. Phase 02's parity check and phase 03's ported query tests should compare as dicts/sets, or use `COLLATE "C"` where byte order matters.
  - `sum(bigint)` returns `numeric`, which psycopg gives back as `Decimal`. Cast (`::bigint`) or `int()` it before comparing or JSON-encoding.
  - The skill catalog registers an `<ancestor>:<skill>` slug for **every** ancestor folder, so a skill under a temp path yields about 9 slugs. Tests assert membership, not counts.
  - `load_settings()` writes `.env.local` values into `os.environ`. An autouse fixture in `conftest.py` restores the environment after each test. Any CLI test that connects **must** set `DB_SCHEMA` to the test schema first, or `.env.local`'s schema would be used.
  - Each `claude-lens scan` costs about 30 round-trips (≈5 s) even with nothing to do.
- **Notes for the next session:**
  - Use `claude_lens.db.pool.connect(settings)` for one-off connections. It sets `search_path`. Call `migrate(conn, settings.db_schema)` on an **idle** connection before writing.
  - The `files` table is `(machine, path, mtime DOUBLE PRECISION, bytes_read BIGINT, scanned_at TIMESTAMPTZ)`. Copy `path`, `mtime` and `bytes_read` from SQLite verbatim, with `machine = settings.machine` (`Zeeshan-Desktop`), so the first real `scan` skips the 1,202 unchanged files.
  - `messages` has a generated `prompt_tsv`: exclude it from the COPY column list. `tool_calls.is_error` is `INTEGER`, so copy 0/1 as-is. `messages.is_sidechain` is `BOOLEAN` (Postgres also accepts the text `'0'`/`'1'`). `tool_calls_json` is jsonb: SQLite text that contains `\u0000` or unpaired surrogate escapes will fail, so reuse `ingest._clean_json` / `_clean_text` for the migrated text columns.
  - `migrate-sqlite` should TRUNCATE `messages, tool_calls, session_titles, files, settings, dismissed_tips` for `--force` (not `sync_runs`, `skill_catalog` or `users`).
  - For the daily task: the CLI already prints `scanned N files: …` on success, which phase 02's log check looks for. `print()` is a no-op under `pythonw` (where `sys.stdout` is None), so add the file log handler as the phase file says.

### 2026-11-22: Phase 00, done
- **Did:**
  - fixed `.gitignore` (`.env*`, `!.env.example`, `.next/`, `backend/.venv/`, `.pytest_cache/`, `*.egg-info/`) and added `.env.example` (names only);
  - created the `backend/` uv project and `config.py` (`Settings` + a stdlib `.env.local`/`.env` loader);
  - copied the pure modules into `claude_lens/` (`core/pricing.py`, `core/names.py`, `collector/parse.py` with `tool_use_id`, `collector/skills_catalog.py`) and `pricing.json` into `backend/`;
  - ported the tests to pytest and added a stub CLI.
- **Files:**
  - created: `.env.example`, `backend/{pyproject.toml,uv.lock,README.md,pricing.json}`, `backend/claude_lens/{__init__,config,cli}.py`, `backend/claude_lens/core/{__init__,pricing,names}.py`, `backend/claude_lens/collector/{__init__,parse,skills_catalog}.py`, `backend/tests/{conftest,test_pricing,test_names,test_parse,test_skills_catalog,test_config,test_cli}.py`, `backend/tests/fixtures/*` (copied);
  - changed: `.gitignore`, this file, and the phase 00 file (boxes ticked, Outcome line).
- **Verification:**
  - `cd backend && uv run pytest`: **71 passed** in 0.10s (cli 6, config 14, names 11, parse 13, pricing 17, skills_catalog 10);
  - `uv run claude-lens --help` lists scan, migrate-sqlite, status and set-password;
  - `python -m unittest discover tests`: **Ran 85 tests, OK**;
  - `git check-ignore -v .env.local` matches `.gitignore:13:.env*`, and `git status` doesn't list `.env.local` (`.env.example` stays visible).
- **Commit:** `feat(backend): claude-lens uv scaffold with ported pure modules`, pushed to `mzeeshanaltaf/main` (find the hash with `git log --oneline -1`). It also includes the planning docs, the CLAUDE.md pointer, `.gitignore` and `.env.example`.
- **Gotchas:**
  - `python3` is a Store stub on this PC.
  - The old suite has 85 tests, not 68 as the phase file and CLAUDE.md say.
  - How the tests changed in the port:
    - `unittest` classes became pytest functions, with `tmp_path` in place of `tempfile.mkdtemp`;
    - fixture JSON is now read with explicit `encoding="utf-8"`;
    - the name tests came from `tests/test_queries.py::ProjectNameTests`, since there was no standalone names test;
    - only the pure `_session_title` part of `test_scanner_titles.py` was ported, because its scan/SQLite part belongs to phase 01's ingest;
    - added tests: `tool_use_id` on both row kinds, uniform tool-row keys, the `_tier_from_name` cases, `best_project_name`, `config` and the CLI.
- **Notes for the next session:**
  - `collector/parse.py` has no `_project_slug` helper and no file walking. Port `_project_slug`, `scan_file`'s partial-line guard and `scan_dir`'s mtime/offset skip logic into `collector/ingest.py`.
  - Get config via `claude_lens.config.load_settings()`. It loads the repo-root `.env.local` into `os.environ` (never overriding real vars) and returns `Settings`: `database_url`, `db_schema`, `machine`, `claude_projects_dir`, and so on.
  - For test schemas, `Settings.from_env({..., "DB_SCHEMA": "claude_lens_test_<hex>"})` passes validation.
  - `load_pricing()` defaults to `backend/pricing.json` via `DEFAULT_PRICING_PATH`.
  - Add `psycopg.sql` / `Identifier` usage for the schema; don't f-string it.
