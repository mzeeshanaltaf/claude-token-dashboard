"""FastAPI dependencies: DB connection, pricing, date range, client IP, current user."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

import psycopg
from fastapi import Depends, HTTPException, Query, Request, Response, status

from ..config import Settings
from ..core.passwords import token_hash
from ..db.queries import auth as auth_q

COOKIE_NAME = "cl_session"
SESSION_LIFETIME = timedelta(days=7)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_conn(request: Request) -> Iterator[psycopg.Connection]:
    """One pooled connection per request (shared by every dependency that asks).

    Endpoints that write call `conn.commit()` themselves before returning, so
    the change is durable before the response goes out.
    """
    with request.app.state.pool.connection() as conn:
        yield conn


def get_pricing(request: Request) -> dict:
    return request.app.state.get_pricing()


# --------------------------------------------------------------------------
# date range
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DateRange:
    since: Optional[datetime] = None
    until: Optional[datetime] = None


def parse_instant(value: Optional[str], name: str) -> Optional[datetime]:
    """ISO 8601 → aware datetime. A value without an offset is read as UTC."""
    if value is None or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
    except ValueError:
        raise HTTPException(422,
                            f"{name} must be an ISO 8601 date or timestamp") from None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def date_range(
    since: Optional[str] = Query(None, description="ISO 8601, inclusive (no offset = UTC)"),
    until: Optional[str] = Query(None, description="ISO 8601, exclusive (no offset = UTC)"),
) -> DateRange:
    return DateRange(parse_instant(since, "since"), parse_instant(until, "until"))


# --------------------------------------------------------------------------
# client identity
# --------------------------------------------------------------------------

def client_ip(request: Request, settings: Settings) -> str:
    """The peer address, or (behind a trusted proxy) the last X-Forwarded-For hop.

    The last entry is the one our own proxy appended; anything to its left was
    supplied by the client and can be forged.
    """
    if settings.trust_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            hops = [h.strip() for h in xff.split(",") if h.strip()]
            if hops:
                return hops[-1]
    return request.client.host if request.client else "unknown"


# --------------------------------------------------------------------------
# sessions / current user
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    username: str
    token_hash: str
    expires_at: datetime


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        COOKIE_NAME, token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True, samesite="lax", secure=settings.cookie_secure, path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax",
                           secure=settings.cookie_secure)


def _unauthorized() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")


def current_user(
    request: Request,
    response: Response,
    conn: psycopg.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """The logged-in user, from the `cl_session` cookie, or 401.

    Slides the expiry forward (and re-sends the cookie) once less than half the
    7-day lifetime is left.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise _unauthorized()
    th = token_hash(token)
    row = auth_q.session_user(conn, th)
    if row is None:
        conn.rollback()
        raise _unauthorized()
    expires_at = row["expires_at"]
    if row["remaining"] < SESSION_LIFETIME / 2:
        expires_at = auth_q.extend_session(conn, th, SESSION_LIFETIME) or expires_at
        conn.commit()
        set_session_cookie(response, token, settings)
    else:
        conn.rollback()  # end the read transaction; nothing to keep
    return CurrentUser(row["user_id"], row["username"], th, expires_at)
