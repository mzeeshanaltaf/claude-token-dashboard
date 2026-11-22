"""Plain helpers shared by the DB tests (fixtures live in conftest.py)."""
import json
import os
import secrets
from pathlib import Path

import psycopg
from psycopg import sql

TEST_SCHEMA_PREFIX = "claude_lens_test_"
ADMIN_USER = "admin"
ADMIN_PASS = "correct-horse-battery"


def login(client, username=ADMIN_USER, password=ADMIN_PASS):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def new_test_schema_name() -> str:
    return f"{TEST_SCHEMA_PREFIX}{secrets.token_hex(4)}"


def drop_test_schema(conn: psycopg.Connection, schema: str) -> None:
    assert schema.startswith(TEST_SCHEMA_PREFIX), schema  # never drop a real schema
    conn.rollback()
    conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
    conn.commit()


def write_jsonl(path: Path, records) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def append_jsonl(path: Path, records) -> None:
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def bump_mtime(path: Path, seconds: float = 10) -> None:
    st = path.stat()
    os.utime(path, (st.st_atime + seconds, st.st_mtime + seconds))


def user_record(uuid="u1", sid="s1", ts="2026-04-10T00:00:00Z", text="hi"):
    return {
        "type": "user", "uuid": uuid, "sessionId": sid, "timestamp": ts,
        "isSidechain": False, "message": {"role": "user", "content": text},
    }


_MSG_DEFAULTS = {
    "parent_uuid": None, "project_slug": "p", "machine": "test-pc", "cwd": None,
    "type": "assistant", "is_sidechain": False, "agent_id": None, "model": None,
    "message_id": None, "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0,
    "cache_create_5m_tokens": 0, "cache_create_1h_tokens": 0, "prompt_text": None,
    "prompt_chars": None, "tool_calls_json": None,
}
_TOOL_DEFAULTS = {
    "project_slug": "p", "target": None, "tool_use_id": None, "result_tokens": None,
    "is_error": 0,
}


def _insert(conn, table, required, defaults, rows, json_cols=()):
    from psycopg.types.json import Jsonb
    cols = [*required, *defaults]
    full = []
    for r in rows:
        row = {**defaults, **r}
        for c in json_cols:
            if row[c] is not None:
                row[c] = Jsonb(row[c])
        full.append(row)
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(c) for c in cols),
        sql.SQL(", ").join(sql.Placeholder(c) for c in cols),
    )
    with conn.cursor() as cur:
        cur.executemany(query, full)
    conn.commit()


def insert_messages(conn, rows) -> None:
    """Insert message rows (dicts with uuid, session_id, timestamp + any overrides)."""
    _insert(conn, "messages", ("uuid", "session_id", "timestamp"), _MSG_DEFAULTS, rows,
            json_cols=("tool_calls_json",))


def insert_tools(conn, rows) -> None:
    """Insert tool_calls rows (dicts with message_uuid, session_id, tool_name, timestamp)."""
    _insert(conn, "tool_calls", ("message_uuid", "session_id", "tool_name", "timestamp"),
            _TOOL_DEFAULTS, rows)


def q(conn, query, params=None):
    """Run a read query, return all rows, and end the read transaction."""
    rows = conn.execute(query, params).fetchall()
    conn.rollback()
    return rows


def q1(conn, query, params=None):
    rows = q(conn, query, params)
    return rows[0][0] if rows else None
