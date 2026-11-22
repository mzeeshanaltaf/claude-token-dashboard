"""`/api/prompts` (paginated)."""
from __future__ import annotations

from typing import Literal, Optional

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from ...core.costs import turn_cost
from ...db.queries import prompts as q
from ...db.queries.common import MAX_PAGE_SIZE, PageRequest
from ..deps import DateRange, date_range, get_conn, get_pricing
from ..schemas import PromptPage

router = APIRouter(tags=["prompts"])

PromptSort = Literal[tuple(q.PROMPT_SORTS)]  # type: ignore[valid-type]


def prompts_with_cost(conn: psycopg.Connection, req: PageRequest, rng: DateRange, *,
                      q_: Optional[str], project: Optional[str], model: Optional[str],
                      pricing: dict) -> dict:
    """One page of priced prompts (also used by the CSV export). ValueError on a bad sort."""
    data = q.prompts_page(conn, req, pricing, since=rng.since, until=rng.until,
                          q=q_ or None, project=project or None, model=model or None)
    for r in data["items"]:
        r.update(turn_cost(r, pricing))
    return data


@router.get("/prompts", response_model=PromptPage)
def prompts(
    rng: DateRange = Depends(date_range),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    sort: Optional[PromptSort] = Query(None, description="default: tokens"),
    order: Optional[Literal["asc", "desc"]] = Query(None, description="default: desc"),
    q_: Optional[str] = Query(None, alias="q", max_length=200,
                              description="matches the prompt text"),
    project: Optional[str] = Query(None, description="project slug"),
    model: Optional[str] = Query(None, description="the answering turn's model"),
    conn: psycopg.Connection = Depends(get_conn),
    pricing: dict = Depends(get_pricing),
):
    """Each prompt with the assistant turn that answered it, priced on all 5 token types."""
    req = PageRequest(page=page, page_size=page_size, sort=sort, order=order)
    try:
        return prompts_with_cost(conn, req, rng, q_=q_, project=project, model=model,
                                 pricing=pricing)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
