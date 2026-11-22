"""`/api/sessions` (paginated), `/api/sessions/{id}` and `/api/sessions/{id}/insights`."""
from __future__ import annotations

from typing import Literal, Optional

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from ...core.costs import cost_by_key, turn_cost
from ...core.session_insights import build_insights
from ...db.queries import session_insights as si
from ...db.queries import sessions as q
from ...db.queries.common import MAX_PAGE_SIZE, PageRequest
from ..deps import DateRange, date_range, get_conn, get_pricing
from ..schemas import SessionPage, TurnRow
from ..schemas_insights import SessionInsights

router = APIRouter(tags=["sessions"])

SessionSort = Literal[tuple(q.SESSION_SORTS)]  # type: ignore[valid-type]


def sessions_with_cost(conn: psycopg.Connection, req: PageRequest, rng: DateRange, *,
                       q_: Optional[str], project: Optional[str], model: Optional[str],
                       pricing: dict) -> dict:
    """One page of sessions with `estimated_cost_usd` (also used by the CSV export).

    Raises ValueError for a bad sort.
    """
    data = q.sessions_page(conn, req, since=rng.since, until=rng.until, q=q_ or None,
                           project=project or None, model=model or None, pricing=pricing)
    items = data["items"]
    costs = cost_by_key(
        q.session_model_tokens(conn, [r["session_id"] for r in items], rng.since, rng.until),
        "session_id", pricing,
    )
    for r in items:
        c = costs.get(r["session_id"])
        r["estimated_cost_usd"] = round(c, 4) if c is not None else None
    return data


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
        return sessions_with_cost(conn, req, rng, q_=q_, project=project, model=model,
                                  pricing=pricing)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


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


@router.get("/sessions/{session_id}/insights", response_model=SessionInsights)
def session_insights(session_id: str,
                     conn: psycopg.Connection = Depends(get_conn),
                     pricing: dict = Depends(get_pricing)):
    """New in Claude Lens (phase 06): context growth, tool timeline, subagents,
    files touched, branches, models and duration. An unknown id gives empty lists."""
    return build_insights(
        si.assistant_turns(conn, session_id),
        si.tool_uses(conn, session_id),
        si.branch_spans(conn, session_id),
        pricing,
    )
