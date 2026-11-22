"""`/api/export/{sessions,prompts,projects}.csv` (new in Claude Lens, phase 06).

Each takes the same filters as its list endpoint and streams **every** matching
row (no page cap), in the list's sort order. Page 1 runs on the request's
connection, so a bad parameter is a 422 before any bytes are sent; later pages
are read from their own pooled connection while the response streams.
"""
from __future__ import annotations

from typing import Callable, Iterator, Literal, Optional

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ...core.csv_export import csv_lines
from ...db.queries import activity as aq
from ...db.queries.common import MAX_PAGE_SIZE, PageRequest
from ...db.queries.settings import get_timezone
from ..deps import DateRange, date_range, get_conn, get_pricing
from .projects import projects_with_cost
from .prompts import PromptSort, prompts_with_cost
from .sessions import SessionSort, sessions_with_cost

router = APIRouter(tags=["export"])

SESSION_COLUMNS = (
    "session_id", "title", "project_name", "project_slug", "started", "ended", "turns",
    "input_tokens", "output_tokens", "cache_read_tokens", "cache_create_5m_tokens",
    "cache_create_1h_tokens", "total_tokens", "estimated_cost_usd",
)
PROMPT_COLUMNS = (
    "timestamp", "session_id", "project_slug", "title", "model", "prompt_chars",
    "input_tokens", "output_tokens", "cache_read_tokens", "cache_create_5m_tokens",
    "cache_create_1h_tokens", "estimated_cost_usd", "prompt_text",
)
PROJECT_COLUMNS = (
    "project_name", "project_slug", "sessions", "turns", "input_tokens", "output_tokens",
    "cache_read_tokens", "cache_create_5m_tokens", "cache_create_1h_tokens", "total_tokens",
    "last_active", "estimated_cost_usd",
)

CSV_RESPONSE = {200: {"content": {"text/csv": {}}, "description": "CSV file (UTF-8 with BOM)"}}
Order = Optional[Literal["asc", "desc"]]


def _csv(conn: psycopg.Connection, table: str, columns, rows) -> StreamingResponse:
    day = aq.today(conn, get_timezone(conn)).isoformat()
    conn.rollback()  # end the read transaction before the body streams
    return StreamingResponse(
        csv_lines(columns, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="claude-lens-{table}-{day}.csv"'},
    )


def _all_pages(request: Request, first: dict,
               fetch: Callable[[psycopg.Connection, int], dict]) -> Iterator[dict]:
    """Page 1's items, then every later page until `total` rows have been sent."""
    yield from first["items"]
    sent = len(first["items"])
    if sent >= first["total"] or sent < MAX_PAGE_SIZE:
        return
    with request.app.state.pool.connection() as conn:
        page = 2
        while sent < first["total"]:
            items = fetch(conn, page)["items"]
            yield from items
            sent += len(items)
            if len(items) < MAX_PAGE_SIZE:
                break
            page += 1


def _req(page: int, sort, order) -> PageRequest:
    return PageRequest(page=page, page_size=MAX_PAGE_SIZE, sort=sort, order=order)


@router.get("/export/sessions.csv", response_class=StreamingResponse, responses=CSV_RESPONSE)
def export_sessions(
    request: Request,
    rng: DateRange = Depends(date_range),
    sort: Optional[SessionSort] = Query(None),
    order: Order = Query(None),
    q_: Optional[str] = Query(None, alias="q", max_length=200),
    project: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    conn: psycopg.Connection = Depends(get_conn),
    pricing: dict = Depends(get_pricing),
):
    """Every session `/api/sessions` would list for these filters, as CSV."""
    def fetch(c: psycopg.Connection, page: int) -> dict:
        return sessions_with_cost(c, _req(page, sort, order), rng, q_=q_, project=project,
                                  model=model, pricing=pricing)
    try:
        first = fetch(conn, 1)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return _csv(conn, "sessions", SESSION_COLUMNS, _all_pages(request, first, fetch))


@router.get("/export/prompts.csv", response_class=StreamingResponse, responses=CSV_RESPONSE)
def export_prompts(
    request: Request,
    rng: DateRange = Depends(date_range),
    sort: Optional[PromptSort] = Query(None),
    order: Order = Query(None),
    q_: Optional[str] = Query(None, alias="q", max_length=200),
    project: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    conn: psycopg.Connection = Depends(get_conn),
    pricing: dict = Depends(get_pricing),
):
    """Every prompt `/api/prompts` would list for these filters, as CSV."""
    def fetch(c: psycopg.Connection, page: int) -> dict:
        return prompts_with_cost(c, _req(page, sort, order), rng, q_=q_, project=project,
                                 model=model, pricing=pricing)
    try:
        first = fetch(conn, 1)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return _csv(conn, "prompts", PROMPT_COLUMNS, _all_pages(request, first, fetch))


@router.get("/export/projects.csv", response_class=StreamingResponse, responses=CSV_RESPONSE)
def export_projects(
    rng: DateRange = Depends(date_range),
    q_: Optional[str] = Query(None, alias="q", max_length=200,
                              description="name or slug contains (the Projects page filter)"),
    conn: psycopg.Connection = Depends(get_conn),
    pricing: dict = Depends(get_pricing),
):
    """Every project `/api/projects` lists for the range, most expensive first, as CSV."""
    rows = projects_with_cost(conn, rng, pricing)
    if q_ and q_.strip():
        needle = q_.strip().casefold()
        rows = [r for r in rows
                if needle in r["project_name"].casefold() or needle in r["project_slug"].casefold()]
    rows.sort(key=lambda r: (-(r["estimated_cost_usd"] or 0), r["project_slug"]))
    return _csv(conn, "projects", PROJECT_COLUMNS, iter(rows))
