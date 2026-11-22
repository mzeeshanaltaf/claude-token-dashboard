"""`/api/projects`, `/api/projects/daily` and `/api/projects/{slug}/sessions`."""
from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from ...core.costs import cost_breakdown_by_key, cost_by_key, cost_by_model_per_key
from ...db.queries import projects as q
from ...db.queries.analytics import daily_model_tokens
from ...db.queries.sessions import session_model_tokens
from ...db.queries.settings import get_timezone
from ..deps import DateRange, date_range, get_conn, get_pricing
from ..schemas import ProjectDailyCost, ProjectRow, ProjectSessionRow

router = APIRouter(tags=["projects"])


@router.get("/projects/daily", response_model=list[ProjectDailyCost])
def projects_daily(rng: DateRange = Depends(date_range),
                   conn: psycopg.Connection = Depends(get_conn),
                   pricing: dict = Depends(get_pricing)):
    """Estimated cost per (project, local day) for the projects list's sparklines.

    Days with no priced activity are absent; days are in the `timezone` setting.
    """
    rows = daily_model_tokens(conn, rng.since, rng.until, tz=get_timezone(conn), by_project=True)
    costs = cost_by_model_per_key(rows, ("project_slug", "day"), pricing)
    out = [{"project_slug": slug, "day": day, "cost_usd": round(sum(models.values()), 4)}
           for (slug, day), models in costs.items()]
    out.sort(key=lambda r: (r["project_slug"], r["day"]))
    return out


def _r4(v):
    return round(v, 4) if v is not None else None


@router.get("/projects", response_model=list[ProjectRow])
def projects(rng: DateRange = Depends(date_range),
             conn: psycopg.Connection = Depends(get_conn),
             pricing: dict = Depends(get_pricing)):
    rows = q.project_summary(conn, rng.since, rng.until)
    model_rows = q.project_model_tokens(conn, rng.since, rng.until)
    costs = cost_by_key(model_rows, "project_slug", pricing)
    breakdowns = cost_breakdown_by_key(model_rows, "project_slug", pricing)
    for r in rows:
        slug = r["project_slug"]
        r["estimated_cost_usd"] = _r4(costs.get(slug))
        bd = breakdowns.get(slug)
        r["cost_input_usd"] = _r4(bd["input"]) if bd else None
        r["cost_output_usd"] = _r4(bd["output"]) if bd else None
        r["cost_cache_read_usd"] = _r4(bd["cache_read"]) if bd else None
        r["cost_cache_create_5m_usd"] = _r4(bd["cache_create_5m"]) if bd else None
        r["cost_cache_create_1h_usd"] = _r4(bd["cache_create_1h"]) if bd else None
        r["cost_cache_write_usd"] = (
            _r4(bd["cache_create_5m"] + bd["cache_create_1h"]) if bd else None
        )
    return rows


@router.get("/projects/{slug}/sessions", response_model=list[ProjectSessionRow])
def project_sessions(slug: str,
                     rng: DateRange = Depends(date_range),
                     conn: psycopg.Connection = Depends(get_conn),
                     pricing: dict = Depends(get_pricing)):
    rows = q.project_sessions(conn, slug, rng.since, rng.until)
    costs = cost_by_key(
        session_model_tokens(conn, [r["session_id"] for r in rows], rng.since, rng.until),
        "session_id", pricing,
    )
    for r in rows:
        r["estimated_cost_usd"] = _r4(costs.get(r["session_id"]))
    return rows
