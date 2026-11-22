"""`/api/tools/insights`: per-tool calls, results and errors; top files, commands, domains.

A tool's result tokens and errors live on its `_tool_result` row, which is
linked to the tool_use by `tool_use_id`. Rows migrated from the old SQLite DB
have no `tool_use_id`, so only "linked" calls count toward result tokens and
the error rate; the response carries the linked count so the UI can say so.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import psycopg

from .common import fetch_all, range_clause

FILE_TOOLS = ("Read", "Edit", "Write")
SHELL_TOOLS = ("Bash", "PowerShell")
TOP_N = 20


def per_tool(conn: psycopg.Connection, since: Optional[datetime] = None,
             until: Optional[datetime] = None) -> list[dict]:
    rng, params = range_clause(since, until, col="u.timestamp")
    return fetch_all(conn, f"""
      SELECT u.tool_name,
             COUNT(*) AS calls,
             COUNT(r.tool_use_id) AS linked,
             COUNT(*) FILTER (WHERE r.is_error = 1) AS errors,
             COALESCE(SUM(r.result_tokens), 0)::bigint AS result_tokens
        FROM tool_calls u
        LEFT JOIN (
          SELECT tool_use_id, MAX(is_error) AS is_error, SUM(result_tokens) AS result_tokens
            FROM tool_calls
           WHERE tool_name = '_tool_result' AND tool_use_id IS NOT NULL
           GROUP BY tool_use_id
        ) r ON r.tool_use_id = u.tool_use_id
       WHERE u.tool_name <> '_tool_result' {rng}
       GROUP BY u.tool_name
       ORDER BY calls DESC, u.tool_name
    """, params)


def top_files(conn: psycopg.Connection, since: Optional[datetime] = None,
              until: Optional[datetime] = None, limit: int = TOP_N) -> list[dict]:
    rng, params = range_clause(since, until, col="tc.timestamp")
    params.update(tools=list(FILE_TOOLS), limit=limit)
    return fetch_all(conn, f"""
      SELECT tc.target AS path,
             COUNT(*) FILTER (WHERE tc.tool_name = 'Read')  AS read,
             COUNT(*) FILTER (WHERE tc.tool_name = 'Edit')  AS edit,
             COUNT(*) FILTER (WHERE tc.tool_name = 'Write') AS write,
             COUNT(*) AS total,
             COUNT(DISTINCT tc.session_id) AS sessions,
             MAX(tc.timestamp) AS last_used
        FROM tool_calls tc
       WHERE tc.tool_name = ANY(%(tools)s) AND tc.target IS NOT NULL AND tc.target <> '' {rng}
       GROUP BY tc.target
       ORDER BY total DESC, path
       LIMIT %(limit)s
    """, params)


def top_commands(conn: psycopg.Connection, since: Optional[datetime] = None,
                 until: Optional[datetime] = None, limit: int = TOP_N) -> list[dict]:
    """Exact command strings (the collector keeps the first 500 characters)."""
    rng, params = range_clause(since, until, col="tc.timestamp")
    params.update(tools=list(SHELL_TOOLS), limit=limit)
    return fetch_all(conn, f"""
      SELECT tc.target AS command,
             MIN(tc.tool_name) AS tool_name,
             COUNT(*) AS calls,
             COUNT(DISTINCT tc.session_id) AS sessions,
             MAX(tc.timestamp) AS last_used
        FROM tool_calls tc
       WHERE tc.tool_name = ANY(%(tools)s) AND tc.target IS NOT NULL AND tc.target <> '' {rng}
       GROUP BY tc.target
       ORDER BY calls DESC, command
       LIMIT %(limit)s
    """, params)


def top_domains(conn: psycopg.Connection, since: Optional[datetime] = None,
                until: Optional[datetime] = None, limit: int = TOP_N) -> list[dict]:
    """WebFetch hosts (lower-cased, without `www.`), from the stored URL."""
    rng, params = range_clause(since, until, col="tc.timestamp")
    params["limit"] = limit
    return fetch_all(conn, f"""
      SELECT d.domain, COUNT(*) AS calls, MAX(d.timestamp) AS last_used
        FROM (
          SELECT regexp_replace(
                   lower(substring(tc.target FROM '^[A-Za-z][A-Za-z0-9+.-]*://([^/?#:@]+)')),
                   '^www[.]', '') AS domain,
                 tc.timestamp
            FROM tool_calls tc
           WHERE tc.tool_name = 'WebFetch' AND tc.target IS NOT NULL {rng}
        ) d
       WHERE d.domain IS NOT NULL
       GROUP BY d.domain
       ORDER BY calls DESC, d.domain
       LIMIT %(limit)s
    """, params)
