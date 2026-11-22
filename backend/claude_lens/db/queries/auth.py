"""Users and server-side login sessions (`users`, `auth_sessions`)."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

import psycopg

from .common import fetch_one


def count_users(conn: psycopg.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_user(conn: psycopg.Connection, username: str) -> Optional[dict]:
    return fetch_one(conn, "SELECT id, username, password_hash FROM users WHERE username = %(u)s",
                     {"u": username})


def create_user(conn: psycopg.Connection, username: str, password_hash: str) -> int:
    return conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (%(u)s, %(h)s) RETURNING id",
        {"u": username, "h": password_hash},
    ).fetchone()[0]


def set_password_hash(conn: psycopg.Connection, user_id: int, password_hash: str) -> None:
    conn.execute("UPDATE users SET password_hash = %(h)s WHERE id = %(id)s",
                 {"h": password_hash, "id": user_id})


def create_session(conn: psycopg.Connection, token_hash: str, user_id: int,
                   lifetime: timedelta) -> None:
    conn.execute(
        "INSERT INTO auth_sessions (token_hash, user_id, expires_at)"
        " VALUES (%(t)s, %(u)s, now() + %(life)s)",
        {"t": token_hash, "u": user_id, "life": lifetime},
    )


def session_user(conn: psycopg.Connection, token_hash: str) -> Optional[dict]:
    """The live session's user and expiry, or None when missing or expired."""
    return fetch_one(conn, """
      SELECT u.id AS user_id, u.username, s.expires_at, s.expires_at - now() AS remaining
        FROM auth_sessions s JOIN users u ON u.id = s.user_id
       WHERE s.token_hash = %(t)s AND s.expires_at > now()
    """, {"t": token_hash})


def extend_session(conn: psycopg.Connection, token_hash: str, lifetime: timedelta):
    row = conn.execute(
        "UPDATE auth_sessions SET expires_at = now() + %(life)s WHERE token_hash = %(t)s"
        " RETURNING expires_at",
        {"t": token_hash, "life": lifetime},
    ).fetchone()
    return row[0] if row else None


def delete_session(conn: psycopg.Connection, token_hash: str) -> None:
    conn.execute("DELETE FROM auth_sessions WHERE token_hash = %(t)s", {"t": token_hash})


def delete_user_sessions(conn: psycopg.Connection, user_id: int,
                         keep_token_hash: Optional[str] = None) -> int:
    """Revoke every session of `user_id` except `keep_token_hash`. Returns how many."""
    cur = conn.execute(
        "DELETE FROM auth_sessions WHERE user_id = %(u)s"
        " AND (%(keep)s::text IS NULL OR token_hash <> %(keep)s::text)",
        {"u": user_id, "keep": keep_token_hash},
    )
    return cur.rowcount


def purge_expired_sessions(conn: psycopg.Connection) -> int:
    return conn.execute("DELETE FROM auth_sessions WHERE expires_at <= now()").rowcount
