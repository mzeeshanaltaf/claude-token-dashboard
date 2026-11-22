"""Raw rows for `/api/sessions/{id}/insights`; `core.session_insights` shapes them."""
from __future__ import annotations

import psycopg

from .common import fetch_all


def assistant_turns(conn: psycopg.Connection, session_id: str) -> list[dict]:
    """The session's assistant turns in time order (main chain and sidechains)."""
    return fetch_all(conn, """
      SELECT m.uuid, m.timestamp, m.model, m.is_sidechain, m.agent_id,
             m.input_tokens, m.output_tokens, m.cache_read_tokens,
             m.cache_create_5m_tokens, m.cache_create_1h_tokens
        FROM messages m
       WHERE m.session_id = %(sid)s AND m.type = 'assistant'
       ORDER BY m.timestamp, m.uuid
    """, {"sid": session_id})


def tool_uses(conn: psycopg.Connection, session_id: str) -> list[dict]:
    """Tool_use rows in time order, with `is_error` from the matching result.

    `is_error` is NULL when the row has no `tool_use_id` (migrated from the old
    SQLite DB) or no result came back (an interrupted call).
    """
    return fetch_all(conn, """
      SELECT u.timestamp, u.tool_name, u.target, u.message_uuid, u.tool_use_id,
             r.is_error
        FROM tool_calls u
        LEFT JOIN (
          SELECT tool_use_id, MAX(is_error) AS is_error
            FROM tool_calls
           WHERE session_id = %(sid)s AND tool_name = '_tool_result'
             AND tool_use_id IS NOT NULL
           GROUP BY tool_use_id
        ) r ON r.tool_use_id = u.tool_use_id
       WHERE u.session_id = %(sid)s AND u.tool_name <> '_tool_result'
       ORDER BY u.timestamp, u.id
    """, {"sid": session_id})


def branch_spans(conn: psycopg.Connection, session_id: str) -> list[dict]:
    """Per git branch (NULL included): first and last record time, oldest first."""
    return fetch_all(conn, """
      SELECT m.git_branch, MIN(m.timestamp) AS first_ts, MAX(m.timestamp) AS last_ts
        FROM messages m
       WHERE m.session_id = %(sid)s
       GROUP BY m.git_branch
       ORDER BY 2, 1
    """, {"sid": session_id})
