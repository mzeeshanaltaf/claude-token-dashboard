"""Single-admin login: `/api/auth/*` and the first-boot admin bootstrap."""
from __future__ import annotations

import logging

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from ..config import Settings
from ..core.passwords import (
    check_new_password, hash_password, new_token, token_hash, verify_password,
)
from ..db.queries import auth as auth_q
from .deps import (
    COOKIE_NAME, SESSION_LIFETIME, CurrentUser, clear_session_cookie, client_ip,
    current_user, get_conn, get_settings, set_session_cookie,
)
from .schemas import LoginRequest, Me, Ok, PasswordChange, PasswordChanged

log = logging.getLogger("claude_lens.api")
router = APIRouter(prefix="/auth", tags=["auth"])


def bootstrap_admin(conn: psycopg.Connection, settings: Settings) -> bool:
    """Create the admin from ADMIN_USERNAME / ADMIN_PASSWORD if `users` is empty.

    Returns True when a user was created. Raises RuntimeError (the app refuses
    to start) when there are no users and the env vars are missing. Once a user
    exists the env vars are ignored, so changing them never resets a password.
    """
    if auth_q.count_users(conn) > 0:
        conn.rollback()
        return False
    if not (settings.admin_username and settings.admin_password):
        conn.rollback()
        raise RuntimeError(
            "no users exist and ADMIN_USERNAME / ADMIN_PASSWORD are not set: refusing to start"
        )
    check_new_password(settings.admin_password)
    auth_q.create_user(conn, settings.admin_username, hash_password(settings.admin_password))
    conn.commit()
    log.info("created admin user %r", settings.admin_username)
    return True


def _lock_key(request: Request, settings: Settings, username: str):
    return (client_ip(request, settings), username.strip().lower())


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "too many failed attempts; try again later",
        headers={"Retry-After": str(retry_after)},
    )


@router.post("/login", response_model=Me, responses={401: {}, 429: {}})
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    conn: psycopg.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> Me:
    lockout = request.app.state.lockout
    key = _lock_key(request, settings, body.username)
    wait = lockout.retry_after(key)
    if wait:
        raise _too_many(wait)
    user = auth_q.get_user(conn, body.username)
    if not verify_password(body.password, user["password_hash"] if user else None):
        conn.rollback()
        lockout.record_failure(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid username or password")
    lockout.reset(key)
    token = new_token()
    auth_q.purge_expired_sessions(conn)
    auth_q.create_session(conn, token_hash(token), user["id"], SESSION_LIFETIME)
    row = auth_q.session_user(conn, token_hash(token))
    conn.commit()
    set_session_cookie(response, token, settings)
    return Me(username=user["username"], expires_at=row["expires_at"])


@router.post("/logout", response_model=Ok)
def logout(
    request: Request,
    response: Response,
    conn: psycopg.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> Ok:
    """Revoke the current session (if any) and clear the cookie. Always 200."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        auth_q.delete_session(conn, token_hash(token))
        conn.commit()
    clear_session_cookie(response, settings)
    return Ok()


@router.get("/me", response_model=Me, responses={401: {}})
def me(user: CurrentUser = Depends(current_user)) -> Me:
    return Me(username=user.username, expires_at=user.expires_at)


@router.post("/password", response_model=PasswordChanged, responses={400: {}, 401: {}, 429: {}})
def change_password(
    body: PasswordChange,
    request: Request,
    user: CurrentUser = Depends(current_user),
    conn: psycopg.Connection = Depends(get_conn),
    settings: Settings = Depends(get_settings),
) -> PasswordChanged:
    """Change the password and revoke every other session of this user."""
    lockout = request.app.state.lockout
    key = _lock_key(request, settings, user.username)
    wait = lockout.retry_after(key)
    if wait:
        raise _too_many(wait)
    row = auth_q.get_user(conn, user.username)
    if row is None or not verify_password(body.current, row["password_hash"]):
        conn.rollback()
        lockout.record_failure(key)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "current password is incorrect")
    lockout.reset(key)
    auth_q.set_password_hash(conn, user.user_id, hash_password(body.new))
    revoked = auth_q.delete_user_sessions(conn, user.user_id, keep_token_hash=user.token_hash)
    conn.commit()
    return PasswordChanged(revoked_sessions=revoked)
