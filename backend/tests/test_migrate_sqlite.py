"""`claude-lens migrate-sqlite`: SQLite -> Postgres copy and parity check."""
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from claude_lens.cli import main
from claude_lens.collector import migrate_sqlite as m
from claude_lens.collector.ingest import scan
from helpers import q, q1, user_record, write_jsonl

# The old app's schema (token_dashboard/db.py), inlined so these tests outlive it.
OLD_SCHEMA = """
CREATE TABLE files (path TEXT PRIMARY KEY, mtime REAL NOT NULL, bytes_read INTEGER NOT NULL,
                    scanned_at REAL NOT NULL);
CREATE TABLE messages (
  uuid TEXT PRIMARY KEY, parent_uuid TEXT, session_id TEXT NOT NULL, project_slug TEXT NOT NULL,
  cwd TEXT, git_branch TEXT, cc_version TEXT, entrypoint TEXT, type TEXT NOT NULL,
  is_sidechain INTEGER NOT NULL DEFAULT 0, agent_id TEXT, timestamp TEXT NOT NULL, model TEXT,
  stop_reason TEXT, prompt_id TEXT, message_id TEXT,
  input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
  cache_read_tokens INTEGER NOT NULL DEFAULT 0, cache_create_5m_tokens INTEGER NOT NULL DEFAULT 0,
  cache_create_1h_tokens INTEGER NOT NULL DEFAULT 0, prompt_text TEXT, prompt_chars INTEGER,
  tool_calls_json TEXT);
CREATE TABLE tool_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT, message_uuid TEXT NOT NULL, session_id TEXT NOT NULL,
  project_slug TEXT NOT NULL, tool_name TEXT NOT NULL, target TEXT, result_tokens INTEGER,
  is_error INTEGER NOT NULL DEFAULT 0, timestamp TEXT NOT NULL);
CREATE TABLE session_titles (session_id TEXT PRIMARY KEY, title TEXT NOT NULL);
CREATE TABLE plan (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE dismissed_tips (tip_key TEXT PRIMARY KEY, dismissed_at REAL NOT NULL);
"""

MACHINE = "old-pc"
MSG_COLS = ("uuid", "parent_uuid", "session_id", "project_slug", "cwd", "git_branch",
            "cc_version", "entrypoint", "type", "is_sidechain", "agent_id", "timestamp", "model",
            "stop_reason", "prompt_id", "message_id", "input_tokens", "output_tokens",
            "cache_read_tokens", "cache_create_5m_tokens", "cache_create_1h_tokens",
            "prompt_text", "prompt_chars", "tool_calls_json")


def _msg(uuid, sid="s1", *, type="assistant", model="claude-opus-5-5", ts="2026-03-01T10:00:00.123Z",
         side=0, tokens=(10, 20, 30, 40, 50), text=None, tools=None, mid=None):
    return {
        "uuid": uuid, "parent_uuid": None, "session_id": sid, "project_slug": "C--work-a",
        "cwd": "C:\\work\\a", "git_branch": "main", "cc_version": "2.1.0", "entrypoint": "cli",
        "type": type, "is_sidechain": side, "agent_id": "ag1" if side else None,
        "timestamp": ts, "model": model if type == "assistant" else None,
        "stop_reason": None, "prompt_id": None, "message_id": mid,
        "input_tokens": tokens[0], "output_tokens": tokens[1], "cache_read_tokens": tokens[2],
        "cache_create_5m_tokens": tokens[3], "cache_create_1h_tokens": tokens[4],
        "prompt_text": text, "prompt_chars": len(text) if text else None,
        "tool_calls_json": json.dumps(tools) if tools is not None else None,
    }


def make_old_db(path: Path, *, files=(), n_extra=0) -> Path:
    c = sqlite3.connect(path)
    c.executescript(OLD_SCHEMA)
    msgs = [
        _msg("u1", type="user", tokens=(0, 0, 0, 0, 0), text="fix the bug ✓"),
        _msg("a1", mid="msg_1", tools=[{"name": "Read", "target": "x.py"}]),
        _msg("a2", sid="s2", model="claude-sonnet-5-5", side=1, ts="2026-04-02T00:00:00+00:00",
             mid="msg_2", tokens=(1, 2, 3, 4, 5)),
        _msg("a3", sid="s2", model=None, mid="msg_3", tokens=(7, 0, 0, 0, 0)),
    ]
    msgs += [_msg(f"x{i}", sid=f"s{3 + i % 3}", mid=f"msg_x{i}", tokens=(i, i, i, i, i))
             for i in range(n_extra)]
    c.executemany(
        f"INSERT INTO messages ({', '.join(MSG_COLS)}) VALUES ({', '.join('?' * len(MSG_COLS))})",
        [tuple(r[k] for k in MSG_COLS) for r in msgs],
    )
    c.executemany(
        "INSERT INTO tool_calls (message_uuid, session_id, project_slug, tool_name, target,"
        " result_tokens, is_error, timestamp) VALUES (?,?,?,?,?,?,?,?)",
        [("a1", "s1", "C--work-a", "Read", "x.py", None, 0, "2026-03-01T10:00:00.123Z"),
         ("a1", "s1", "C--work-a", "_tool_result", "toolu_1", 123, 1, "2026-03-01T10:00:01Z"),
         ("a2", "s2", "C--work-a", "Bash", "ls", None, 0, "2026-04-02T00:00:00+00:00")],
    )
    c.executemany("INSERT INTO session_titles VALUES (?, ?)", [("s1", "Fix the bug"), ("s2", "Two")])
    c.execute("INSERT INTO plan VALUES ('plan', 'max-5x')")
    c.execute("INSERT INTO dismissed_tips VALUES ('repeat-file:C:\\x.py', 1776758163.7403712)")
    files = list(files) or [("C:\\p\\C--work-a\\s1.jsonl", 1795189647.9953735, 4096,
                             1795248002.8317854)]
    c.executemany("INSERT INTO files VALUES (?, ?, ?, ?)", files)
    c.commit()
    c.close()
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def old_db(tmp_path):
    return make_old_db(tmp_path / "token-dashboard.db")


def test_copies_every_table_with_conversions(db, old_db):
    copied, checks = m.run(old_db, db, MACHINE)
    assert copied == {"messages": 4, "tool_calls": 3, "files": 1, "session_titles": 2,
                      "dismissed_tips": 1, "settings": 1}
    assert all(c.ok for c in checks), m.format_checks(checks)

    row = q(db, "SELECT machine, type, is_sidechain, timestamp, prompt_text, prompt_chars,"
                " tool_calls_json FROM messages WHERE uuid = 'u1'")[0]
    assert row == (MACHINE, "user", False,
                   datetime(2026, 3, 1, 10, 0, 0, 123000, tzinfo=timezone.utc),
                   "fix the bug ✓", 13, None)
    assert q(db, "SELECT is_sidechain, agent_id FROM messages WHERE uuid = 'a2'") == [(True, "ag1")]
    # tool_calls_json is real jsonb, not a string
    assert q1(db, "SELECT tool_calls_json -> 0 ->> 'name' FROM messages WHERE uuid = 'a1'") == "Read"
    # prompt_tsv is generated from the copied text
    assert q1(db, "SELECT count(*) FROM messages WHERE prompt_tsv @@ to_tsquery('english', 'bug')") == 1

    tools = q(db, "SELECT id, message_uuid, tool_name, target, tool_use_id, result_tokens, is_error"
                  " FROM tool_calls ORDER BY id")
    assert tools == [(1, "a1", "Read", "x.py", None, None, 0),
                     (2, "a1", "_tool_result", "toolu_1", None, 123, 1),
                     (3, "a2", "Bash", "ls", None, None, 0)]

    assert q(db, "SELECT machine, path, mtime, bytes_read, scanned_at FROM files") == [
        (MACHINE, "C:\\p\\C--work-a\\s1.jsonl", 1795189647.9953735, 4096,
         datetime.fromtimestamp(1795248002.8317854, tz=timezone.utc))]
    assert q(db, "SELECT session_id, title FROM session_titles ORDER BY 1") == [
        ("s1", "Fix the bug"), ("s2", "Two")]
    assert q(db, "SELECT v FROM settings WHERE k = 'plan'") == [("max-5x",)]
    assert q1(db, "SELECT jsonb_typeof(v) FROM settings WHERE k = 'plan'") == "string"
    assert q(db, "SELECT tip_key, dismissed_at FROM dismissed_tips") == [
        ("repeat-file:C:\\x.py", datetime.fromtimestamp(1776758163.7403712, tz=timezone.utc))]


def test_sqlite_file_is_untouched(db, old_db):
    before = (_sha(old_db), old_db.stat().st_mtime_ns)
    m.run(old_db, db, MACHINE)
    assert (_sha(old_db), old_db.stat().st_mtime_ns) == before
    assert not Path(str(old_db) + "-journal").exists()


def test_readonly_connection_cannot_write(old_db):
    src = m.open_sqlite_readonly(old_db)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            src.execute("DELETE FROM messages")
    finally:
        src.close()


def test_chunks_and_per_model_parity(db, tmp_path):
    path = make_old_db(tmp_path / "big.db", n_extra=25)
    copied, checks = m.run(path, db, MACHINE, chunk=7)
    assert copied["messages"] == 29
    assert all(c.ok for c in checks), m.format_checks(checks)
    names = {c.metric for c in checks}
    assert {"messages", "tool_calls", "files", "distinct sessions", "sum(output_tokens)",
            "model claude-opus-5-5: rows+5 sums", "model claude-sonnet-5-5: rows+5 sums",
            "model (none): rows+5 sums"} <= names
    by_name = {c.metric: c for c in checks}
    assert by_name["distinct sessions"].postgres == 5
    assert by_name["sum(input_tokens)"].postgres == 10 + 1 + 7 + sum(range(25))


def test_refuses_when_postgres_has_data_unless_forced(db, old_db):
    m.run(old_db, db, MACHINE)
    with pytest.raises(m.MigrationError, match="already has data.*--force"):
        m.run(old_db, db, MACHINE)
    db.execute("INSERT INTO messages (uuid, session_id, project_slug, machine, type, timestamp)"
               " VALUES ('stray', 'sX', 'p', 'm', 'user', now())")
    db.execute("INSERT INTO settings (k, v) VALUES ('timezone', '\"UTC\"')")
    db.commit()
    copied, checks = m.run(old_db, db, MACHINE, force=True)
    assert copied["messages"] == 4 and all(c.ok for c in checks)
    assert q1(db, "SELECT count(*) FROM messages WHERE uuid = 'stray'") == 0
    assert q1(db, "SELECT min(id) FROM tool_calls") == 1  # identities restarted


def test_refuses_when_only_files_are_present(db, old_db):
    db.execute("INSERT INTO files VALUES ('m', 'p', 1.0, 1, now())")
    db.commit()
    with pytest.raises(m.MigrationError, match=r"already has data \(files\)"):
        m.run(old_db, db, MACHINE)


def test_parity_reports_mismatches(db, old_db):
    m.run(old_db, db, MACHINE)
    db.execute("UPDATE messages SET output_tokens = output_tokens + 1 WHERE uuid = 'a2'")
    db.execute("UPDATE files SET bytes_read = 1")
    db.commit()
    _, checks = m.run(old_db, db, MACHINE, check_only=True)
    bad = {c.metric for c in checks if not c.ok}
    assert bad == {"sum(output_tokens)", "model claude-sonnet-5-5: rows+5 sums",
                   "files (path, mtime, bytes_read) identical"}
    assert "MISMATCH" in m.format_checks(checks)


def test_rejects_a_non_dashboard_database(db, tmp_path):
    other = tmp_path / "other.db"
    sqlite3.connect(other).execute("CREATE TABLE t (x)").connection.close()
    with pytest.raises(m.MigrationError, match="not a Token Dashboard database"):
        m.run(other, db, MACHINE)
    with pytest.raises(m.MigrationError, match="not found"):
        m.run(tmp_path / "missing.db", db, MACHINE)


def test_migrated_offsets_make_the_next_scan_incremental(db, tmp_path, projects):
    """The point of copying `files` verbatim: a scan after the migration skips unchanged files."""
    root, proj = projects
    unchanged = proj / "s1.jsonl"
    write_jsonl(unchanged, [user_record("u-on-disk", "s1")])
    grown = proj / "s2.jsonl"
    write_jsonl(grown, [user_record("u-old", "s2", text="old")])
    old_size = grown.stat().st_size
    files = [(str(p), p.stat().st_mtime, p.stat().st_size, 1.0) for p in (unchanged, grown)]
    old = make_old_db(tmp_path / "old.db", files=files)
    m.run(old, db, MACHINE)

    with open(grown, "a", encoding="utf-8") as f:
        f.write(json.dumps(user_record("u-new", "s2", ts="2026-04-11T00:00:00Z")) + "\n")
    st = grown.stat()
    os.utime(grown, (st.st_atime, st.st_mtime + 5))

    totals = scan(root, db, MACHINE)
    assert totals["files"] == 1 and totals["messages"] == 1  # only the appended line
    # Neither on-disk record of the skipped/resumed bytes was re-read.
    assert q1(db, "SELECT count(*) FROM messages WHERE uuid IN ('u-on-disk', 'u-old')") == 0
    assert q1(db, "SELECT count(*) FROM messages WHERE uuid = 'u-new'") == 1
    assert q1(db, "SELECT bytes_read FROM files WHERE path = %s", (str(grown),)) > old_size


# --- CLI ------------------------------------------------------------------------

@pytest.fixture
def cli_db(db, pg_url, pg_schema, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("DB_SCHEMA", pg_schema)
    monkeypatch.setenv("CLAUDE_LENS_MACHINE", "cli-pc")
    return db


def test_cli_migrates_and_prints_parity(cli_db, old_db, capsys):
    assert main(["migrate-sqlite", "--sqlite", str(old_db)]) == 0
    out = capsys.readouterr().out
    assert "parity ok" in out and "MISMATCH" not in out
    assert "copied 4 messages, 3 tool_calls" in out
    assert q(cli_db, "SELECT DISTINCT machine FROM messages") == [("cli-pc",)]

    assert main(["migrate-sqlite", "--sqlite", str(old_db), "--check-only"]) == 0
    assert "parity ok" in capsys.readouterr().out

    assert main(["migrate-sqlite", "--sqlite", str(old_db)]) == 2
    assert "--force" in capsys.readouterr().err

    assert main(["migrate-sqlite", "--sqlite", str(old_db), "--force", "--machine", "pc2"]) == 0
    assert q(cli_db, "SELECT DISTINCT machine FROM messages") == [("pc2",)]


def test_cli_exits_nonzero_on_mismatch(cli_db, old_db, capsys):
    assert main(["migrate-sqlite", "--sqlite", str(old_db)]) == 0
    cli_db.execute("DELETE FROM session_titles WHERE session_id = 's2'")
    cli_db.commit()
    capsys.readouterr()
    assert main(["migrate-sqlite", "--sqlite", str(old_db), "--check-only"]) == 1
    captured = capsys.readouterr()
    assert "MISMATCH" in captured.out and "parity FAILED: 1 of" in captured.err


def test_cli_missing_sqlite_file(cli_db, tmp_path, capsys):
    assert main(["migrate-sqlite", "--sqlite", str(tmp_path / "nope.db")]) == 2
    assert "not found" in capsys.readouterr().err
