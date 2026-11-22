"""App settings in the `settings` key/value table (values are jsonb).

`plan` replaces the old SQLite `plan` table; `timezone` (an IANA name) drives
local-day bucketing and defaults to UTC.
"""
from __future__ import annotations

from typing import Any, Optional

import psycopg
from psycopg.types.json import Jsonb

DEFAULT_PLAN = "api"
DEFAULT_TIMEZONE = "UTC"


def get_setting(conn: psycopg.Connection, key: str) -> Optional[Any]:
    row = conn.execute("SELECT v FROM settings WHERE k = %(k)s", {"k": key}).fetchone()
    return row[0] if row else None


def set_setting(conn: psycopg.Connection, key: str, value: Any) -> None:
    conn.execute(
        "INSERT INTO settings (k, v) VALUES (%(k)s, %(v)s)"
        " ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v",
        {"k": key, "v": Jsonb(value)},
    )


def get_plan(conn: psycopg.Connection, default: str = DEFAULT_PLAN) -> str:
    v = get_setting(conn, "plan")
    return v if isinstance(v, str) and v else default


def set_plan(conn: psycopg.Connection, plan: str) -> None:
    set_setting(conn, "plan", plan)


def get_timezone(conn: psycopg.Connection, default: str = DEFAULT_TIMEZONE) -> str:
    v = get_setting(conn, "timezone")
    return v if isinstance(v, str) and v else default


def is_valid_timezone(conn: psycopg.Connection, tz: str) -> bool:
    """True when Postgres knows `tz` (checked by name, so no tzdata is needed in Python)."""
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_timezone_names WHERE name = %(tz)s)", {"tz": tz}
    ).fetchone()
    return bool(row and row[0])


def set_timezone(conn: psycopg.Connection, tz: str) -> None:
    if not is_valid_timezone(conn, tz):
        raise ValueError(f"unknown timezone: {tz!r}")
    set_setting(conn, "timezone", tz)
