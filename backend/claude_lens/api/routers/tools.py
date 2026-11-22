"""`/api/tools/insights` (new in Claude Lens, phase 06). `/api/tools` stays in analytics."""
from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends

from ...db.queries import tool_insights as tq
from ..deps import DateRange, date_range, get_conn
from ..schemas_insights import ToolsInsights

router = APIRouter(tags=["tools"])


@router.get("/tools/insights", response_model=ToolsInsights)
def tools_insights(rng: DateRange = Depends(date_range),
                   conn: psycopg.Connection = Depends(get_conn)):
    """Per tool: calls, result tokens and error rate; the top 20 files, shell
    commands (Bash and PowerShell) and WebFetch domains.

    Result tokens and the error rate count only *linked* calls: those whose
    `tool_use_id` matches a result. Rows migrated from the old SQLite database
    have no `tool_use_id`; `linked_note` says how many calls are covered.
    """
    tools = tq.per_tool(conn, rng.since, rng.until)
    for t in tools:
        t["error_rate"] = t["errors"] / t["linked"] if t["linked"] else None
    calls = sum(t["calls"] for t in tools)
    linked = sum(t["linked"] for t in tools)
    note = (
        f"Error rates and result tokens cover the {linked:,} of {calls:,} tool calls that are "
        "linked to their result by tool_use_id. Calls copied from the old database have no id; "
        "running \"claude-lens scan --full\" once re-reads the transcripts still on disk and links them."
    )
    return {
        "tools": tools,
        "calls": calls,
        "linked": linked,
        "linked_note": note,
        "files": tq.top_files(conn, rng.since, rng.until),
        "commands": tq.top_commands(conn, rng.since, rng.until),
        "domains": tq.top_domains(conn, rng.since, rng.until),
    }
