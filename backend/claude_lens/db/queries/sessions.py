"""Sessions: the paginated list, one session's turns, and per-model sums.

Ported from `token_dashboard/db.py` (`recent_sessions`, `session_turns`,
`session_model_tokens`). The list is now server-side paginated, sorted from a
whitelist, and filterable by text (title / session id), project and model.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

import psycopg

from ...core.costs import RATES_CTE, cost_sql, rate_joins, rates_param
from .common import (
    PageRequest, envelope, fetch_all, like_pattern, order_by, page_total,
    project_names, range_clause,
)

# sort key -> (SQL expression over the `s` subquery, default direction)
SESSION_SORTS = {
    "ended":              ("s.ended", "desc"),
    "started":            ("s.started", "desc"),
    "turns":              ("s.turns", "desc"),
    "tokens":             ("s.tokens", "desc"),
    "input_tokens":       ("s.input_tokens", "desc"),
    "output_tokens":      ("s.output_tokens", "desc"),
    "cache_read_tokens":  ("s.cache_read_tokens", "desc"),
    "cache_write_tokens": ("s.cache_write_tokens", "desc"),
    "total_tokens":       ("s.total_tokens", "desc"),
    "cost":               ("s.cost", "desc"),
    "title":              ("t.title", "asc"),
}
DEFAULT_SESSION_SORT = "ended"


def sessions_page(
    conn: psycopg.Connection,
    req: PageRequest,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    q: Optional[str] = None,
    project: Optional[str] = None,
    model: Optional[str] = None,
    pricing: Optional[dict] = None,
) -> dict:
    """{items, total, page, page_size}. Token sums cover only messages in range.

    `pricing` is needed only for `sort=cost`; the caller adds the displayed
    `estimated_cost_usd` (and `project_name`) to the items.
    """
    order = order_by(SESSION_SORTS, DEFAULT_SESSION_SORT, req, "s.session_id")
    by_cost = (req.sort or DEFAULT_SESSION_SORT) == "cost"
    if by_cost and pricing is None:
        raise ValueError("sort=cost needs pricing")

    rng, params = range_clause(since, until)
    inner_where = rng
    if project:
        inner_where += " AND m.project_slug = %(project)s"
        params["project"] = project
    having = ""
    if model:
        having = " HAVING bool_or(m.model = %(model)s)"
        params["model"] = model
    outer_where = ""
    if q:
        outer_where = " AND (t.title ILIKE %(q)s OR s.session_id ILIKE %(q)s)"
        params["q"] = like_pattern(q)

    with_cte, joins, cost_col = "", "", "NULL::float8 AS cost"
    if by_cost:
        with_cte = f"WITH {RATES_CTE}"
        joins = rate_joins("m")
        cost_col = f"SUM({cost_sql('m')}) FILTER (WHERE m.type = 'assistant') AS cost"
        params["rates"] = rates_param(pricing)

    inner = f"""
          SELECT m.session_id, MIN(m.project_slug) AS project_slug,
                 MIN(m.timestamp) AS started, MAX(m.timestamp) AS ended,
                 COUNT(*) FILTER (WHERE m.type = 'user') AS turns,
                 (SUM(m.input_tokens) + SUM(m.output_tokens))::bigint AS tokens,
                 COALESCE(SUM(m.input_tokens), 0)::bigint  AS input_tokens,
                 COALESCE(SUM(m.output_tokens), 0)::bigint AS output_tokens,
                 COALESCE(SUM(m.cache_read_tokens), 0)::bigint AS cache_read_tokens,
                 COALESCE(SUM(m.cache_create_5m_tokens), 0)::bigint AS cache_create_5m_tokens,
                 COALESCE(SUM(m.cache_create_1h_tokens), 0)::bigint AS cache_create_1h_tokens,
                 (COALESCE(SUM(m.cache_create_5m_tokens), 0)
                  + COALESCE(SUM(m.cache_create_1h_tokens), 0))::bigint AS cache_write_tokens,
                 (COALESCE(SUM(m.input_tokens), 0) + COALESCE(SUM(m.output_tokens), 0)
                  + COALESCE(SUM(m.cache_read_tokens), 0)
                  + COALESCE(SUM(m.cache_create_5m_tokens), 0)
                  + COALESCE(SUM(m.cache_create_1h_tokens), 0))::bigint AS total_tokens,
                 {cost_col}
            FROM messages m {joins}
           WHERE TRUE {inner_where}
           GROUP BY m.session_id {having}"""

    params.update(limit=req.page_size, offset=req.offset)
    rows = fetch_all(conn, f"""
      {with_cte}
      SELECT s.session_id, s.project_slug, s.started, s.ended, s.turns, s.tokens,
             s.input_tokens, s.output_tokens, s.cache_read_tokens,
             s.cache_create_5m_tokens, s.cache_create_1h_tokens, s.cache_write_tokens,
             s.total_tokens, t.title, COUNT(*) OVER () AS total
        FROM ({inner}) s
        LEFT JOIN session_titles t ON t.session_id = s.session_id
       WHERE TRUE {outer_where}
       ORDER BY {order}
       LIMIT %(limit)s OFFSET %(offset)s
    """, params)
    total = page_total(conn, rows, req, f"""
      {with_cte}
      SELECT COUNT(*) AS n FROM ({inner}) s
        LEFT JOIN session_titles t ON t.session_id = s.session_id
       WHERE TRUE {outer_where}
    """, params)
    for r in rows:
        del r["total"]
    names = project_names(conn, (r["project_slug"] for r in rows))
    for r in rows:
        r["project_name"] = names.get(r["project_slug"], r["project_slug"])
    return envelope(rows, total, req)


def session_turns(conn: psycopg.Connection, session_id: str) -> list[dict]:
    return fetch_all(conn, """
      SELECT m.uuid, m.parent_uuid, m.type, m.timestamp, m.model,
             m.is_sidechain, m.agent_id,
             m.input_tokens, m.output_tokens, m.cache_read_tokens,
             m.cache_create_5m_tokens, m.cache_create_1h_tokens,
             m.prompt_text, m.prompt_chars, m.tool_calls_json,
             m.project_slug, m.cwd, t.title
        FROM messages m
        LEFT JOIN session_titles t ON t.session_id = m.session_id
       WHERE m.session_id = %(sid)s
       ORDER BY m.timestamp ASC, m.uuid
    """, {"sid": session_id})


def session_model_tokens(conn: psycopg.Connection, session_ids: Iterable[str],
                         since: Optional[datetime] = None,
                         until: Optional[datetime] = None) -> list[dict]:
    """Per (session_id, model) assistant-token sums for the given sessions."""
    session_ids = list(session_ids or [])
    if not session_ids:
        return []
    rng, params = range_clause(since, until)
    params["sids"] = session_ids
    return fetch_all(conn, f"""
      SELECT m.session_id, COALESCE(m.model, 'unknown') AS model,
             COALESCE(SUM(m.input_tokens), 0)::bigint            AS input_tokens,
             COALESCE(SUM(m.output_tokens), 0)::bigint           AS output_tokens,
             COALESCE(SUM(m.cache_read_tokens), 0)::bigint       AS cache_read_tokens,
             COALESCE(SUM(m.cache_create_5m_tokens), 0)::bigint  AS cache_create_5m_tokens,
             COALESCE(SUM(m.cache_create_1h_tokens), 0)::bigint  AS cache_create_1h_tokens
        FROM messages m
       WHERE m.type = 'assistant' AND m.session_id = ANY(%(sids)s) {rng}
       GROUP BY m.session_id, COALESCE(m.model, 'unknown')
    """, params)
