"""Pricing table + plan-aware cost formatting.

Ported from `token_dashboard/pricing.py`, plus `make_pricing_loader` from
`token_dashboard/server.py`. The plan getter/setter lives in
`db/queries/settings.py` (the Postgres `settings` table).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Callable, Optional, Union

# backend/pricing.json, next to pyproject.toml
DEFAULT_PRICING_PATH = Path(__file__).resolve().parents[2] / "pricing.json"


def load_pricing(path: Union[str, Path] = DEFAULT_PRICING_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def make_pricing_loader(path: Union[str, Path] = DEFAULT_PRICING_PATH) -> Callable[[], dict]:
    """Return a callable that yields the current pricing.json contents.

    Re-reads the file only when its mtime changes, so edits apply on the next
    request without a restart. If the file is briefly unreadable or invalid
    (e.g. mid-save), the last good copy is served instead. Thread-safe.
    """
    path = Path(path)
    state: dict = {"mtime": None, "data": None}
    lock = threading.Lock()

    def get() -> dict:
        with lock:
            try:
                mtime = path.stat().st_mtime_ns
                if mtime != state["mtime"] or state["data"] is None:
                    state["data"] = load_pricing(path)
                    state["mtime"] = mtime
            except (OSError, ValueError):
                if state["data"] is None:
                    raise
            return state["data"]

    return get


def _tier_from_name(model: str) -> Optional[str]:
    m = (model or "").lower()
    for tier in ("fable", "mythos", "opus", "sonnet", "haiku"):
        if tier in m:
            return tier
    return None


def cost_for(model: str, usage: dict, pricing: dict) -> dict:
    """Return {usd, estimated, breakdown}. usd=None when no tier match."""
    rates = pricing["models"].get(model)
    estimated = False
    if rates is None:
        tier = _tier_from_name(model or "")
        if tier and tier in pricing["tier_fallback"]:
            rates = pricing["tier_fallback"][tier]
            estimated = True
        else:
            return {"usd": None, "estimated": True, "breakdown": {}}
    bd = {
        "input":           usage["input_tokens"]            * rates["input"]           / 1_000_000,
        "output":          usage["output_tokens"]           * rates["output"]          / 1_000_000,
        "cache_read":      usage["cache_read_tokens"]       * rates["cache_read"]      / 1_000_000,
        "cache_create_5m": usage["cache_create_5m_tokens"]  * rates["cache_create_5m"] / 1_000_000,
        "cache_create_1h": usage["cache_create_1h_tokens"]  * rates["cache_create_1h"] / 1_000_000,
    }
    return {"usd": round(sum(bd.values()), 6), "estimated": estimated, "breakdown": bd}


def format_for_user(api_cost_usd: float, plan: str, pricing: dict) -> dict:
    p = pricing["plans"].get(plan, pricing["plans"]["api"])
    if plan == "api" or p["monthly"] == 0:
        return {"display_usd": api_cost_usd, "subtitle": None, "subscription_usd": None}
    return {
        "display_usd":      api_cost_usd,
        "subtitle":         f"You pay ${p['monthly']}/mo on {p['label']}",
        "subscription_usd": p["monthly"],
    }
