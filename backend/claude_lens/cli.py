"""claude-lens command line entry point."""
from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Sequence

import psycopg

from . import __version__
from .config import Settings, default_sync_log, load_settings
from .collector import migrate_sqlite as sqlite_migration
from .collector.ingest import BATCH_LINES, scan
from .collector.skills_catalog import upload_catalog
from .db.migrate import applied_versions, migrate
from .db.pool import connect

RETRIES = 3          # retries after the first attempt, on psycopg.OperationalError
RETRY_DELAY = 60     # seconds between attempts
STALE_RUN_HOURS = 6  # 'running' rows older than this are marked as interrupted
SYNC_LOG_BYTES = 1_000_000
DEFAULT_SQLITE = Path.home() / ".claude" / "token-dashboard.db"
_sleep = time.sleep  # patched in tests

log = logging.getLogger("claude_lens.sync")


def _not_implemented(args: argparse.Namespace) -> int:
    print(f"claude-lens {args.command}: not implemented")
    return 1


# --------------------------------------------------------------------------
# sync log
# --------------------------------------------------------------------------

class _BelowWarning(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.WARNING


def _open_sync_log(path: Path) -> None:
    """Send `claude_lens.sync` to a rotating file, plus the console when there is one.

    The scheduled task runs under pythonw, where sys.stdout and sys.stderr are
    None, so the file is the only record of a run. Console output keeps the
    plain message: info on stdout, warnings and errors on stderr.
    """
    _close_sync_log()
    log.setLevel(logging.INFO)
    log.propagate = False
    console = logging.Formatter("%(message)s")
    if sys.stdout is not None:
        out = logging.StreamHandler(sys.stdout)
        out.addFilter(_BelowWarning())
        out.setFormatter(console)
        log.addHandler(out)
    if sys.stderr is not None:
        err = logging.StreamHandler(sys.stderr)
        err.setLevel(logging.WARNING)
        err.setFormatter(console)
        log.addHandler(err)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(path, maxBytes=SYNC_LOG_BYTES, backupCount=1, encoding="utf-8")
    except OSError as e:
        log.warning("cannot open sync log %s: %s", path, e)
        return
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)


def _close_sync_log() -> None:
    for h in list(log.handlers):
        log.removeHandler(h)
        h.close()


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
            log.info("  batch %d: %d files, %d messages so far",
                     t["batches"], t["files"], t["messages"])

        try:
            totals = scan(root, conn, machine, full=full, batch_lines=batch_lines, progress=progress)
            skills = upload_catalog(conn, machine)
        except psycopg.OperationalError:
            raise  # retried by the caller; the next attempt closes this run row
        except Exception as e:  # noqa: BLE001 - record any failure on the run row
            _finish_run(conn, run_id, "error", None, f"{type(e).__name__}: {e}")
            state.run_id = None
            log.error("scan failed: %s: %s", type(e).__name__, e, exc_info=True)
            return 1
        _finish_run(conn, run_id, "ok", totals, None)
        state.run_id = None
    finally:
        conn.close()

    secs = time.monotonic() - started
    log.info(
        "scanned %d files: %d messages, %d tool calls, %d titles in %d batches; "
        "%d skills in catalog (machine %s, schema %s, %.1fs)",
        totals["files"], totals["messages"], totals["tools"], totals["titles"],
        totals["batches"], skills, machine, settings.db_schema, secs,
    )
    return 0


def _scan_with_retries(args: argparse.Namespace, settings: Settings) -> int:
    if not settings.database_url:
        log.error("DATABASE_URL is not set (put it in .env.local at the repo root)")
        return 2
    root = Path(args.projects_dir).expanduser() if args.projects_dir else settings.claude_projects_dir
    if not root.is_dir():
        log.error("projects dir not found: %s", root)
        return 2
    state = _RunState()
    attempt = 0
    while True:
        try:
            return _scan_once(settings, root, args.full, args.batch_lines, state)
        except psycopg.OperationalError as e:
            state.last_error = str(e).strip()
            if attempt >= RETRIES:
                log.error("scan failed after %d attempts: %s", attempt + 1, state.last_error)
                return 1
            attempt += 1
            log.warning("database error: %s; retry %d/%d in %ds",
                        state.last_error, attempt, RETRIES, RETRY_DELAY)
            _sleep(RETRY_DELAY)


def _cmd_scan(args: argparse.Namespace) -> int:
    try:
        settings = load_settings()
    except Exception:
        _open_sync_log(default_sync_log())
        log.exception("scan failed: invalid configuration")
        _close_sync_log()
        return 2
    _open_sync_log(settings.sync_log)
    try:
        return _scan_with_retries(args, settings)
    except Exception:  # noqa: BLE001 - under pythonw the log is the only place this shows
        log.exception("scan failed: unexpected error")
        return 1
    finally:
        _close_sync_log()


# --------------------------------------------------------------------------
# migrate-sqlite
# --------------------------------------------------------------------------

def _cmd_migrate_sqlite(args: argparse.Namespace) -> int:
    settings = load_settings()
    if not settings.database_url:
        print("DATABASE_URL is not set (put it in .env.local at the repo root)", file=sys.stderr)
        return 2
    machine = args.machine or settings.machine
    src_path = Path(args.sqlite).expanduser()
    started = time.monotonic()
    print(f"{'parity check' if args.check_only else 'migrating'} {src_path} -> "
          f"schema {settings.db_schema} (machine {machine})", flush=True)
    try:
        conn = connect(settings)
    except psycopg.OperationalError as e:
        print(f"cannot connect: {str(e).strip()}", file=sys.stderr)
        return 1
    try:
        if not args.check_only:
            migrate(conn, settings.db_schema)
        elif not applied_versions(conn):
            print("schema not initialised: nothing to check", file=sys.stderr)
            return 2
        copied, checks = sqlite_migration.run(
            src_path, conn, machine, force=args.force, check_only=args.check_only,
            chunk=args.chunk, progress=lambda m: print(m, flush=True),
        )
    except sqlite_migration.MigrationError as e:
        print(f"migrate-sqlite: {e}", file=sys.stderr)
        return 2
    finally:
        conn.close()

    secs = time.monotonic() - started
    if copied:
        print(f"copied {', '.join(f'{n:,} {t}' for t, n in copied.items())} in {secs:.1f}s")
    print("\nparity (sqlite vs postgres):")
    print(sqlite_migration.format_checks(checks))
    bad = [c for c in checks if not c.ok]
    if bad:
        print(f"\nparity FAILED: {len(bad)} of {len(checks)} checks differ", file=sys.stderr)
        return 1
    print(f"\nparity ok: {len(checks)} checks match ({secs:.1f}s total)")
    return 0


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

    p = sub.add_parser(
        "migrate-sqlite", help="Copy history from the old SQLite database into Postgres.",
        description="One-time copy of the old Token Dashboard SQLite history into Postgres,"
                    " followed by a parity check (exits non-zero on any mismatch).")
    p.add_argument("--sqlite", metavar="PATH", default=str(DEFAULT_SQLITE),
                   help=f"old SQLite database, opened read-only (default {DEFAULT_SQLITE})")
    p.add_argument("--machine", metavar="NAME",
                   help="machine label for migrated rows (default: CLAUDE_LENS_MACHINE or hostname)")
    p.add_argument("--force", action="store_true",
                   help="truncate the migrated tables first if Postgres already has data")
    p.add_argument("--check-only", action="store_true",
                   help="skip the copy; only run the parity check")
    p.add_argument("--chunk", type=int, default=sqlite_migration.CHUNK_ROWS, metavar="N",
                   help=f"rows per COPY chunk (default {sqlite_migration.CHUNK_ROWS})")
    p.set_defaults(func=_cmd_migrate_sqlite)

    stubs = {
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
