"""User prompts joined with the assistant turn that answered them.

Ported from `token_dashboard/db.py::expensive_prompts`, now paginated. Each
row carries the assistant turn's five token counts, so the API can price the
**whole** turn (the old app priced only its cache reads).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import psycopg

from ...core.costs import RATES_CTE, cost_sql, rate_joins, rates_param
from .common import (
    PageRequest, envelope, fetch_all, like_pattern, order_by, page_total, range_clause,
)

_CORE = "(a.input_tokens + a.output_tokens + a.cache_create_5m_tokens + a.cache_create_1h_tokens)"

PROMPT_SORTS = {
    "tokens":     (_CORE, "desc"),
    "recent":     ("u.timestamp", "desc"),
    "cost":       (cost_sql("a"), "desc"),
    "cache_read": ("a.cache_read_tokens", "desc"),
    "chars":      ("u.prompt_chars", "desc"),
}
DEFAULT_PROMPT_SORT = "tokens"


def prompts_page(
    conn: psycopg.Connection,
    req: PageRequest,
    pricing: dict,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    q: Optional[str] = None,
    project: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """{items, total, page, page_size}. `sort` is one of PROMPT_SORTS."""
    order = order_by(PROMPT_SORTS, DEFAULT_PROMPT_SORT, req, "u.uuid, a.uuid")
    rng, params = range_clause(since, until, col="u.timestamp")
    where = rng
    if q:
        where += " AND u.prompt_text ILIKE %(q)s"
        params["q"] = like_pattern(q)
    if project:
        where += " AND u.project_slug = %(project)s"
        params["project"] = project
    if model:
        where += " AND a.model = %(model)s"
        params["model"] = model
    params.update(rates=rates_param(pricing), limit=req.page_size, offset=req.offset)

    base = f"""
        FROM messages u
        JOIN messages a ON a.parent_uuid = u.uuid AND a.type = 'assistant'
       WHERE u.type = 'user' AND u.prompt_text IS NOT NULL {where}"""
    rows = fetch_all(conn, f"""
      WITH {RATES_CTE}
      SELECT u.uuid AS user_uuid, u.session_id, u.project_slug, u.timestamp,
             u.prompt_text, u.prompt_chars,
             a.uuid AS assistant_uuid, a.model,
             a.input_tokens, a.output_tokens, a.cache_read_tokens,
             a.cache_create_5m_tokens, a.cache_create_1h_tokens,
             {_CORE} AS core_tokens,
             t.title,
             COUNT(*) OVER () AS total
        FROM messages u
        JOIN messages a ON a.parent_uuid = u.uuid AND a.type = 'assistant'
        {rate_joins("a")}
        LEFT JOIN session_titles t ON t.session_id = u.session_id
       WHERE u.type = 'user' AND u.prompt_text IS NOT NULL {where}
       ORDER BY {order}
       LIMIT %(limit)s OFFSET %(offset)s
    """, params)
    total = page_total(conn, rows, req, f"SELECT COUNT(*) AS n {base}", params)
    for r in rows:
        del r["total"]
    return envelope(rows, total, req)
