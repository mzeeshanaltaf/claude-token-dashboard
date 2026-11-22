"""Helpers shared by the query modules.

Every query uses named `%(name)s` parameters. f-strings in SQL only ever
interpolate internal, caller-controlled fragments (column names from a
whitelist, the range clause below); user-reachable values are always bound.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

import psycopg
from psycopg.rows import dict_row

from ...core.names import best_project_name

MAX_PAGE_SIZE = 200


def fetch_all(conn: psycopg.Connection, query: str, params: Optional[dict] = None) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params or {})
        return cur.fetchall()


def fetch_one(conn: psycopg.Connection, query: str, params: Optional[dict] = None) -> Optional[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params or {})
        return cur.fetchone()


def range_clause(since: Optional[datetime], until: Optional[datetime],
                 col: str = "m.timestamp") -> tuple[str, dict]:
    """`AND col >= since AND col < until` for whichever bounds are given."""
    where, params = [], {}
    if since is not None:
        where.append(f"{col} >= %(since)s")
        params["since"] = since
    if until is not None:
        where.append(f"{col} < %(until)s")
        params["until"] = until
    return ("".join(f" AND {w}" for w in where), params)


def like_pattern(q: str) -> str:
    """`%q%` for ILIKE, with LIKE's metacharacters in `q` escaped (backslash escape)."""
    esc = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


def project_names(conn: psycopg.Connection, slugs: Iterable[str]) -> dict[str, str]:
    """{slug: pretty name} for the given slugs, in one query (no N+1)."""
    slugs = sorted({s for s in slugs if s is not None})
    if not slugs:
        return {}
    rows = fetch_all(conn, """
        SELECT project_slug, array_agg(DISTINCT cwd) FILTER (WHERE cwd IS NOT NULL) AS cwds
          FROM messages
         WHERE project_slug = ANY(%(slugs)s)
         GROUP BY project_slug
    """, {"slugs": slugs})
    cwds = {r["project_slug"]: r["cwds"] or [] for r in rows}
    return {s: best_project_name(cwds.get(s, []), s) for s in slugs}


@dataclass(frozen=True)
class PageRequest:
    page: int = 1
    page_size: int = 50
    sort: Optional[str] = None
    order: Optional[str] = None  # "asc" | "desc"; None = the sort key's default

    def __post_init__(self) -> None:
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if not 1 <= self.page_size <= MAX_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")
        if self.order not in (None, "asc", "desc"):
            raise ValueError("order must be 'asc' or 'desc'")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def order_by(sorts: dict[str, tuple[str, str]], default: str, req: PageRequest,
             tiebreak: str) -> str:
    """ORDER BY fragment from a whitelist {key: (sql_expr, default_direction)}."""
    key = req.sort or default
    if key not in sorts:
        raise ValueError(f"sort must be one of: {', '.join(sorts)}")
    expr, default_dir = sorts[key]
    direction = (req.order or default_dir).upper()
    return f"{expr} {direction} NULLS LAST, {tiebreak}"


def envelope(items: list[dict], total: int, req: PageRequest) -> dict[str, Any]:
    return {"items": items, "total": total, "page": req.page, "page_size": req.page_size}


def page_total(conn: psycopg.Connection, rows: list[dict], req: PageRequest,
               count_query: str, params: dict) -> int:
    """The window `total` from the page's rows, or a COUNT when the page is empty."""
    if rows:
        return int(rows[0]["total"])
    if req.page == 1:
        return 0
    row = fetch_one(conn, count_query, params)
    return int(row["n"]) if row else 0
