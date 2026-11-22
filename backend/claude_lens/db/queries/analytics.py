"""Dashboard-wide aggregates: overview, daily, by-model, tools, skills.

Ported from `token_dashboard/db.py`. `SUM(bigint)` is `numeric` in Postgres,
so sums are cast back to `bigint` to come out as Python ints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import psycopg

from .common import fetch_all, fetch_one, range_clause

_TOKEN_SUMS = """
       COALESCE(SUM(m.input_tokens), 0)::bigint            AS input_tokens,
       COALESCE(SUM(m.output_tokens), 0)::bigint           AS output_tokens,
       COALESCE(SUM(m.cache_read_tokens), 0)::bigint       AS cache_read_tokens,
       COALESCE(SUM(m.cache_create_5m_tokens), 0)::bigint  AS cache_create_5m_tokens,
       COALESCE(SUM(m.cache_create_1h_tokens), 0)::bigint  AS cache_create_1h_tokens"""


def overview_totals(conn: psycopg.Connection, since: Optional[datetime] = None,
                    until: Optional[datetime] = None) -> dict:
    rng, params = range_clause(since, until)
    return fetch_one(conn, f"""
      SELECT COUNT(DISTINCT m.session_id)   AS sessions,
             COUNT(DISTINCT m.project_slug) AS projects,
             COUNT(*) FILTER (WHERE m.type = 'user') AS turns,
             {_TOKEN_SUMS}
        FROM messages m
       WHERE TRUE {rng}
    """, params)


def model_breakdown(conn: psycopg.Connection, since: Optional[datetime] = None,
                    until: Optional[datetime] = None) -> list[dict]:
    """Per-model token totals + assistant turn count. The caller prices them."""
    rng, params = range_clause(since, until)
    return fetch_all(conn, f"""
      SELECT COALESCE(m.model, 'unknown') AS model,
             COUNT(*) AS turns,
             {_TOKEN_SUMS}
        FROM messages m
       WHERE m.type = 'assistant' {rng}
       GROUP BY COALESCE(m.model, 'unknown')
       ORDER BY SUM(m.input_tokens + m.output_tokens
                    + m.cache_create_5m_tokens + m.cache_create_1h_tokens) DESC,
                1
    """, params)


def daily_token_breakdown(conn: psycopg.Connection, since: Optional[datetime] = None,
                          until: Optional[datetime] = None, tz: str = "UTC") -> list[dict]:
    """One row per local day (in `tz`): stacked-bar data."""
    rng, params = range_clause(since, until)
    params["tz"] = tz
    return fetch_all(conn, f"""
      SELECT (m.timestamp AT TIME ZONE %(tz)s)::date AS day,
             COALESCE(SUM(m.input_tokens), 0)::bigint      AS input_tokens,
             COALESCE(SUM(m.output_tokens), 0)::bigint     AS output_tokens,
             COALESCE(SUM(m.cache_read_tokens), 0)::bigint AS cache_read_tokens,
             (COALESCE(SUM(m.cache_create_5m_tokens), 0)
              + COALESCE(SUM(m.cache_create_1h_tokens), 0))::bigint AS cache_create_tokens
        FROM messages m
       WHERE TRUE {rng}
       GROUP BY 1
       ORDER BY 1
    """, params)


def tool_token_breakdown(conn: psycopg.Connection, since: Optional[datetime] = None,
                         until: Optional[datetime] = None) -> list[dict]:
    rng, params = range_clause(since, until, col="tc.timestamp")
    return fetch_all(conn, f"""
      SELECT tc.tool_name,
             COUNT(*) AS calls,
             COALESCE(SUM(tc.result_tokens), 0)::bigint AS result_tokens
        FROM tool_calls tc
       WHERE tc.tool_name <> '_tool_result' {rng}
       GROUP BY tc.tool_name
       ORDER BY calls DESC, tc.tool_name
    """, params)


def skill_breakdown(conn: psycopg.Connection, since: Optional[datetime] = None,
                    until: Optional[datetime] = None) -> list[dict]:
    """Per-skill invocations, distinct sessions, last use, and SKILL.md tokens.

    `tokens_per_call` comes from `skill_catalog` (uploaded by the collector; the
    most recently updated machine wins when several have the same slug). It is
    NULL for skills outside the scanned roots. Token attribution from
    `result_tokens` isn't used: a Skill's content arrives in a system-reminder,
    not in the tool_result body (see the old `db.skill_breakdown` docstring).
    """
    rng, params = range_clause(since, until, col="tc.timestamp")
    return fetch_all(conn, f"""
      WITH catalog AS (
        SELECT DISTINCT ON (slug) slug, tokens
          FROM skill_catalog
         ORDER BY slug, updated_at DESC, machine
      )
      SELECT s.skill, s.invocations, s.sessions, s.last_used, c.tokens AS tokens_per_call
        FROM (
          SELECT tc.target AS skill,
                 COUNT(*) AS invocations,
                 COUNT(DISTINCT tc.session_id) AS sessions,
                 MAX(tc.timestamp) AS last_used
            FROM tool_calls tc
           WHERE tc.tool_name = 'Skill' AND tc.target IS NOT NULL AND tc.target <> '' {rng}
           GROUP BY tc.target
        ) s
        LEFT JOIN catalog c ON c.slug = s.skill
       ORDER BY s.invocations DESC, s.skill
    """, params)
