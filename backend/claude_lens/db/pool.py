"""Postgres connections that always point `search_path` at the Claude Lens schema.

Every table lives in one schema (`DB_SCHEMA`, default `claude_dashboard`), so
SQL elsewhere never qualifies table names. The schema name is validated as a
plain identifier by `Settings` and is still quoted with `sql.Identifier` here.
"""
from __future__ import annotations

from typing import Optional

import psycopg
from psycopg import sql
from psycopg_pool import ConnectionPool

from ..config import Settings

CONNECT_TIMEOUT = 15  # seconds; the VPS is a network hop away


def set_search_path(conn: psycopg.Connection, schema: str) -> None:
    """Point the session's `search_path` at `schema` and leave the connection idle."""
    conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
    if not conn.autocommit:
        conn.commit()


def _require_url(settings: Settings) -> str:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set (put it in .env.local at the repo root)")
    return settings.database_url


def connect(settings: Settings, *, autocommit: bool = False) -> psycopg.Connection:
    """Open a one-off connection (for the CLI) with `search_path` set."""
    conn = psycopg.connect(
        _require_url(settings), autocommit=autocommit, connect_timeout=CONNECT_TIMEOUT
    )
    try:
        set_search_path(conn, settings.db_schema)
    except BaseException:
        conn.close()
        raise
    return conn


def make_pool(
    settings: Settings,
    *,
    min_size: int = 1,
    max_size: int = 10,
    open: bool = True,
    name: Optional[str] = "claude-lens",
) -> ConnectionPool:
    """Create a connection pool whose connections all use the configured schema.

    Sessions run in UTC, so every `timestamptz` comes back as a UTC datetime
    (serialised as `...Z`). Local-day bucketing uses `AT TIME ZONE` explicitly.
    """
    schema = settings.db_schema

    def _configure(conn: psycopg.Connection) -> None:
        conn.execute("SET TIME ZONE 'UTC'")
        set_search_path(conn, schema)

    return ConnectionPool(
        conninfo=_require_url(settings),
        kwargs={"connect_timeout": CONNECT_TIMEOUT},
        min_size=min_size,
        max_size=max_size,
        configure=_configure,
        check=ConnectionPool.check_connection,
        open=open,
        name=name,
    )
