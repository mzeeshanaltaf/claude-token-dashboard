"""Per-project aggregates. Ported from `token_dashboard/db.py`."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import psycopg

from .common import fetch_all, project_names, range_clause


def project_summary(conn: psycopg.Connection, since: Optional[datetime] = None,
                    until: Optional[datetime] = None) -> list[dict]:
    rng, params = range_clause(since, until)
    rows = fetch_all(conn, f"""
      SELECT m.project_slug,
             COUNT(DISTINCT m.session_id) AS sessions,
             COUNT(*) FILTER (WHERE m.type = 'user') AS turns,
             COALESCE(SUM(m.input_tokens), 0)::bigint  AS input_tokens,
             COALESCE(SUM(m.output_tokens), 0)::bigint AS output_tokens,
             (SUM(m.input_tokens) + SUM(m.output_tokens)
              + SUM(m.cache_create_5m_tokens) + SUM(m.cache_create_1h_tokens))::bigint AS core_tokens,
             COALESCE(SUM(m.cache_read_tokens), 0)::bigint      AS cache_read_tokens,
             COALESCE(SUM(m.cache_create_5m_tokens), 0)::bigint AS cache_create_5m_tokens,
             COALESCE(SUM(m.cache_create_1h_tokens), 0)::bigint AS cache_create_1h_tokens,
             (COALESCE(SUM(m.cache_create_5m_tokens), 0)
              + COALESCE(SUM(m.cache_create_1h_tokens), 0))::bigint AS cache_write_tokens,
             (COALESCE(SUM(m.input_tokens), 0) + COALESCE(SUM(m.output_tokens), 0)
              + COALESCE(SUM(m.cache_read_tokens), 0)
              + COALESCE(SUM(m.cache_create_5m_tokens), 0)
              + COALESCE(SUM(m.cache_create_1h_tokens), 0))::bigint AS total_tokens,
             MAX(m.timestamp) AS last_active
        FROM messages m
       WHERE TRUE {rng}
       GROUP BY m.project_slug
       ORDER BY core_tokens DESC, m.project_slug
    """, params)
    names = project_names(conn, (r["project_slug"] for r in rows))
    for r in rows:
        r["project_name"] = names.get(r["project_slug"], r["project_slug"])
    return rows


def project_model_tokens(conn: psycopg.Connection, since: Optional[datetime] = None,
                         until: Optional[datetime] = None) -> list[dict]:
    """Per (project_slug, model) assistant-token sums; the caller prices them."""
    rng, params = range_clause(since, until)
    return fetch_all(conn, f"""
      SELECT m.project_slug, COALESCE(m.model, 'unknown') AS model,
             COALESCE(SUM(m.input_tokens), 0)::bigint            AS input_tokens,
             COALESCE(SUM(m.output_tokens), 0)::bigint           AS output_tokens,
             COALESCE(SUM(m.cache_read_tokens), 0)::bigint       AS cache_read_tokens,
             COALESCE(SUM(m.cache_create_5m_tokens), 0)::bigint  AS cache_create_5m_tokens,
             COALESCE(SUM(m.cache_create_1h_tokens), 0)::bigint  AS cache_create_1h_tokens
        FROM messages m
       WHERE m.type = 'assistant' {rng}
       GROUP BY m.project_slug, COALESCE(m.model, 'unknown')
    """, params)


def project_sessions(conn: psycopg.Connection, slug: str, since: Optional[datetime] = None,
                     until: Optional[datetime] = None) -> list[dict]:
    rng, params = range_clause(since, until)
    params["slug"] = slug
    rows = fetch_all(conn, f"""
      SELECT a.*, t.title
        FROM (
          SELECT m.session_id, MIN(m.project_slug) AS project_slug,
                 MIN(m.timestamp) AS started, MAX(m.timestamp) AS ended,
                 COUNT(*) FILTER (WHERE m.type = 'user') AS turns,
                 (SUM(m.input_tokens) + SUM(m.output_tokens))::bigint AS tokens
            FROM messages m
           WHERE m.project_slug = %(slug)s {rng}
           GROUP BY m.session_id
        ) a
        LEFT JOIN session_titles t ON t.session_id = a.session_id
       ORDER BY a.ended DESC, a.session_id
    """, params)
    if rows:
        name = project_names(conn, [slug]).get(slug, slug)
        for r in rows:
            r["project_name"] = name
    return rows
