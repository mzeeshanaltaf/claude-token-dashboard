# Phase 00: Repo hygiene & backend scaffold

**Goal:** make the repo safe to commit to, then create the `backend/` uv project and move the *pure* logic into it: pricing, project names, JSONL parsing and the skill catalog. Their tests come along and must pass. No database work and no API yet.

## Entry criteria

- None (this is the first phase). Still do protocol step A.

## Environment check

```bash
git status                                   # expect clean on main
python3 -m unittest discover tests           # old suite: expect 68 passing
uv --version
```

## Read first

- `token_dashboard/pricing.py`: `cost_for`, `_tier_from_name`, `load_pricing`
- `token_dashboard/db.py:163-216`: `_encode_slug`, `_walk_to_root`, `project_name_for`, `best_project_name`
- `token_dashboard/scanner.py:36-187`: `_session_title`, `_usage`, `_prompt_text`, `_target`, `_extract_tools`, `_extract_results`, `parse_record`
- `token_dashboard/skills.py`: `_slugs_for`, `scan_catalog`
- `tests/test_pricing.py`, `tests/test_scanner_parse.py`, `tests/test_skills.py`, `tests/test_scanner_titles.py` (title parsing part)

## Tasks

- [x] **`.gitignore`:** add `.env*` with `!.env.example`, plus `.next/`, `backend/.venv/`, `.pytest_cache/`, `*.egg-info/`. Then run `git check-ignore .env.local` to confirm it's ignored.
- [x] Add a root `.env.example` listing the variable names only: `DATABASE_URL`, `DB_SCHEMA=claude_dashboard`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `COOKIE_SECURE`, `BACKEND_URL`, `CLAUDE_PROJECTS_DIR`, `CLAUDE_LENS_MACHINE`.
- [x] Create the uv project in `backend/`:
  - `pyproject.toml` with name `claude-lens`, Python `>=3.12`, the `claude_lens` package and a `[project.scripts]` entry `claude-lens = "claude_lens.cli:main"`;
  - runtime deps: `psycopg[binary]`, `psycopg-pool`, `fastapi`, `uvicorn[standard]`, `pydantic`, `pwdlib[argon2]`;
  - dev deps: `pytest`, `httpx`.
- [x] Create `claude_lens/config.py`:
  - a dataclass `Settings` loaded from env;
  - a tiny `.env.local` / `.env` loader (stdlib, no python-dotenv) that searches the repo root and doesn't override real env vars;
  - `DB_SCHEMA` defaults to `claude_dashboard`, `CLAUDE_LENS_MACHINE` to `socket.gethostname()`, and `CLAUDE_PROJECTS_DIR` to `~/.claude/projects`.
- [x] Copy (don't move: the old app must keep working) these into `backend/claude_lens/`:
  - `core/pricing.py`: `load_pricing`, `_tier_from_name`, `cost_for`. Leave out `get_plan`/`set_plan`, which become DB queries in phase 03.
  - `core/names.py`: the slug/name helpers from `db.py`.
  - `collector/parse.py`: the parsing functions from `scanner.py`. Also capture **`tool_use_id`** (`block.get("id")`) on tool_use rows, as a new key on each tool dict.
  - `collector/skills_catalog.py`: `_slugs_for` and `scan_catalog` (keep the default roots).
- [x] Copy `pricing.json` to `backend/pricing.json`. The old copy stays at the root until phase 07.
- [x] Port the matching tests to pytest under `backend/tests/` (`test_pricing.py`, `test_names.py`, `test_parse.py`, `test_skills_catalog.py`, title parsing), along with `tests/fixtures/`. Add a test for the new `tool_use_id` field.
- [x] Stub `claude_lens/cli.py` with argparse subcommands `scan`, `migrate-sqlite`, `status` and `set-password`. Each prints "not implemented" for now.

## Exit criteria

- `cd backend && uv run pytest`: all ported tests pass.
- `uv run claude-lens --help` lists the 4 subcommands.
- The old suite still passes: `python3 -m unittest discover tests`.
- `git status` doesn't show `.env.local`.

## Handoff notes to capture

- The exact dependency versions `uv` resolved.
- Any test that needed changes while porting, and why.

## Outcome

Done 2026-11-22. Backend suite: 71 passed. `claude-lens --help` lists the 4 subcommands. The old suite passes with 85 tests (not 68). `.env.local` is ignored. On this PC, `python3` is a Windows Store stub, so run the old suite with `python -m unittest discover tests`. Details are in the HANDOFF.md session log.
