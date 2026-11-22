import pytest

from claude_lens.core.pricing import (
    DEFAULT_PRICING_PATH, _tier_from_name, cost_for, format_for_user, load_pricing,
)


@pytest.fixture(scope="module")
def pricing():
    return load_pricing(DEFAULT_PRICING_PATH)


def _u(**kw):
    base = {
        "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0,
        "cache_create_5m_tokens": 0, "cache_create_1h_tokens": 0,
    }
    base.update(kw)
    return base


def test_default_path_is_backend_pricing_json():
    assert DEFAULT_PRICING_PATH.name == "pricing.json"
    assert DEFAULT_PRICING_PATH.parent.joinpath("pyproject.toml").is_file()
    assert load_pricing() == load_pricing(DEFAULT_PRICING_PATH)


def test_known_opus_input_cost(pricing):
    c = cost_for("claude-opus-4-7", _u(input_tokens=1_000_000), pricing)
    assert c["usd"] == pytest.approx(5.00, abs=1e-4)
    assert c["estimated"] is False


def test_known_sonnet_output_cost(pricing):
    c = cost_for("claude-sonnet-4-6", _u(output_tokens=1_000_000), pricing)
    assert c["usd"] == pytest.approx(15.00, abs=1e-4)


def test_unknown_opus_falls_back(pricing):
    c = cost_for("claude-opus-9-9-experimental", _u(input_tokens=1_000_000), pricing)
    assert c["usd"] == pytest.approx(5.00, abs=1e-4)
    assert c["estimated"] is True


def test_known_fable_costs(pricing):
    c = cost_for("claude-fable-5", _u(
        input_tokens=1_000_000, output_tokens=1_000_000, cache_read_tokens=1_000_000,
    ), pricing)
    assert c["usd"] == pytest.approx(61.00, abs=1e-4)  # 10 + 50 + 1
    assert c["estimated"] is False


def test_unknown_fable_falls_back(pricing):
    c = cost_for("claude-fable-6-experimental", _u(input_tokens=1_000_000), pricing)
    assert c["usd"] == pytest.approx(10.00, abs=1e-4)
    assert c["estimated"] is True


def test_unknown_unparseable_returns_none(pricing):
    c = cost_for("custom-local-model", _u(input_tokens=9999), pricing)
    assert c["usd"] is None


def test_cache_read_cheaper_than_input(pricing):
    c_in = cost_for("claude-opus-4-7", _u(input_tokens=1_000_000), pricing)
    c_cr = cost_for("claude-opus-4-7", _u(cache_read_tokens=1_000_000), pricing)
    assert c_cr["usd"] < c_in["usd"]


@pytest.mark.parametrize("model, tier", [
    ("claude-opus-4-7", "opus"),
    ("Claude-Sonnet-5-5", "sonnet"),
    ("claude-haiku-5-5", "haiku"),
    ("claude-fable-5-2", "fable"),
    ("gpt-4", None),
    ("", None),
    (None, None),
])
def test_tier_from_name(model, tier):
    assert _tier_from_name(model) == tier


def test_api_plan_returns_raw(pricing):
    out = format_for_user(12.34, "api", pricing)
    assert out["display_usd"] == 12.34
    assert out["subscription_usd"] is None


def test_pro_plan_returns_subscription_subtitle(pricing):
    out = format_for_user(12.34, "pro", pricing)
    assert out["subscription_usd"] == 20
    assert "Pro" in out["subtitle"]
