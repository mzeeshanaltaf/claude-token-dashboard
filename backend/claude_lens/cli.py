"""claude-lens command line entry point."""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import psycopg

from . import __version__
from .config import Settings, load_settings
from .collector.ingest import BATCH_LINES, scan
from .collector.skills_catalog import upload_catalog
from .db.migrate import applied_versions, migrate
from .db.pool import connect

RETRIES = 3          # retries after the first attempt, on psycopg.OperationalError
RETRY_DELAY = 60     # seconds between attempts
STALE_RUN_HOURS = 6  # 'running' rows older than this are marked as interrupted
_sleep = time.sleep  # patched in tests


def _not_implemented(args: argparse.Namespace) -> int:
    print(f"claude-lens {args.command}: not implemented")
    return 1


# --------------------------------------------------------------------------
# scan
# --------------------------------------------------------------------------

@dataclass
class _RunState:
    """Carries a run row across retries so a failed attempt's row gets closed."""
    run_id: Optional[int] = None
    last_error: Optional[str] = None


def _finish_run(conn, run_id: int, status: str, totals: Optional[dict], error: Optional[str]) -> None:
    totals = totals or {}
    with conn.transaction():
        conn.execute(
            "UPDATE sync_runs SET finished_at = now(), status = %s, error = %s,"
            " files = %s, messages = %s, tools = %s, titles = %s WHERE id = %s",
            (status, error, totals.get("files"), totals.get("messages"),
             totals.get("tools"), totals.get("titles"), run_id),
        )


def _scan_once(settings: Settings, root: Path, full: bool, batch_lines: int, state: _RunState) -> int:
    machine = settings.machine
    started = time.monotonic()
    conn = connect(settings)
    try:
        migrate(conn, settings.db_schema)
        with conn.transaction():
            if state.run_id is not None:  # the previous attempt lost its connection
                conn.execute(
                    "UPDATE sync_runs SET finished_at = now(), status = 'error', error = %s"
                    " WHERE id = %s AND status = 'running'",
                    (f"connection lost: {state.last_error}", state.run_id),
                )
                state.run_id = None
            conn.execute(
                "UPDATE sync_runs SET finished_at = now(), status = 'error',"
                " error = 'interrupted: the run never finished'"
                " WHERE machine = %s AND status = 'running'"
                " AND started_at < now() - make_interval(hours => %s)",
                (machine, STALE_RUN_HOURS),
            )
            run_id = conn.execute(
                "INSERT INTO sync_runs (machine, status) VALUES (%s, 'running') RETURNING id",
                (machine,),
            ).fetchone()[0]
        state.run_id = run_id

        def progress(t: dict) -> None:
            print(f"  batch {t['batches']}: {t['files']} files, {t['messages']} messages so far",
                  flush=True)

        try:
            totals = scan(root, conn, machine, full=full, batch_lines=batch_lines, progress=progress)
            skills = upload_catalog(conn, machine)
        except psycopg.OperationalError:
            raise  # retried by the caller; the next attempt closes this run row
        except Exception as e:  # noqa: BLE001 - record any failure on the run row
            _finish_run(conn, run_id, "error", None, f"{type(e).__name__}: {e}")
            state.run_id = None
            print(f"scan failed: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        _finish_run(conn, run_id, "ok", totals, None)
        state.run_id = None
    finally:
        conn.close()

    secs = time.monotonic() - started
    print(
        f"scanned {totals['files']} files: {totals['messages']} messages, "
        f"{totals['tools']} tool calls, {totals['titles']} titles "
        f"in {totals['batches']} batches; {skills} skills in catalog "
        f"(machine {machine}, schema {settings.db_schema}, {secs:.1f}s)",
        flush=True,
    )
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    settings = load_settings()
    if not settings.database_url:
        print("DATABASE_URL is not set (put it in .env.local at the repo root)", file=sys.stderr)
        return 2
    root = Path(args.projects_dir).expanduser() if args.projects_dir else settings.claude_projects_dir
    if not root.is_dir():
        print(f"projects dir not found: {root}", file=sys.stderr)
        return 2
    state = _RunState()
    attempt = 0
    while True:
        try:
            return _scan_once(settings, root, args.full, args.batch_lines, state)
        except psycopg.OperationalError as e:
            state.last_error = str(e).strip()
            if attempt >= RETRIES:
                print(f"scan failed after {attempt + 1} attempts: {state.last_error}", file=sys.stderr)
                return 1
            attempt += 1
            print(f"database error: {state.last_error}; retry {attempt}/{RETRIES} in {RETRY_DELAY}s",
                  file=sys.stderr, flush=True)
            _sleep(RETRY_DELAY)


# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------

_COUNT_TABLES = ("messages", "tool_calls", "session_titles", "files", "skill_catalog", "sync_runs")


def _fmt_dt(dt) -> str:
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S") if dt else "-"


def _cmd_status(args: argparse.Namespace) -> int:
    settings = load_settings()
    if not settings.database_url:
        print("DATABASE_URL is not set (put it in .env.local at the repo root)", file=sys.stderr)
        return 2
    try:
        conn = connect(settings)
    except psycopg.OperationalError as e:
        print(f"cannot connect: {str(e).strip()}", file=sys.stderr)
        return 1
    try:
        print(f"schema {settings.db_schema}, machine {settings.machine}")
        versions = applied_versions(conn)
        if not versions:
            print("not initialised: no migrations applied yet (run `claude-lens scan`)")
            return 0
        print(f"migrations applied: {', '.join(f'{v:03d}' for v in versions)}")

        runs = conn.execute(
            "SELECT id, machine, started_at, finished_at, status, files, messages, tools, titles, error"
            " FROM sync_runs ORDER BY started_at DESC, id DESC LIMIT 5"
        ).fetchall()
        print("\nlast sync runs:")
        if not runs:
            print("  (none)")
        for rid, mach, start, end, status, files, msgs, tools, titles, err in runs:
            dur = f"{(end - start).total_seconds():.1f}s" if end else "-"
            line = (f"  #{rid} {_fmt_dt(start)} {status:<7} {dur:>8}  {mach}  "
                    f"files={files if files is not None else '-'} "
                    f"messages={msgs if msgs is not None else '-'} "
                    f"tools={tools if tools is not None else '-'} "
                    f"titles={titles if titles is not None else '-'}")
            if err:
                line += f"\n      error: {err[:200]}"
            print(line)

        print("\nrow counts:")
        for table in _COUNT_TABLES:
            n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            print(f"  {table:<15} {n:>10,}")
        sessions = conn.execute("SELECT count(DISTINCT session_id) FROM messages").fetchone()[0]
        print(f"  {'sessions':<15} {sessions:>10,}")
        conn.rollback()
    finally:
        conn.close()
    return 0


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude-lens",
        description="Claude Lens: usage, cost & workflow analytics for Claude Code.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>", required=True)

    p = sub.add_parser("scan", help="Ingest new JSONL transcript lines into Postgres.",
                       description="Ingest new JSONL transcript lines into Postgres.")
    p.add_argument("--full", action="store_true",
                   help="ignore stored offsets and re-read every transcript (idempotent)")
    p.add_argument("--projects-dir", metavar="PATH",
                   help="transcript folder (default: CLAUDE_PROJECTS_DIR or ~/.claude/projects)")
    p.add_argument("--batch-lines", type=int, default=BATCH_LINES, metavar="N",
                   help=f"lines per transaction (default {BATCH_LINES})")
    p.set_defaults(func=_cmd_scan)

    p = sub.add_parser("status", help="Show sync status and database counts.",
                       description="Show sync status and database counts.")
    p.set_defaults(func=_cmd_status)

    stubs = {
        "migrate-sqlite": "Copy history from the old SQLite database into Postgres.",
        "set-password": "Reset the admin password.",
    }
    for name, help_text in stubs.items():
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.set_defaults(func=_not_implemented)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
