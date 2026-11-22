"""Shapes one session's raw rows into `/api/sessions/{id}/insights` (pure, no DB).

"Tokens" for a subagent means core tokens (input + output + cache writes), as
elsewhere in Claude Lens; cache reads are left out because they dwarf the rest.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Optional

from .costs import turn_cost

FILE_ACTIONS = ("Read", "Edit", "Write")
SUBAGENT_TOOLS = ("Task", "Agent")
MAX_FILES = 100


def context_tokens(r: Mapping) -> int:
    """What the model saw on this turn: fresh input + cache reads + cache writes."""
    return (int(r["input_tokens"]) + int(r["cache_read_tokens"])
            + int(r["cache_create_5m_tokens"]) + int(r["cache_create_1h_tokens"]))


def core_tokens(r: Mapping) -> int:
    return (int(r["input_tokens"]) + int(r["output_tokens"])
            + int(r["cache_create_5m_tokens"]) + int(r["cache_create_1h_tokens"]))


def _cost(r: Mapping, pricing: dict) -> Optional[float]:
    return turn_cost(r, pricing).get("estimated_cost_usd") if r.get("model") else None


def build_insights(turns: Iterable[Mapping], tools: Iterable[Mapping],
                   branch_rows: Iterable[Mapping], pricing: dict) -> dict:
    turns = list(turns)
    tools = list(tools)
    branch_rows = list(branch_rows)

    context_growth = []
    models: dict[str, dict] = {}
    agents: dict[str, dict] = {}
    session_cost = 0.0
    for r in turns:
        cost = _cost(r, pricing)
        session_cost += cost or 0.0
        context_growth.append({
            "uuid": r["uuid"],
            "ts": r["timestamp"],
            "context_tokens": context_tokens(r),
            "output_tokens": int(r["output_tokens"]),
            "cost": cost,
            "model": r["model"],
            "is_sidechain": bool(r["is_sidechain"]),
        })
        m = models.setdefault(r["model"] or "unknown", {"turns": 0, "cost": None})
        m["turns"] += 1
        if cost is not None:
            m["cost"] = (m["cost"] or 0.0) + cost
        if r["is_sidechain"]:
            a = agents.setdefault(r["agent_id"] or "unknown", {
                "turns": 0, "tokens": 0, "cost": None,
                "first_ts": r["timestamp"], "last_ts": r["timestamp"],
            })
            a["turns"] += 1
            a["tokens"] += core_tokens(r)
            if cost is not None:
                a["cost"] = (a["cost"] or 0.0) + cost
            a["first_ts"] = min(a["first_ts"], r["timestamp"])
            a["last_ts"] = max(a["last_ts"], r["timestamp"])

    timeline = []
    files: dict[str, dict] = {}
    invocations = []
    for t in tools:
        err = t["is_error"]
        timeline.append({
            "ts": t["timestamp"],
            "tool_name": t["tool_name"],
            "target": t["target"],
            "is_error": None if err is None else bool(err),
            "message_uuid": t["message_uuid"],
        })
        if t["tool_name"] in FILE_ACTIONS and t["target"]:
            f = files.setdefault(t["target"], {"path": t["target"], "read": 0, "edit": 0,
                                               "write": 0, "total": 0})
            f[t["tool_name"].lower()] += 1
            f["total"] += 1
        if t["tool_name"] in SUBAGENT_TOOLS:
            invocations.append({"ts": t["timestamp"], "subagent_type": t["target"],
                                "message_uuid": t["message_uuid"]})

    file_rows = sorted(files.values(), key=lambda f: (-f["total"], f["path"]))

    subagents = [
        {"agent_id": aid, **{k: (round(v, 6) if k == "cost" and v is not None else v)
                             for k, v in a.items()}}
        for aid, a in agents.items()
    ]
    subagents.sort(key=lambda a: (a["first_ts"], a["agent_id"]))

    first = min((b["first_ts"] for b in branch_rows), default=None)
    last = max((b["last_ts"] for b in branch_rows), default=None)
    return {
        "context_growth": context_growth,
        "tool_timeline": timeline,
        "subagents": subagents,
        "subagent_invocations": invocations,
        "files": file_rows[:MAX_FILES],
        "files_total": len(file_rows),
        "branches": [b["git_branch"] for b in branch_rows if b["git_branch"]],
        "models": sorted(
            ({"model": k, "turns": v["turns"],
              "cost": round(v["cost"], 6) if v["cost"] is not None else None}
             for k, v in models.items()),
            key=lambda m: (-(m["cost"] or 0), -m["turns"], m["model"]),
        ),
        "duration_s": (last - first).total_seconds() if first and last else None,
        "started": first,
        "ended": last,
        "cost_usd": round(session_cost, 6),
        "tool_calls_linked": sum(1 for t in tools if t["tool_use_id"]),
    }
