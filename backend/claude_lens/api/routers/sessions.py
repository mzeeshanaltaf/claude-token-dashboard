"""`/api/sessions` (paginated) and `/api/sessions/{id}`."""
from __future__ import annotations

from typing import Literal, Optional

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from ...core.costs import cost_by_key, turn_cost
from ...db.queries import sessions as q
from ...db.queries.common import MAX_PAGE_SIZE, PageRequest
from ..deps import DateRange, date_range, get_conn, get_pricing
from ..schemas import SessionPage, TurnRow

router = APIRouter(tags=["sessions"])

SessionSort = Literal[tuple(q.SESSION_SORTS)]  # type: ignore[valid-type]


@router.get("/sessions", response_model=SessionPage)
def sessions(
    rng: DateRange = Depends(date_range),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    sort: Optional[SessionSort] = Query(None, description="default: ended"),
    order: Optional[Literal["asc", "desc"]] = Query(None, description="default: the sort's own"),
    q_: Optional[str] = Query(None, alias="q", max_length=200,
                              description="matches the title or session id"),
    project: Optional[str] = Query(None, description="project slug"),
    model: Optional[str] = Query(None, description="sessions that used this model"),
    conn: psycopg.Connection = Depends(get_conn),
    pricing: dict = Depends(get_pricing),
):
    """Sessions with activity in range. Token sums and cost cover only that range."""
    req = PageRequest(page=page, page_size=page_size, sort=sort, order=order)
    try:
        data = q.sessions_page(conn, req, since=rng.since, until=rng.until, q=q_ or None,
                               project=project or None, model=model or None, pricing=pricing)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    items = data["items"]
    costs = cost_by_key(
        q.session_model_tokens(conn, [r["session_id"] for r in items], rng.since, rng.until),
        "session_id", pricing,
    )
    for r in items:
        c = costs.get(r["session_id"])
        r["estimated_cost_usd"] = round(c, 4) if c is not None else None
    return data


@router.get("/sessions/{session_id}", response_model=list[TurnRow])
def session_detail(session_id: str,
                   conn: psycopg.Connection = Depends(get_conn),
                   pricing: dict = Depends(get_pricing)):
    """Every record of the session in time order; assistant turns carry their cost."""
    rows = q.session_turns(conn, session_id)
    for r in rows:
        if r["type"] == "assistant" and r["model"]:
            r.update(turn_cost(r, pricing))
    return rows
