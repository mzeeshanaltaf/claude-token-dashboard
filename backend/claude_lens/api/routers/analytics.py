"""`/api/overview`, `/api/daily`, `/api/by-model`, `/api/tools`, `/api/skills`."""
from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from ...core.costs import overview_costs, usage_of
from ...core.pricing import cost_for
from ...db.queries import analytics as q
from ...db.queries.settings import get_timezone
from ..deps import DateRange, date_range, get_conn, get_pricing
from ..schemas import DailyRow, ModelRow, Overview, SkillRow, ToolRow

router = APIRouter(tags=["analytics"])


@router.get("/overview", response_model=Overview)
def overview(rng: DateRange = Depends(date_range),
             conn: psycopg.Connection = Depends(get_conn),
             pricing: dict = Depends(get_pricing)):
    totals = q.overview_totals(conn, rng.since, rng.until)
    totals.update(overview_costs(q.model_breakdown(conn, rng.since, rng.until), pricing))
    return totals


@router.get("/daily", response_model=list[DailyRow])
def daily(rng: DateRange = Depends(date_range),
          conn: psycopg.Connection = Depends(get_conn)):
    """Per-day token sums; days are local dates in the `timezone` setting."""
    return q.daily_token_breakdown(conn, rng.since, rng.until, tz=get_timezone(conn))


@router.get("/by-model", response_model=list[ModelRow])
def by_model(rng: DateRange = Depends(date_range),
             conn: psycopg.Connection = Depends(get_conn),
             pricing: dict = Depends(get_pricing)):
    rows = q.model_breakdown(conn, rng.since, rng.until)
    for r in rows:
        c = cost_for(r["model"], usage_of(r), pricing)
        r["cost_usd"] = c["usd"]
        r["cost_estimated"] = c["estimated"]
    return rows


@router.get("/tools", response_model=list[ToolRow])
def tools(rng: DateRange = Depends(date_range),
          conn: psycopg.Connection = Depends(get_conn)):
    return q.tool_token_breakdown(conn, rng.since, rng.until)


@router.get("/skills", response_model=list[SkillRow])
def skills(rng: DateRange = Depends(date_range),
           conn: psycopg.Connection = Depends(get_conn)):
    """`tokens_per_call` is the SKILL.md size from `skill_catalog` (null when unknown)."""
    return q.skill_breakdown(conn, rng.since, rng.until)
