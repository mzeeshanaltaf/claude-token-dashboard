"""Plain helpers shared by the DB tests (fixtures live in conftest.py)."""
import json
import os
import secrets
from pathlib import Path

import psycopg
from psycopg import sql

TEST_SCHEMA_PREFIX = "claude_lens_test_"


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


def q(conn, query, params=None):
    """Run a read query, return all rows, and end the read transaction."""
    rows = conn.execute(query, params).fetchall()
    conn.rollback()
    return rows


def q1(conn, query, params=None):
    rows = q(conn, query, params)
    return rows[0][0] if rows else None
