"""Offline units of the API layer: pricing loader, costs, lockout, client IP, range parsing."""
import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from claude_lens.api.deps import client_ip, parse_instant
from claude_lens.api.security import LoginLockout
from claude_lens.config import Settings
from claude_lens.core.costs import (
    cost_breakdown_by_key, cost_by_key, overview_costs, rates_param, turn_cost,
)
from claude_lens.core.pricing import load_pricing, make_pricing_loader

PRICING = load_pricing()


# --- pricing loader (ported from tests/test_server.py) ------------------------------

def _write(path, models, bump):
    import json
    path.write_text(json.dumps({"models": models}), encoding="utf-8")
    st = path.stat()  # force a distinct mtime regardless of FS timestamp resolution
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + bump))


def test_loader_picks_up_edits_without_restart(tmp_path):
    p = tmp_path / "pricing.json"
    _write(p, {"a": 1}, 1_000_000)
    get = make_pricing_loader(p)
    assert get()["models"] == {"a": 1}
    _write(p, {"a": 1, "b": 2}, 2_000_000)
    assert get()["models"] == {"a": 1, "b": 2}


def test_loader_keeps_last_good_copy_when_file_is_invalid(tmp_path):
    p = tmp_path / "pricing.json"
    _write(p, {"a": 1}, 1_000_000)
    get = make_pricing_loader(p)
    get()
    p.write_text("{ not json", encoding="utf-8")
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000))
    assert get()["models"] == {"a": 1}


def test_loader_raises_if_never_loaded_and_invalid(tmp_path):
    p = tmp_path / "pricing.json"
    p.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ValueError):
        make_pricing_loader(p)()


# --- costs ----------------------------------------------------------------------------

ROWS = [
    {"k": "x", "model": "claude-opus-4-7", "input_tokens": 1_000_000, "output_tokens": 0,
     "cache_read_tokens": 0, "cache_create_5m_tokens": 0, "cache_create_1h_tokens": 0},
    {"k": "x", "model": "claude-haiku-4-5", "input_tokens": 0, "output_tokens": 1_000_000,
     "cache_read_tokens": 0, "cache_create_5m_tokens": 0, "cache_create_1h_tokens": 0},
    {"k": "y", "model": "unknown", "input_tokens": 5, "output_tokens": 5,
     "cache_read_tokens": 0, "cache_create_5m_tokens": 0, "cache_create_1h_tokens": 0},
]


def test_cost_by_key_skips_unpriced_keys():
    assert cost_by_key(ROWS, "k", PRICING) == {"x": pytest.approx(5.0 + 5.0)}


def test_cost_breakdown_by_key():
    bd = cost_breakdown_by_key(ROWS, "k", PRICING)
    assert set(bd) == {"x"}
    assert bd["x"]["input"] == pytest.approx(5.0) and bd["x"]["output"] == pytest.approx(5.0)


def test_overview_costs():
    c = overview_costs(ROWS, PRICING)
    assert c["cost_usd"] == 10.0 and c["cost_input_usd"] == 5.0 and c["cost_output_usd"] == 5.0
    assert c["cost_cache_create_usd"] == 0.0


def test_turn_cost_unpriced_is_empty():
    assert turn_cost({"model": "gpt-x", "input_tokens": 1}, PRICING) == {}
    assert turn_cost({"model": "claude-opus-9", "output_tokens": 1_000_000}, PRICING)[
        "estimated_cost_usd"] == 25.0  # tier fallback


def test_rates_param_has_models_and_tiers():
    rows = rates_param(PRICING).obj
    assert any(r["model"] == "claude-opus-4-7" and r["tier"] is None for r in rows)
    assert any(r["model"] is None and r["tier"] == "opus" for r in rows)


# --- lockout --------------------------------------------------------------------------

def test_lockout_window():
    now = [1000.0]
    lock = LoginLockout(max_failures=5, window=900, clock=lambda: now[0])
    key = ("1.2.3.4", "admin")
    for _ in range(4):
        lock.record_failure(key)
    assert lock.retry_after(key) == 0
    lock.record_failure(key)
    assert 0 < lock.retry_after(key) <= 901
    now[0] += 901  # all five age out
    assert lock.retry_after(key) == 0
    lock.record_failure(key)
    lock.reset(key)
    assert lock.retry_after(key) == 0


def test_lockout_keys_are_independent():
    lock = LoginLockout(max_failures=1)
    lock.record_failure(("a", "u"))
    assert lock.retry_after(("a", "u")) > 0
    assert lock.retry_after(("b", "u")) == 0 and lock.retry_after(("a", "v")) == 0


# --- client ip --------------------------------------------------------------------------

def _req(peer, xff=None):
    headers = {"x-forwarded-for": xff} if xff else {}
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers)


def test_client_ip_ignores_xff_unless_trusted():
    untrusted = Settings.from_env({})
    trusted = Settings.from_env({"TRUST_PROXY": "true"})
    assert client_ip(_req("10.0.0.2", "6.6.6.6"), untrusted) == "10.0.0.2"
    assert client_ip(_req("10.0.0.2", "6.6.6.6, 203.0.113.9"), trusted) == "203.0.113.9"
    assert client_ip(_req("10.0.0.2"), trusted) == "10.0.0.2"


# --- range parsing ------------------------------------------------------------------------

def test_parse_instant():
    assert parse_instant(None, "since") is None
    assert parse_instant("", "since") is None
    assert parse_instant("2026-04-10T00:00:00Z", "since").isoformat() == "2026-04-10T00:00:00+00:00"
    assert parse_instant("2026-04-10", "since").isoformat() == "2026-04-10T00:00:00+00:00"
    assert parse_instant("2026-04-10T05:00:00+05:00", "s").utcoffset().total_seconds() == 18000
    with pytest.raises(HTTPException) as e:
        parse_instant("yesterday", "since")
    assert e.value.status_code == 422
