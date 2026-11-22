"""Rule-based tips engine, ported from `token_dashboard/tips.py` to Postgres.

Four rule sets look at the last 7 days (relative to `today`, default now):
cache discipline, repeated targets (files and bash commands), right-sizing
short Opus turns, and outliers (huge tool results, subagent cost spikes).
A dismissed tip stays hidden for 14 days.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import psycopg

from ..db.queries.common import fetch_all, fetch_one

WINDOW = timedelta(days=7)


def _key(category: str, scope: str) -> str:
    return f"{category}:{scope}"


def _since(today: Optional[datetime]) -> datetime:
    today = today or datetime.now(timezone.utc)
    if today.tzinfo is None:
        today = today.replace(tzinfo=timezone.utc)
    return today - WINDOW


def dismissed_keys(conn: psycopg.Connection) -> set[str]:
    """Keys dismissed within the last 14 days (the old per-key `_is_dismissed`, in one query)."""
    rows = conn.execute(
        "SELECT tip_key FROM dismissed_tips WHERE dismissed_at > now() - interval '14 days'"
    ).fetchall()
    return {r[0] for r in rows}


def dismiss_tip(conn: psycopg.Connection, key: str) -> None:
    conn.execute(
        "INSERT INTO dismissed_tips (tip_key, dismissed_at) VALUES (%(k)s, now())"
        " ON CONFLICT (tip_key) DO UPDATE SET dismissed_at = EXCLUDED.dismissed_at",
        {"k": key},
    )


def _dismissed(conn, dismissed: Optional[set]) -> set:
    return dismissed_keys(conn) if dismissed is None else dismissed


def cache_discipline_tips(conn: psycopg.Connection, today: Optional[datetime] = None,
                          dismissed: Optional[set] = None) -> List[dict]:
    dismissed = _dismissed(conn, dismissed)
    rows = fetch_all(conn, """
      SELECT project_slug,
             COALESCE(SUM(cache_read_tokens), 0)::bigint AS cr,
             COALESCE(SUM(input_tokens + cache_create_5m_tokens + cache_create_1h_tokens), 0)::bigint
               AS rebuild
        FROM messages
       WHERE type = 'assistant' AND timestamp >= %(since)s
       GROUP BY project_slug
      HAVING SUM(cache_read_tokens)
             + SUM(input_tokens + cache_create_5m_tokens + cache_create_1h_tokens) > 100000
       ORDER BY project_slug
    """, {"since": _since(today)})
    out = []
    for row in rows:
        total = row["cr"] + row["rebuild"]
        hit = row["cr"] / total if total else 0
        if hit >= 0.40:
            continue
        key = _key("cache", row["project_slug"])
        if key in dismissed:
            continue
        out.append({
            "key": key,
            "category": "cache",
            "title": f"Low cache hit rate in {row['project_slug']}",
            "body": f"Cache hit rate is {hit*100:.0f}% over the last 7 days. Sessions that restart context frequently rebuild cache. Consider longer-lived sessions or fewer context resets.",
            "scope": row["project_slug"],
        })
    return out


def repeated_target_tips(conn: psycopg.Connection, today: Optional[datetime] = None,
                         dismissed: Optional[set] = None) -> List[dict]:
    dismissed = _dismissed(conn, dismissed)
    since = _since(today)
    out = []
    for row in fetch_all(conn, """
      SELECT target, COUNT(*) AS n, COUNT(DISTINCT session_id) AS sessions
        FROM tool_calls
       WHERE tool_name IN ('Read', 'Edit', 'Write') AND timestamp >= %(since)s
       GROUP BY target HAVING COUNT(*) > 10
       ORDER BY n DESC, target
       LIMIT 10
    """, {"since": since}):
        key = _key("repeat-file", row["target"] or "?")
        if key in dismissed:
            continue
        out.append({
            "key": key, "category": "repeat-file",
            "title": f"{row['target']} read {row['n']} times",
            "body": f"This file was opened {row['n']} times across {row['sessions']} sessions in the past 7 days. A summary in CLAUDE.md or one read per session would avoid repeats.",
            "scope": row["target"],
        })
    for row in fetch_all(conn, """
      SELECT target, COUNT(*) AS n
        FROM tool_calls
       WHERE tool_name = 'Bash' AND timestamp >= %(since)s
       GROUP BY target HAVING COUNT(*) > 15
       ORDER BY n DESC, target
       LIMIT 10
    """, {"since": since}):
        key = _key("repeat-bash", row["target"] or "?")
        if key in dismissed:
            continue
        out.append({
            "key": key, "category": "repeat-bash",
            "title": f"`{row['target']}` ran {row['n']} times",
            "body": f"This bash command ran {row['n']} times in the past 7 days. Consider a watch flag or shell alias.",
            "scope": row["target"],
        })
    return out


def right_size_tips(conn: psycopg.Connection, today: Optional[datetime] = None,
                    dismissed: Optional[set] = None) -> List[dict]:
    dismissed = _dismissed(conn, dismissed)
    row = fetch_one(conn, """
      SELECT COUNT(*) AS n,
             COALESCE(SUM(input_tokens + cache_create_5m_tokens + cache_create_1h_tokens), 0)::bigint
               AS in_tok,
             COALESCE(SUM(output_tokens), 0)::bigint AS out_tok
        FROM messages
       WHERE type = 'assistant' AND strpos(model, 'opus') > 0
         AND output_tokens < 500 AND NOT is_sidechain
         AND timestamp >= %(since)s
    """, {"since": _since(today)})
    if not row or row["n"] < 10:
        return []
    api_opus = (row["in_tok"] * 15 + row["out_tok"] * 75) / 1_000_000
    api_sonnet = (row["in_tok"] * 3 + row["out_tok"] * 15) / 1_000_000
    savings = api_opus - api_sonnet
    if savings < 1.0:
        return []
    key = _key("right-size", "opus-short-turns-7d")
    if key in dismissed:
        return []
    return [{
        "key": key, "category": "right-size",
        "title": f"{row['n']} short Opus turns might fit on Sonnet",
        "body": f"Opus turns under 500 output tokens cost ~${api_opus:.2f} in the last 7 days. Sonnet would have cost ~${api_sonnet:.2f} (savings ~${savings:.2f}).",
        "scope": "opus-short-turns-7d",
    }]


def outlier_tips(conn: psycopg.Connection, today: Optional[datetime] = None,
                 dismissed: Optional[set] = None) -> List[dict]:
    dismissed = _dismissed(conn, dismissed)
    since = _since(today)
    out = []
    big = fetch_one(conn, """
      SELECT COUNT(*) AS n, AVG(result_tokens)::float8 AS avg_t
        FROM tool_calls
       WHERE tool_name = '_tool_result' AND result_tokens > 50000 AND timestamp >= %(since)s
    """, {"since": since})
    if big and big["n"] >= 5:
        key = _key("tool-bloat", "result-50k+")
        if key not in dismissed:
            out.append({
                "key": key, "category": "tool-bloat",
                "title": f"{big['n']} tool results over 50k tokens this week",
                "body": f"Average size is {int(big['avg_t']):,} tokens. Pipe long Bash output to head/tail and ask for narrower file reads.",
                "scope": "result-50k+",
            })
    for row in fetch_all(conn, """
      SELECT agent_id, COUNT(*) AS n,
             AVG(input_tokens + output_tokens)::float8 AS mean_t,
             MAX(input_tokens + output_tokens) AS max_t
        FROM messages
       WHERE is_sidechain AND agent_id IS NOT NULL AND timestamp >= %(since)s
       GROUP BY agent_id HAVING COUNT(*) >= 10
       ORDER BY agent_id
    """, {"since": since}):
        max_t = row["max_t"] or 0
        if max_t > 6 * (row["mean_t"] or 1) and max_t > 50_000:
            key = _key("subagent-outlier", row["agent_id"])
            if key in dismissed:
                continue
            out.append({
                "key": key, "category": "subagent-outlier",
                "title": f"Subagent {row['agent_id']} has cost outliers",
                "body": f"Largest invocation used {int(max_t):,} tokens vs mean {int(row['mean_t']):,}. Worth checking what those did differently.",
                "scope": row["agent_id"],
            })
    return out


def all_tips(conn: psycopg.Connection, today: Optional[datetime] = None) -> List[dict]:
    dismissed = dismissed_keys(conn)
    return [
        *cache_discipline_tips(conn, today, dismissed),
        *repeated_target_tips(conn, today, dismissed),
        *right_size_tips(conn, today, dismissed),
        *outlier_tips(conn, today, dismissed),
    ]
