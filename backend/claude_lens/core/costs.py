"""Cost rollups over per-model token rows.

`cost_by_key` / `cost_breakdown_by_key` are ported from `token_dashboard/server.py`
(`_cost_by_key`, `_cost_breakdown_by_key`); `overview_costs` is the overview
endpoint's rollup. Every cost goes through `pricing.cost_for`, so a model with
no rate (and no tier fallback) contributes nothing, and a key with no priced
model at all is absent: callers can tell "no cost data" from "$0".

For server-side sorting by cost (prompts, sessions), the same formula is also
available as SQL: `rates_param(pricing)` is bound as `%(rates)s`, `RATES_CTE`
goes in the WITH clause, `rate_joins(alias)` in FROM, and `cost_sql(alias)`
is the per-row USD expression (NULL when the model has no rate).
"""
from __future__ import annotations

from typing import Iterable, Mapping

from psycopg.types.json import Jsonb

from .pricing import cost_for

TOKEN_FIELDS = (
    "input_tokens", "output_tokens", "cache_read_tokens",
    "cache_create_5m_tokens", "cache_create_1h_tokens",
)
BREAKDOWN_KEYS = ("input", "output", "cache_read", "cache_create_5m", "cache_create_1h")
# Same order as pricing._tier_from_name: the first tier named in the model wins.
TIERS = ("fable", "mythos", "opus", "sonnet", "haiku")


def usage_of(row: Mapping) -> dict:
    """The five token counts of a row, with NULLs as 0."""
    return {k: int(row.get(k) or 0) for k in TOKEN_FIELDS}


def cost_by_key(model_rows: Iterable[Mapping], key: str, pricing: dict) -> dict:
    """Sum per-model estimated USD into {key_value: cost}."""
    costs: dict = {}
    for m in model_rows:
        c = cost_for(m["model"], usage_of(m), pricing)
        if c["usd"] is not None:
            costs[m[key]] = costs.get(m[key], 0.0) + c["usd"]
    return costs


def cost_breakdown_by_key(model_rows: Iterable[Mapping], key: str, pricing: dict) -> dict:
    """Sum per-model breakdown USD into {key_value: {input, output, cache_read,
    cache_create_5m, cache_create_1h}}."""
    out: dict = {}
    for m in model_rows:
        c = cost_for(m["model"], usage_of(m), pricing)
        if c["usd"] is None:
            continue
        bd = out.setdefault(m[key], dict.fromkeys(BREAKDOWN_KEYS, 0.0))
        for k, v in c["breakdown"].items():
            bd[k] += v
    return out


def overview_costs(model_rows: Iterable[Mapping], pricing: dict) -> dict:
    """The overview's cost fields, summed over per-model rows (rounded to 4 dp)."""
    total = 0.0
    bd_sum = dict.fromkeys(BREAKDOWN_KEYS, 0.0)
    for m in model_rows:
        c = cost_for(m["model"], usage_of(m), pricing)
        if c["usd"] is None:
            continue
        total += c["usd"]
        for k in BREAKDOWN_KEYS:
            bd_sum[k] += c["breakdown"].get(k, 0.0)
    return {
        "cost_usd": round(total, 4),
        "cost_input_usd": round(bd_sum["input"], 4),
        "cost_output_usd": round(bd_sum["output"], 4),
        "cost_cache_read_usd": round(bd_sum["cache_read"], 4),
        "cost_cache_create_5m_usd": round(bd_sum["cache_create_5m"], 4),
        "cost_cache_create_1h_usd": round(bd_sum["cache_create_1h"], 4),
        "cost_cache_create_usd": round(bd_sum["cache_create_5m"] + bd_sum["cache_create_1h"], 4),
    }


def turn_cost(row: Mapping, pricing: dict, ndigits: int = 6) -> dict:
    """Per-turn cost fields for one assistant row, or {} when its model has no rate."""
    c = cost_for(row.get("model"), usage_of(row), pricing)
    if c["usd"] is None:
        return {}
    bd = c["breakdown"]
    return {
        "cost_input_usd": round(bd["input"], ndigits),
        "cost_output_usd": round(bd["output"], ndigits),
        "cost_cache_read_usd": round(bd["cache_read"], ndigits),
        "cost_cache_create_5m_usd": round(bd["cache_create_5m"], ndigits),
        "cost_cache_create_1h_usd": round(bd["cache_create_1h"], ndigits),
        "estimated_cost_usd": round(c["usd"], ndigits),
    }


# --------------------------------------------------------------------------
# the same formula in SQL, for ORDER BY cost
# --------------------------------------------------------------------------

def rates_param(pricing: dict) -> Jsonb:
    """Exact-model rows (tier NULL) plus tier-fallback rows (model NULL)."""
    rows = []
    for model, r in pricing.get("models", {}).items():
        rows.append({"model": model, "tier": None, **{k: r[k] for k in BREAKDOWN_KEYS}})
    for tier, r in pricing.get("tier_fallback", {}).items():
        rows.append({"model": None, "tier": tier, **{k: r[k] for k in BREAKDOWN_KEYS}})
    return Jsonb(rows)


RATES_CTE = (
    "rates AS (SELECT * FROM jsonb_to_recordset(%(rates)s) AS r("
    "model text, tier text, input float8, output float8, cache_read float8,"
    " cache_create_5m float8, cache_create_1h float8))"
)


def _tier_sql(alias: str) -> str:
    whens = " ".join(f"WHEN strpos(lower({alias}.model), '{t}') > 0 THEN '{t}'" for t in TIERS)
    return f"(CASE {whens} END)"


def rate_joins(alias: str) -> str:
    """LEFT JOINs that bring in `{alias}_rm` (exact model) and `{alias}_rt` (tier) rates."""
    return (
        f" LEFT JOIN rates {alias}_rm ON {alias}_rm.model = {alias}.model"
        f" LEFT JOIN rates {alias}_rt ON {alias}_rt.model IS NULL"
        f" AND {alias}_rt.tier = {_tier_sql(alias)}"
    )


def cost_sql(alias: str) -> str:
    """Per-row USD for `{alias}`'s five token columns; NULL when no rate applies."""
    parts = []
    for col, rate in zip(TOKEN_FIELDS, BREAKDOWN_KEYS):
        parts.append(f"COALESCE({alias}_rm.{rate}, {alias}_rt.{rate}) * {alias}.{col}")
    return "((" + " + ".join(parts) + ") / 1000000.0)"
