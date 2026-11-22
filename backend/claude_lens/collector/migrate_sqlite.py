"""One-time copy of the old Token Dashboard SQLite history into Postgres.

`claude-lens migrate-sqlite` exists because the old DB holds rows whose JSONL
transcripts are gone from disk, so a rescan can't rebuild them. It:

* opens SQLite **read-only** and reads every table inside **one** read
  transaction, so the copy and the parity check see the same snapshot even if
  the old app's scanner is running (in rollback-journal mode it waits for us);
* refuses to touch a Postgres schema that already has data, unless `force`
  (which truncates the migrated tables first);
* streams each table in chunks through `COPY`, one transaction per table;
* copies `files` offsets verbatim, so the next `claude-lens scan` only reads
  what changed since the old app's last scan;
* runs `ANALYZE`, then a parity check (counts, distinct sessions, token sums
  overall and per model, exact `files` offsets) that the CLI prints.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from .ingest import MSG_COLS, _clean_json, _clean_text, _parse_ts

CHUNK_ROWS = 20_000

# Tables `force` empties. sync_runs, skill_catalog, users and auth_sessions
# aren't part of the old DB, so they're left alone.
TARGET_TABLES = ("messages", "tool_calls", "session_titles", "files", "settings", "dismissed_tips")
# Any of these being non-empty means the schema already holds history.
_GUARD_TABLES = ("messages", "tool_calls", "session_titles", "files", "dismissed_tips")

TOKEN_COLS = (
    "input_tokens", "output_tokens", "cache_read_tokens",
    "cache_create_5m_tokens", "cache_create_1h_tokens",
)
# SQLite has every messages column except `machine` (added here).
_SRC_MSG_COLS = tuple(c for c in MSG_COLS if c != "machine")
_TOOL_COLS = ("message_uuid", "session_id", "project_slug", "tool_name", "target",
              "result_tokens", "is_error", "timestamp")
_MSG_TEXT_COLS = frozenset((
    "uuid", "parent_uuid", "session_id", "project_slug", "cwd", "git_branch", "cc_version",
    "entrypoint", "type", "agent_id", "model", "stop_reason", "prompt_id", "message_id",
    "prompt_text",
))

Progress = Callable[[str], None]


class MigrationError(RuntimeError):
    """The migration can't (or mustn't) proceed; the message says why."""


# --------------------------------------------------------------------------
# SQLite side
# --------------------------------------------------------------------------

def open_sqlite_readonly(path: Union[str, Path]) -> sqlite3.Connection:
    """Open the SQLite file with `mode=ro`, so nothing here can ever write to it."""
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise MigrationError(f"SQLite database not found: {path}")
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    # Manage the transaction by hand: one BEGIN spans every read.
    conn.isolation_level = None
    return conn


def _sqlite_tables(src: sqlite3.Connection) -> set:
    return {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _require_source_tables(src: sqlite3.Connection) -> set:
    tables = _sqlite_tables(src)
    missing = {"messages", "tool_calls", "files"} - tables
    if missing:
        raise MigrationError(
            f"not a Token Dashboard database (missing tables: {', '.join(sorted(missing))})"
        )
    return tables


def _chunks(cur: sqlite3.Cursor, size: int) -> Iterable[List[tuple]]:
    while True:
        rows = cur.fetchmany(size)
        if not rows:
            return
        yield rows


# --------------------------------------------------------------------------
# Row conversion (SQLite types -> what the Postgres columns expect)
# --------------------------------------------------------------------------

def _ts(value, what: str) -> datetime:
    ts = _parse_ts(value)
    if ts is None:
        raise MigrationError(f"unparseable timestamp {value!r} in {what}")
    return ts


def _epoch(value) -> datetime:
    return datetime.fromtimestamp(float(value), tz=timezone.utc)


def _message_row(row: tuple, machine: str) -> tuple:
    rec = dict(zip(_SRC_MSG_COLS, row))
    out = []
    for c in MSG_COLS:
        if c == "machine":
            out.append(machine)
            continue
        v = rec[c]
        if c in _MSG_TEXT_COLS:
            v = _clean_text(v)
        elif c == "is_sidechain":
            v = bool(v)
        elif c == "timestamp":
            v = _ts(v, f"messages uuid={rec['uuid']}")
        elif c == "tool_calls_json":
            v = _clean_json(v)
        out.append(v)
    return tuple(out)


def _tool_row(row: tuple) -> tuple:
    rec = dict(zip(_TOOL_COLS, row))
    return tuple(
        _ts(rec[c], f"tool_calls message_uuid={rec['message_uuid']}") if c == "timestamp"
        else _clean_text(rec[c]) if c in ("message_uuid", "session_id", "project_slug",
                                          "tool_name", "target")
        else rec[c]
        for c in _TOOL_COLS
    )


# --------------------------------------------------------------------------
# Copy
# --------------------------------------------------------------------------

@dataclass
class _Table:
    name: str
    select: str
    columns: Sequence[str]
    convert: Callable[[tuple], tuple]


def _plan(machine: str, tables: set) -> List[_Table]:
    plan = [
        _Table("messages", f"SELECT {', '.join(_SRC_MSG_COLS)} FROM messages ORDER BY rowid",
               MSG_COLS, lambda r: _message_row(r, machine)),
        # SQLite's id is dropped: BIGSERIAL assigns new ones in the same order.
        _Table("tool_calls", f"SELECT {', '.join(_TOOL_COLS)} FROM tool_calls ORDER BY id",
               _TOOL_COLS, _tool_row),
        _Table("files", "SELECT path, mtime, bytes_read, scanned_at FROM files ORDER BY path",
               ("machine", "path", "mtime", "bytes_read", "scanned_at"),
               # mtime stays a float8 bit-for-bit so the collector's equality check holds.
               lambda r: (machine, r[0], float(r[1]), int(r[2]), _epoch(r[3]))),
    ]
    if "session_titles" in tables:
        plan.append(_Table(
            "session_titles", "SELECT session_id, title FROM session_titles ORDER BY session_id",
            ("session_id", "title"), lambda r: (_clean_text(r[0]), _clean_text(r[1]))))
    if "dismissed_tips" in tables:
        plan.append(_Table(
            "dismissed_tips", "SELECT tip_key, dismissed_at FROM dismissed_tips ORDER BY tip_key",
            ("tip_key", "dismissed_at"), lambda r: (_clean_text(r[0]), _epoch(r[1]))))
    return plan


def _nonempty_tables(conn: psycopg.Connection) -> List[str]:
    found = []
    with conn.transaction():
        for t in _GUARD_TABLES:
            q = sql.SQL("SELECT EXISTS (SELECT 1 FROM {})").format(sql.Identifier(t))
            if conn.execute(q).fetchone()[0]:
                found.append(t)
    return found


def _truncate(conn: psycopg.Connection) -> None:
    with conn.transaction():
        conn.execute(sql.SQL("TRUNCATE {} RESTART IDENTITY").format(
            sql.SQL(", ").join(sql.Identifier(t) for t in TARGET_TABLES)))


def _copy_table(conn: psycopg.Connection, src: sqlite3.Connection, t: _Table,
                chunk: int, progress: Progress) -> int:
    total = src.execute(f"SELECT count(*) FROM {t.name}").fetchone()[0]
    copy_sql = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(t.name), sql.SQL(", ").join(sql.Identifier(c) for c in t.columns))
    started = time.monotonic()
    done = 0
    with conn.transaction():
        with conn.cursor() as cur:
            for rows in _chunks(src.execute(t.select), chunk):
                with cur.copy(copy_sql) as cp:
                    for r in rows:
                        cp.write_row(t.convert(r))
                done += len(rows)
                progress(f"  {t.name}: {done:,}/{total:,} rows")
    progress(f"  {t.name}: {done:,} rows committed in {time.monotonic() - started:.1f}s")
    return done


def _copy_plan(conn: psycopg.Connection, src: sqlite3.Connection, tables: set) -> Optional[str]:
    """Copy plan.k='plan' into settings; returns the plan value (or None)."""
    if "plan" not in tables:
        return None
    row = src.execute("SELECT v FROM plan WHERE k = 'plan'").fetchone()
    if not row or row[0] is None:
        return None
    with conn.transaction():
        conn.execute(
            "INSERT INTO settings (k, v) VALUES ('plan', %s)"
            " ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v",
            (Jsonb(row[0]),),
        )
    return row[0]


def migrate_sqlite(
    src: sqlite3.Connection,
    conn: psycopg.Connection,
    machine: str,
    *,
    force: bool = False,
    chunk: int = CHUNK_ROWS,
    progress: Progress = lambda _msg: None,
) -> Dict[str, int]:
    """Copy every table from `src` into the (already migrated) Postgres schema.

    `src` must already be inside a read transaction (see `run`) for the copy to
    be a consistent snapshot. Returns rows copied per table.
    """
    tables = _require_source_tables(src)
    busy = _nonempty_tables(conn)
    if busy and not force:
        raise MigrationError(
            f"the Postgres schema already has data ({', '.join(busy)}); "
            "pass --force to truncate and re-import"
        )
    if force:
        progress(f"--force: truncating {', '.join(TARGET_TABLES)}")
        _truncate(conn)

    copied: Dict[str, int] = {}
    for t in _plan(machine, tables):
        copied[t.name] = _copy_table(conn, src, t, chunk, progress)
    plan = _copy_plan(conn, src, tables)
    copied["settings"] = 0 if plan is None else 1
    progress(f"  settings: plan = {plan!r}" if plan is not None else "  settings: no plan set")

    progress("  ANALYZE")
    conn.execute(sql.SQL("ANALYZE {}").format(
        sql.SQL(", ").join(sql.Identifier(t) for t in TARGET_TABLES)))
    conn.commit()
    return copied


# --------------------------------------------------------------------------
# Parity
# --------------------------------------------------------------------------

@dataclass
class Check:
    metric: str
    sqlite: object
    postgres: object

    @property
    def ok(self) -> bool:
        return self.sqlite == self.postgres


def _sums_sql(extra_select: str = "", group: str = "") -> str:
    sums = ", ".join(f"CAST(COALESCE(SUM({c}), 0) AS BIGINT)" for c in TOKEN_COLS)
    return f"SELECT {extra_select}count(*), {sums} FROM messages {group}"


def _files_set(rows) -> set:
    return {(p, float(m), int(b)) for p, m, b in rows}


def parity(src: sqlite3.Connection, conn: psycopg.Connection, machine: str) -> List[Check]:
    """Compare SQLite and Postgres. Postgres messages and files are filtered to
    `machine`; tables without that column are compared as totals, which is exact
    right after a migration (the schema then holds only this machine's history)."""
    tables = _sqlite_tables(src)
    checks: List[Check] = []

    def s1(query: str):
        return src.execute(query).fetchone()[0]

    def p1(query: str, params=()):
        return conn.execute(query, params).fetchone()[0]

    try:
        checks.append(Check("messages", s1("SELECT count(*) FROM messages"),
                            p1("SELECT count(*) FROM messages WHERE machine = %s", (machine,))))
        for name in ("tool_calls", "session_titles", "dismissed_tips"):
            if name in tables:
                checks.append(Check(name, s1(f"SELECT count(*) FROM {name}"),
                                    p1(f"SELECT count(*) FROM {name}")))
        checks.append(Check("files", s1("SELECT count(*) FROM files"),
                            p1("SELECT count(*) FROM files WHERE machine = %s", (machine,))))
        checks.append(Check(
            "distinct sessions", s1("SELECT count(DISTINCT session_id) FROM messages"),
            p1("SELECT count(DISTINCT session_id) FROM messages WHERE machine = %s", (machine,))))

        s_tot = src.execute(_sums_sql()).fetchone()
        p_tot = conn.execute(_sums_sql(group="WHERE machine = %s"), (machine,)).fetchone()
        for i, c in enumerate(TOKEN_COLS, start=1):
            checks.append(Check(f"sum({c})", s_tot[i], p_tot[i]))

        checks.append(Check(
            "sum(tool result_tokens)",
            s1("SELECT COALESCE(SUM(result_tokens), 0) FROM tool_calls"),
            p1("SELECT CAST(COALESCE(SUM(result_tokens), 0) AS BIGINT) FROM tool_calls")))
        checks.append(Check(
            "tool errors", s1("SELECT COALESCE(SUM(is_error), 0) FROM tool_calls"),
            p1("SELECT CAST(COALESCE(SUM(is_error), 0) AS BIGINT) FROM tool_calls")))

        # Per model: compare as dicts (Postgres collation != SQLite byte order).
        s_models = {r[0]: tuple(r[1:]) for r in
                    src.execute(_sums_sql("model, ", "GROUP BY model")).fetchall()}
        p_models = {r[0]: tuple(r[1:]) for r in conn.execute(
            _sums_sql("model, ", "WHERE machine = %s GROUP BY model"), (machine,)).fetchall()}
        for model in sorted(set(s_models) | set(p_models), key=lambda m: (m is None, m or "")):
            checks.append(Check(f"model {model or '(none)'}: rows+5 sums",
                                s_models.get(model), p_models.get(model)))

        s_files = _files_set(src.execute("SELECT path, mtime, bytes_read FROM files"))
        p_files = _files_set(conn.execute(
            "SELECT path, mtime, bytes_read FROM files WHERE machine = %s", (machine,)))
        checks.append(Check("files (path, mtime, bytes_read) identical",
                            len(s_files), len(s_files) if s_files == p_files
                            else f"{len(s_files ^ p_files)} differ"))

        if "plan" in tables:
            row = src.execute("SELECT v FROM plan WHERE k = 'plan'").fetchone()
            pg = conn.execute("SELECT v FROM settings WHERE k = 'plan'").fetchone()
            checks.append(Check("plan", row[0] if row else None, pg[0] if pg else None))
    finally:
        conn.rollback()
    return checks


def format_checks(checks: Sequence[Check]) -> str:
    def fmt(v) -> str:
        if isinstance(v, int) and not isinstance(v, bool):
            return f"{v:,}"
        if isinstance(v, tuple):
            return f"{v[0]:,} rows, {sum(v[1:]):,} tok"
        return str(v)

    rows = [(c.metric, fmt(c.sqlite), fmt(c.postgres), "ok" if c.ok else "MISMATCH")
            for c in checks]
    w = [max(len(r[i]) for r in rows + [("metric", "sqlite", "postgres", "")]) for i in range(3)]
    lines = [f"  {'metric':<{w[0]}}  {'sqlite':>{w[1]}}  {'postgres':>{w[2]}}",
             f"  {'-' * w[0]}  {'-' * w[1]}  {'-' * w[2]}"]
    lines += [f"  {m:<{w[0]}}  {s:>{w[1]}}  {p:>{w[2]}}  {mark}" for m, s, p, mark in rows]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Entry point used by the CLI
# --------------------------------------------------------------------------

def run(
    sqlite_path: Union[str, Path],
    conn: psycopg.Connection,
    machine: str,
    *,
    force: bool = False,
    check_only: bool = False,
    chunk: int = CHUNK_ROWS,
    progress: Progress = lambda _msg: None,
) -> Tuple[Dict[str, int], List[Check]]:
    """Migrate (unless `check_only`) and run the parity check on one SQLite snapshot."""
    src = open_sqlite_readonly(sqlite_path)
    try:
        src.execute("BEGIN")  # one consistent snapshot for the copy and the check
        copied: Dict[str, int] = {}
        if not check_only:
            copied = migrate_sqlite(src, conn, machine, force=force, chunk=chunk,
                                    progress=progress)
        else:
            _require_source_tables(src)
        checks = parity(src, conn, machine)
        src.execute("ROLLBACK")
    finally:
        src.close()
    return copied, checks
