"""`/api/tips`, `POST /api/tips/dismiss` and `POST /api/tips/restore`."""
from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from ...core import tips as engine
from ..deps import get_conn
from ..schemas import Ok, Tip, TipDismiss

router = APIRouter(tags=["tips"])


@router.get("/tips", response_model=list[Tip])
def tips(conn: psycopg.Connection = Depends(get_conn)):
    """Suggestions from the last 7 days; dismissed ones stay hidden for 14 days."""
    return engine.all_tips(conn)


@router.post("/tips/dismiss", response_model=Ok)
def dismiss(body: TipDismiss, conn: psycopg.Connection = Depends(get_conn)):
    engine.dismiss_tip(conn, body.key)
    conn.commit()
    return Ok()


@router.post("/tips/restore", response_model=Ok)
def restore(body: TipDismiss, conn: psycopg.Connection = Depends(get_conn)):
    """Undo a dismissal (new in Claude Lens, for the undo toast)."""
    engine.restore_tip(conn, body.key)
    conn.commit()
    return Ok()
