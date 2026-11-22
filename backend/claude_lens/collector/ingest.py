"""Batched JSONL -> Postgres ingest (the `claude-lens scan` engine).

Semantics are ported from `token_dashboard/scanner.py` (`scan_dir`, `scan_file`,
`_evict_prior_snapshots`):

* **Incremental walk.** A file is skipped when its stored `(mtime, bytes_read)`
  equals its current `(st_mtime, st_size)`. If it grew, reading resumes at
  `bytes_read`; otherwise (touched, rewritten, shrunk) it's re-read from 0.
  Offsets live in `files`, keyed by `(machine, path)`.
* **Partial-line guard.** Reading stops at a line with no trailing newline
  (Claude Code mid-flush), and the stored offset is the end of the last
  complete line, so the partial line is re-read once it's finished.
* **Streaming-snapshot dedup.** Claude Code writes 2-3 lines per assistant
  response with the same `message.id` but different `uuid`s; only the last
  one matches billing. Per `(session_id, message_id)` the last record wins,
  and older snapshots already in the DB are evicted (with their tool rows).
* **Idempotent replays.** Messages upsert on `uuid`; a message's tool rows are
  deleted and re-inserted.

What's new is the batching. The VPS is ~150 ms away, so instead of one
statement per line, records from consecutive files are buffered until about
`batch_lines` lines, then written in **one transaction**: COPY into temp
staging tables, then a single multi-statement merge. The `files` offsets for
everything in the batch are upserted in that same transaction, so a crash
never records an offset for rows that weren't written. A big file is split
across several batches, each committing the offset it reached.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple, Union

import psycopg
from psycopg import sql

from .parse import _session_title, parse_record

BATCH_LINES = 5000
_SURROGATE_RE = re.compile("[\ud800-\udfff]")

MSG_COLS = (
    "uuid", "parent_uuid", "session_id", "project_slug", "machine", "cwd", "git_branch",
    "cc_version", "entrypoint", "type", "is_sidechain", "agent_id", "timestamp", "model",
    "stop_reason", "prompt_id", "message_id", "input_tokens", "output_tokens",
    "cache_read_tokens", "cache_create_5m_tokens", "cache_create_1h_tokens",
    "prompt_text", "prompt_chars", "tool_calls_json",
)
TOOL_COLS = (
    "message_uuid", "session_id", "project_slug", "tool_name", "target", "tool_use_id",
    "result_tokens", "is_error", "timestamp",
)
_TEXT_MSG_COLS = (
    "uuid", "parent_uuid", "session_id", "cwd", "git_branch", "cc_version", "entrypoint",
    "type", "agent_id", "model", "stop_reason", "prompt_id", "message_id", "prompt_text",
)

_STAGE_DDL = """
CREATE TEMP TABLE s_messages (LIKE messages) ON COMMIT DROP;
CREATE TEMP TABLE s_tools (
  seq INTEGER NOT NULL, message_uuid TEXT, session_id TEXT, project_slug TEXT,
  tool_name TEXT, target TEXT, tool_use_id TEXT, result_tokens INTEGER,
  is_error INTEGER, timestamp TIMESTAMPTZ
) ON COMMIT DROP;
"""

_MSG_COL_LIST = ", ".join(MSG_COLS)
_TOOL_COL_LIST = ", ".join(TOOL_COLS)
_MSG_UPDATE = ", ".join(f"{c} = EXCLUDED.{c}" for c in MSG_COLS if c != "uuid")

# Runs after the COPYs, as one round trip. Order matters: evict superseded
# snapshots first, then upsert, then replace tool rows. Titles and file
# offsets are few per batch, so they're inlined as quoted VALUES (built with
# sql.Literal) instead of costing two more COPY round trips each.
_MERGE_SQL = f"""
WITH evicted AS (
  DELETE FROM messages m USING s_messages s
  WHERE m.session_id = s.session_id AND m.message_id = s.message_id AND m.uuid <> s.uuid
  RETURNING m.uuid
)
DELETE FROM tool_calls t USING evicted e WHERE t.message_uuid = e.uuid;

INSERT INTO messages ({_MSG_COL_LIST})
SELECT {_MSG_COL_LIST} FROM s_messages
ON CONFLICT (uuid) DO UPDATE SET {_MSG_UPDATE};

DELETE FROM tool_calls t USING s_messages s WHERE t.message_uuid = s.uuid;

INSERT INTO tool_calls ({_TOOL_COL_LIST})
SELECT {_TOOL_COL_LIST} FROM s_tools ORDER BY seq;
"""
_TITLES_SQL = sql.SQL(
    "INSERT INTO session_titles (session_id, title) VALUES {}"
    " ON CONFLICT (session_id) DO UPDATE SET title = EXCLUDED.title;"
)
_FILES_SQL = sql.SQL(
    "INSERT INTO files (machine, path, mtime, bytes_read, scanned_at) VALUES {}"
    " ON CONFLICT (machine, path) DO UPDATE SET mtime = EXCLUDED.mtime,"
    " bytes_read = EXCLUDED.bytes_read, scanned_at = EXCLUDED.scanned_at;"
)


def _values(rows) -> sql.Composed:
    return sql.SQL(", ").join(
        sql.SQL("({})").format(sql.SQL(", ").join(
            sql.SQL("now()") if v is _NOW else sql.Literal(v) for v in row
        ))
        for row in rows
    )


_NOW = object()  # placeholder for now() in _values rows


# --------------------------------------------------------------------------
# Value cleaning: Postgres rejects things SQLite happily stored.
# --------------------------------------------------------------------------

def _clean_text(v) -> Optional[str]:
    """Coerce to a str Postgres accepts: no NUL bytes, no lone surrogates."""
    if v is None:
        return None
    if not isinstance(v, str):
        v = json.dumps(v) if isinstance(v, (dict, list)) else str(v)
    if "\x00" in v:
        v = v.replace("\x00", "")
    try:
        v.encode("utf-8")
    except UnicodeEncodeError:
        # A surrogate code unit in a Python str is always unpaired (json.loads
        # produces one from a stray "\ud83d" escape); UTF-8 can't encode it.
        v = _SURROGATE_RE.sub("�", v)
    return v


def _clean_obj(o):
    if isinstance(o, str):
        return _clean_text(o)
    if isinstance(o, list):
        return [_clean_obj(x) for x in o]
    if isinstance(o, dict):
        return {_clean_text(k): _clean_obj(x) for k, x in o.items()}
    return o


def _clean_json(s: Optional[str]) -> Optional[str]:
    """jsonb rejects \\u0000 and unpaired surrogate escapes; rebuild only when needed."""
    if s is None:
        return None
    if "\\u0000" in s or "\\ud" in s.lower():
        s = json.dumps(_clean_obj(json.loads(s)), ensure_ascii=False)
    return s


def _parse_ts(v) -> Optional[datetime]:
    if not isinstance(v, str):
        return None
    try:
        ts = datetime.fromisoformat(v)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


# --------------------------------------------------------------------------
# Reading & parsing
# --------------------------------------------------------------------------

def _project_slug(file_path: Path, projects_root: Path) -> str:
    return file_path.relative_to(projects_root).parts[0]


def _iter_lines(path: Path, start_byte: int) -> Iterator[Tuple[bytes, int]]:
    """Yield `(raw_line, end_offset)` for each complete line from `start_byte`.

    Stops at a trailing line with no newline (the partial-line guard).
    """
    pos = start_byte
    with open(path, "rb") as fb:
        if start_byte:
            fb.seek(start_byte)
        for raw in fb:
            if not raw.endswith(b"\n"):
                break
            pos += len(raw)
            yield raw, pos


@dataclass
class _Record:
    msg: dict
    tools: List[dict]


def _parse_line(raw: bytes, slug: str, machine: str):
    """Return ('title', (sid, title)), ('msg', _Record) or None for a skipped line."""
    line = raw.decode("utf-8", errors="replace").strip()
    if not line:
        return None
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        return None
    title = _session_title(rec)
    if title is not None:
        return "title", (_clean_text(title[0]), _clean_text(title[1]))
    if not isinstance(rec, dict) or "uuid" not in rec or "type" not in rec:
        return None
    try:
        msg, tools = parse_record(rec, slug)
    except (TypeError, ValueError, AttributeError):
        return None  # malformed usage numbers etc.; SQLite would have crashed
    if not msg["session_id"] or not msg["timestamp"]:
        return None
    ts = _parse_ts(msg["timestamp"])
    for col in _TEXT_MSG_COLS:
        msg[col] = _clean_text(msg[col])
    if ts is None or not msg["uuid"] or not msg["type"] or not msg["session_id"]:
        return None
    msg["timestamp"] = ts
    msg["machine"] = machine
    msg["project_slug"] = _clean_text(slug)
    msg["is_sidechain"] = bool(msg["is_sidechain"])
    msg["tool_calls_json"] = _clean_json(msg["tool_calls_json"])
    for t in tools:
        t["message_uuid"] = msg["uuid"]
        t["session_id"] = msg["session_id"]
        t["project_slug"] = msg["project_slug"]
        t["tool_name"] = _clean_text(t["tool_name"]) or "unknown"
        t["target"] = _clean_text(t["target"])
        t["tool_use_id"] = _clean_text(t["tool_use_id"])
        t["timestamp"] = ts
    return "msg", _Record(msg, tools)


def dedup_records(records: List[_Record]) -> List[_Record]:
    """Keep the last occurrence per `uuid`, then the last per `(session_id, message_id)`.

    Input is in file order (files in walk order, lines in file order), which is
    the order the SQLite scanner applied them in, so "last" means the same thing.
    Records without a `message_id` are only deduped by `uuid`.
    """
    last_by_uuid: Dict[str, int] = {}
    last_by_key: Dict[Tuple[str, str], int] = {}
    for i, r in enumerate(records):
        last_by_uuid[r.msg["uuid"]] = i
        if r.msg["message_id"]:
            last_by_key[(r.msg["session_id"], r.msg["message_id"])] = i
    out = []
    for i, r in enumerate(records):
        if last_by_uuid[r.msg["uuid"]] != i:
            continue
        mid = r.msg["message_id"]
        if mid and last_by_key[(r.msg["session_id"], mid)] != i:
            continue
        out.append(r)
    return out


# --------------------------------------------------------------------------
# Batching
# --------------------------------------------------------------------------

@dataclass
class _Batch:
    records: List[_Record] = field(default_factory=list)
    titles: Dict[str, str] = field(default_factory=dict)  # last one wins
    files: Dict[str, Tuple[float, int]] = field(default_factory=dict)  # path -> (mtime, offset)
    lines: int = 0

    def empty(self) -> bool:
        return not (self.records or self.titles or self.files)


def _flush(conn: psycopg.Connection, batch: _Batch, machine: str) -> None:
    rows = dedup_records(batch.records)
    merge: List[sql.Composable] = []
    with conn.transaction():
        with conn.cursor() as cur:
            if rows:
                cur.execute(_STAGE_DDL)
                with cur.copy(f"COPY s_messages ({_MSG_COL_LIST}) FROM STDIN") as cp:
                    for r in rows:
                        cp.write_row(tuple(r.msg[c] for c in MSG_COLS))
                tool_rows = [t for r in rows for t in r.tools]
                if tool_rows:
                    with cur.copy(f"COPY s_tools (seq, {_TOOL_COL_LIST}) FROM STDIN") as cp:
                        for seq, t in enumerate(tool_rows):
                            cp.write_row((seq, *(t[c] for c in TOOL_COLS)))
                merge.append(sql.SQL(_MERGE_SQL))
            if batch.titles:
                merge.append(_TITLES_SQL.format(_values(batch.titles.items())))
            if batch.files:
                merge.append(_FILES_SQL.format(_values(
                    (machine, path, mtime, offset, _NOW)
                    for path, (mtime, offset) in batch.files.items()
                )))
            if merge:
                cur.execute(sql.SQL("\n").join(merge))


def _load_offsets(conn: psycopg.Connection, machine: str) -> Dict[str, Tuple[float, int]]:
    with conn.transaction():
        rows = conn.execute(
            "SELECT path, mtime, bytes_read FROM files WHERE machine = %s", (machine,)
        ).fetchall()
    return {path: (mtime, bytes_read) for path, mtime, bytes_read in rows}


def scan(
    projects_root: Union[str, Path],
    conn: psycopg.Connection,
    machine: str,
    full: bool = False,
    *,
    batch_lines: int = BATCH_LINES,
    progress: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Ingest new JSONL lines under `projects_root` into Postgres.

    `conn` must have `search_path` set to the Claude Lens schema and be idle.
    `full=True` ignores stored offsets and re-reads every file (idempotent,
    and it backfills columns added since a file was first scanned, such as
    `tool_use_id`). Returns counts like the SQLite scanner's `scan_dir`
    (records processed, before dedup) plus `batches`.
    """
    root = Path(projects_root)
    totals = {"messages": 0, "tools": 0, "titles": 0, "files": 0, "batches": 0}
    if not root.is_dir():
        return totals
    known = {} if full else _load_offsets(conn, machine)
    batch = _Batch()

    def flush() -> None:
        nonlocal batch
        _flush(conn, batch, machine)
        totals["batches"] += 1
        batch = _Batch()
        if progress:
            progress(dict(totals))

    for p in root.rglob("*.jsonl"):
        try:
            stat = p.stat()
        except OSError:
            continue
        key = str(p)
        row = known.get(key)
        offset = 0
        if row and row[0] == stat.st_mtime and row[1] == stat.st_size:
            continue
        if row and stat.st_size > row[1]:
            offset = row[1]
        slug = _project_slug(p, root)
        mtime = stat.st_mtime
        # Record the file even if no complete line follows (as scan_dir did).
        batch.files[key] = (mtime, offset)
        try:
            for raw, line_end in _iter_lines(p, offset):
                parsed = _parse_line(raw, slug, machine)
                if parsed is not None:
                    kind, payload = parsed
                    if kind == "title":
                        batch.titles[payload[0]] = payload[1]
                        totals["titles"] += 1
                    else:
                        batch.records.append(payload)
                        totals["messages"] += 1
                        totals["tools"] += len(payload.tools)
                batch.files[key] = (mtime, line_end)
                batch.lines += 1
                if batch.lines >= batch_lines:
                    flush()
        except OSError:
            pass  # vanished or locked mid-read: keep what was read, retry next scan
        totals["files"] += 1

    if not batch.empty():
        flush()
    return totals
