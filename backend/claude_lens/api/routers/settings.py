"""`/api/plan`, `/api/settings` and `/api/sync-status`."""
from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from ...db.queries import settings as q
from ...db.queries.sync import sync_status as sync_status_q
from ..deps import get_conn, get_pricing
from ..schemas import Ok, PlanResponse, PlanUpdate, SettingsResponse, SettingsUpdate, SyncStatus

router = APIRouter(tags=["settings"])


def _check_plan(plan: str, pricing: dict) -> None:
    plans = pricing.get("plans", {})
    if plan not in plans:
        raise HTTPException(422,
                            f"plan must be one of: {', '.join(plans)}")


def _settings(conn: psycopg.Connection) -> dict:
    plan = q.get_setting(conn, "plan")
    return {"plan": plan if isinstance(plan, str) and plan else None,
            "timezone": q.get_timezone(conn)}


@router.get("/plan", response_model=PlanResponse)
def get_plan(conn: psycopg.Connection = Depends(get_conn),
             pricing: dict = Depends(get_pricing)):
    """The plan (default `api`) and the whole pricing table."""
    return {"plan": q.get_plan(conn), "pricing": pricing}


@router.post("/plan", response_model=Ok)
def set_plan(body: PlanUpdate,
             conn: psycopg.Connection = Depends(get_conn),
             pricing: dict = Depends(get_pricing)):
    _check_plan(body.plan, pricing)
    q.set_plan(conn, body.plan)
    conn.commit()
    return Ok()


@router.get("/settings", response_model=SettingsResponse)
def get_settings(conn: psycopg.Connection = Depends(get_conn)):
    """`plan` is null until one has been chosen; `timezone` defaults to UTC."""
    return _settings(conn)


@router.post("/settings", response_model=SettingsResponse)
def update_settings(body: SettingsUpdate,
                    conn: psycopg.Connection = Depends(get_conn),
                    pricing: dict = Depends(get_pricing)):
    """Update any subset of the settings; returns the new values."""
    if body.plan is not None:
        _check_plan(body.plan, pricing)
        q.set_plan(conn, body.plan)
    if body.timezone is not None:
        try:
            q.set_timezone(conn, body.timezone)
        except ValueError as e:
            conn.rollback()
            raise HTTPException(422, str(e)) from None
    conn.commit()
    return _settings(conn)


@router.get("/sync-status", response_model=SyncStatus)
def sync_status(conn: psycopg.Connection = Depends(get_conn)):
    """Per machine: the last collector run and the last successful one; plus recent runs."""
    return sync_status_q(conn)
