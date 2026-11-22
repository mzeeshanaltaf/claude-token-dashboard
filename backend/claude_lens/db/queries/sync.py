"""Collector run history (`sync_runs`) for the "last synced" badge and Settings."""
from __future__ import annotations

import psycopg

from .common import fetch_all

_RUN_COLS = "id, machine, started_at, finished_at, status, error, files, messages, tools, titles"


def sync_status(conn: psycopg.Connection, recent: int = 20) -> dict:
    """The last run and last successful sync per machine, plus the most recent runs."""
    latest = fetch_all(conn, f"""
      SELECT DISTINCT ON (machine) {_RUN_COLS}
        FROM sync_runs
       ORDER BY machine, started_at DESC, id DESC
    """)
    last_ok = {r["machine"]: r["last_ok_at"] for r in fetch_all(conn, """
      SELECT machine, MAX(finished_at) AS last_ok_at
        FROM sync_runs WHERE status = 'ok' GROUP BY machine
    """)}
    runs = fetch_all(conn, f"""
      SELECT {_RUN_COLS} FROM sync_runs ORDER BY started_at DESC, id DESC LIMIT %(n)s
    """, {"n": recent})
    machines = [
        {"machine": r["machine"], "last_run": r, "last_ok_at": last_ok.get(r["machine"])}
        for r in sorted(latest, key=lambda r: r["started_at"], reverse=True)
    ]
    oks = [v for v in last_ok.values() if v is not None]
    return {
        "last_synced_at": max(oks) if oks else None,
        "machines": machines,
        "runs": runs,
    }
