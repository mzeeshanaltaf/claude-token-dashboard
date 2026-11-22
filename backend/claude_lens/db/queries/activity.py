"""Activity page: local-day windows, the hour x weekday grid, the top project.

Per-day rows come from `analytics.daily_token_breakdown` + `daily_model_tokens`
(the same rollup as `/api/daily`); this module adds what they don't cover.
Every bucket is in the `timezone` setting, passed in as `tz`.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import psycopg

from .analytics import _TOKEN_SUMS, _filters
from .common import fetch_all, fetch_one


def local_window(conn: psycopg.Connection, tz: str, days: int) -> dict:
    """{today, start_day, since}: the last `days` local dates ending today in `tz`.

    `since` is local midnight of `start_day` as a timestamptz, so it can go
    straight into a range clause.
    """
    return fetch_one(conn, """
      WITH t AS (SELECT (now() AT TIME ZONE %(tz)s)::date AS today)
      SELECT t.today,
             t.today - (%(days)s::int - 1) AS start_day,
             ((t.today - (%(days)s::int - 1))::timestamp AT TIME ZONE %(tz)s) AS since
        FROM t
    """, {"tz": tz, "days": days})


def local_date(conn: psycopg.Connection, ts: datetime, tz: str) -> date:
    """The local date (in `tz`) of an instant."""
    row = fetch_one(conn, "SELECT (%(ts)s::timestamptz AT TIME ZONE %(tz)s)::date AS d",
                    {"ts": ts, "tz": tz})
    return row["d"]


def today(conn: psycopg.Connection, tz: str) -> date:
    return fetch_one(conn, "SELECT (now() AT TIME ZONE %(tz)s)::date AS d", {"tz": tz})["d"]


def hourly_model_rows(conn: psycopg.Connection, since: Optional[datetime] = None,
                      until: Optional[datetime] = None, tz: str = "UTC") -> list[dict]:
    """Per (ISO weekday 1-7, local hour 0-23, model): turns and token sums.

    `turns` counts `type = 'user'` records, the same definition as the overview
    and `/api/daily`. The caller prices the token sums per model.
    """
    rng, params = _filters(since, until, None)
    params["tz"] = tz
    return fetch_all(conn, f"""
      SELECT EXTRACT(ISODOW FROM m.timestamp AT TIME ZONE %(tz)s)::int AS dow,
             EXTRACT(HOUR FROM m.timestamp AT TIME ZONE %(tz)s)::int AS hour,
             COALESCE(m.model, 'unknown') AS model,
             COUNT(*) FILTER (WHERE m.type = 'user') AS turns,
             {_TOKEN_SUMS}
        FROM messages m
       WHERE TRUE {rng}
       GROUP BY 1, 2, 3
    """, params)


def top_project(conn: psycopg.Connection, since: Optional[datetime] = None,
                until: Optional[datetime] = None) -> Optional[dict]:
    """The project with the most turns in range (ties: more sessions, then slug)."""
    rng, params = _filters(since, until, None)
    return fetch_one(conn, f"""
      SELECT m.project_slug,
             COUNT(*) FILTER (WHERE m.type = 'user') AS turns,
             COUNT(DISTINCT m.session_id) AS sessions
        FROM messages m
       WHERE TRUE {rng}
       GROUP BY m.project_slug
       ORDER BY 2 DESC, 3 DESC, 1
       LIMIT 1
    """, params)
