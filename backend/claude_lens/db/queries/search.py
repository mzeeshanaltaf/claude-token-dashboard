"""`/api/search`: prompts (full-text), sessions (title) and projects (name / slug).

Snippets mark each match with two private-use characters (U+E000 … U+E001)
instead of HTML, so the frontend renders highlights without injecting markup.
"""
from __future__ import annotations

import psycopg

from ...core.names import best_project_name
from .common import fetch_all, like_pattern

HL_START, HL_STOP = "", ""
# ts_headline options; quoted values may hold any character but `"`.
HEADLINE_OPTS = (
    f'StartSel="{HL_START}", StopSel="{HL_STOP}", MaxWords=28, MinWords=10, '
    'ShortWord=2, MaxFragments=2, FragmentDelimiter=" … "'
)


def search_prompts(conn: psycopg.Connection, q: str, limit: int) -> list[dict]:
    """User prompts matching `websearch_to_tsquery('english', q)`, best `ts_rank` first."""
    return fetch_all(conn, """
      WITH query AS (SELECT websearch_to_tsquery('english', %(q)s) AS tsq),
      hits AS (
        SELECT m.uuid, m.session_id, m.project_slug, m.timestamp, m.prompt_text,
               ts_rank(m.prompt_tsv, query.tsq) AS rank
          FROM messages m, query
         WHERE m.type = 'user' AND m.prompt_tsv @@ query.tsq
         ORDER BY rank DESC, m.timestamp DESC, m.uuid
         LIMIT %(limit)s
      )
      SELECT h.uuid AS user_uuid, h.session_id, h.project_slug, h.timestamp,
             h.rank::float8 AS rank,
             ts_headline('english', left(h.prompt_text, 100000), query.tsq, %(opts)s) AS snippet,
             t.title
        FROM hits h
        CROSS JOIN query
        LEFT JOIN session_titles t ON t.session_id = h.session_id
       ORDER BY h.rank DESC, h.timestamp DESC, h.uuid
    """, {"q": q, "limit": limit, "opts": HEADLINE_OPTS})


def search_sessions(conn: psycopg.Connection, q: str, limit: int) -> list[dict]:
    """Sessions whose title contains `q` (ILIKE), most recently active first.

    A plain join + GROUP BY, not a LATERAL subquery: a short `q` matches most
    titles, and per-title aggregates then cost one index scan each (a 1-letter
    query took over 60 s); the join lets the planner hash-join in one pass.
    """
    return fetch_all(conn, """
      WITH t AS (
        SELECT session_id, title FROM session_titles WHERE title ILIKE %(like)s
      )
      SELECT t.session_id, t.title, MIN(m.project_slug) AS project_slug,
             MIN(m.timestamp) AS started, MAX(m.timestamp) AS ended
        FROM t
        JOIN messages m ON m.session_id = t.session_id
       GROUP BY t.session_id, t.title
       ORDER BY ended DESC, t.session_id
       LIMIT %(limit)s
    """, {"like": like_pattern(q), "limit": limit})


def search_projects(conn: psycopg.Connection, q: str, limit: int) -> list[dict]:
    """Projects whose display name or slug contains `q` (case-insensitive).

    The display name is derived from the project's cwds (`core.names`), so it
    can't be matched in SQL: all (slug, cwd) pairs are read (a few hundred) and
    matched here; only the matches get the session count and last activity.
    """
    # A plain DISTINCT hash-aggregates ~3x faster than array_agg(DISTINCT ...).
    pairs = fetch_all(conn, "SELECT DISTINCT project_slug, cwd FROM messages")
    cwds: dict[str, list[str]] = {}
    for p in pairs:
        lst = cwds.setdefault(p["project_slug"], [])
        if p["cwd"] is not None:
            lst.append(p["cwd"])
    needle = q.casefold()
    # sorted cwds: the same input order as common.project_names (array_agg DISTINCT)
    names = {s: best_project_name(sorted(c), s) for s, c in cwds.items()}
    hits = [s for s, name in names.items()
            if needle in name.casefold() or needle in s.casefold()]
    if not hits:
        return []
    rows = fetch_all(conn, """
      SELECT m.project_slug, COUNT(DISTINCT m.session_id) AS sessions,
             MAX(m.timestamp) AS last_active
        FROM messages m
       WHERE m.project_slug = ANY(%(slugs)s)
       GROUP BY m.project_slug
       ORDER BY last_active DESC, m.project_slug
       LIMIT %(limit)s
    """, {"slugs": hits, "limit": limit})
    for r in rows:
        r["project_name"] = names[r["project_slug"]]
    return rows
