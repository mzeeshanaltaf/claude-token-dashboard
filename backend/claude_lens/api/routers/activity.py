"""`/api/activity/{calendar,hourly,summary}` (new in Claude Lens, phase 06).

Every bucket is a local date / hour in the `timezone` setting. Per-day cost is
the `/api/daily` rollup: tokens per (day, model), priced, then summed per day.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal, Optional

import psycopg
from fastapi import APIRouter, Depends, Query

from ...core.activity import streaks
from ...core.costs import cost_by_model_per_key, overview_costs, usage_of
from ...core.pricing import cost_for
from ...db.queries import activity as aq
from ...db.queries import analytics
from ...db.queries.common import project_names
from ...db.queries.settings import get_timezone
from ..deps import DateRange, date_range, get_conn, get_pricing
from ..schemas_insights import ActivityCalendar, ActivityHourly, ActivitySummary

router = APIRouter(tags=["activity"])

_CORE = ("input_tokens", "output_tokens", "cache_create_5m_tokens", "cache_create_1h_tokens")


def daily_with_cost(conn: psycopg.Connection, since: Optional[datetime],
                    until: Optional[datetime], tz: str, pricing: dict) -> list[dict]:
    """[{day, cost_usd, tokens (core), sessions, turns}] for days with any record."""
    rows = analytics.daily_token_breakdown(conn, since, until, tz=tz)
    costs = cost_by_model_per_key(
        analytics.daily_model_tokens(conn, since, until, tz=tz), "day", pricing)
    return [{
        "day": r["day"],
        "cost_usd": round(sum(costs.get(r["day"], {}).values()), 4),
        "tokens": int(r["input_tokens"] + r["output_tokens"] + r["cache_create_tokens"]),
        "sessions": r["sessions"],
        "turns": r["turns"],
    } for r in rows]


@router.get("/activity/calendar", response_model=ActivityCalendar)
def calendar(metric: Literal["cost", "tokens"] = "cost",
             days: int = Query(365, ge=7, le=1100, description="window length, ending today"),
             conn: psycopg.Connection = Depends(get_conn),
             pricing: dict = Depends(get_pricing)):
    """One value per active local date over the last `days` days (today included)."""
    tz = get_timezone(conn)
    w = aq.local_window(conn, tz, days)
    out = []
    for d in daily_with_cost(conn, w["since"], None, tz, pricing):
        if not w["start_day"] <= d["day"] <= w["today"]:
            continue
        d["value"] = d["cost_usd"] if metric == "cost" else d["tokens"]
        out.append(d)
    return {"metric": metric, "timezone": tz, "start": w["start_day"], "end": w["today"],
            "days": out}


def _hour_grid(rows: list[dict], pricing: dict) -> list[dict]:
    grid = {(d, h): {"dow": d, "hour": h, "turns": 0, "tokens": 0, "cost_usd": 0.0}
            for d in range(1, 8) for h in range(24)}
    for r in rows:
        cell = grid[(r["dow"], r["hour"])]
        cell["turns"] += r["turns"]
        cell["tokens"] += sum(int(r[k]) for k in _CORE)
        usd = cost_for(r["model"], usage_of(r), pricing)["usd"]
        if usd:
            cell["cost_usd"] += usd
    cells = list(grid.values())
    for c in cells:
        c["cost_usd"] = round(c["cost_usd"], 4)
    return cells


@router.get("/activity/hourly", response_model=ActivityHourly)
def hourly(rng: DateRange = Depends(date_range),
           conn: psycopg.Connection = Depends(get_conn),
           pricing: dict = Depends(get_pricing)):
    """A 7x24 grid (ISO weekday x local hour) of turns, core tokens and cost."""
    tz = get_timezone(conn)
    rows = aq.hourly_model_rows(conn, rng.since, rng.until, tz)
    return {"timezone": tz, "cells": _hour_grid(rows, pricing)}


@router.get("/activity/summary", response_model=ActivitySummary)
def summary(rng: DateRange = Depends(date_range),
            conn: psycopg.Connection = Depends(get_conn),
            pricing: dict = Depends(get_pricing)):
    """Active days, streaks, busiest day, per-active-day averages, top project, peak hour."""
    tz = get_timezone(conn)
    days = daily_with_cost(conn, rng.since, rng.until, tz, pricing)

    last_day: date = aq.today(conn, tz)
    if rng.until is not None:  # `until` is exclusive: its local day is not in range
        last_day = min(last_day, aq.local_date(conn, rng.until - timedelta(microseconds=1), tz))
    days = [d for d in days if d["day"] <= last_day]
    if rng.since is not None:
        first_day: Optional[date] = aq.local_date(conn, rng.since, tz)
    else:
        first_day = days[0]["day"] if days else None
    days_in_range = (last_day - first_day).days + 1 if first_day and first_day <= last_day else 0

    current, longest = streaks((d["day"] for d in days), last_day)
    busiest = max(days, key=lambda d: (d["cost_usd"], d["tokens"]), default=None)
    total_cost = sum(d["cost_usd"] for d in days)
    total_tokens = sum(d["tokens"] for d in days)
    n = len(days)

    top = aq.top_project(conn, rng.since, rng.until)
    top_project = None
    if top:
        slug = top["project_slug"]
        cost = overview_costs(analytics.model_breakdown(conn, rng.since, rng.until, slug),
                              pricing)["cost_usd"]
        top_project = {**top, "project_name": project_names(conn, [slug]).get(slug, slug),
                       "cost_usd": cost}

    per_hour: dict[int, int] = {}
    for r in aq.hourly_model_rows(conn, rng.since, rng.until, tz):
        per_hour[r["hour"]] = per_hour.get(r["hour"], 0) + r["turns"]
    peak = max(per_hour.items(), key=lambda kv: (kv[1], -kv[0]), default=None)

    return {
        "timezone": tz,
        "first_day": first_day,
        "last_day": last_day,
        "days_in_range": days_in_range,
        "active_days": n,
        "current_streak": current,
        "longest_streak": longest,
        "busiest_day": ({"day": busiest["day"], "cost_usd": busiest["cost_usd"],
                         "tokens": busiest["tokens"]} if busiest else None),
        "avg_cost_per_active_day": round(total_cost / n, 4) if n else 0.0,
        "avg_tokens_per_active_day": round(total_tokens / n, 1) if n else 0.0,
        "total_cost_usd": round(total_cost, 4),
        "total_tokens": total_tokens,
        "top_project": top_project,
        "peak_hour": {"hour": peak[0], "turns": peak[1]} if peak and peak[1] else None,
    }
