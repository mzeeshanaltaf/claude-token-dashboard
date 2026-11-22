"""Phase 06 pure helpers: streaks, CSV cells, session-insights shaping (no DB)."""
import csv
import io
from datetime import date, datetime, timedelta, timezone

from claude_lens.core.activity import streaks
from claude_lens.core.csv_export import (
    BOM, EXCEL_CELL_MAX, EXCEL_SAFE_UNITS, cell, csv_lines, excel_units,
)
from claude_lens.core.pricing import load_pricing
from claude_lens.core.session_insights import build_insights

D = date(2026, 6, 10)


def days(*offsets):
    return [D + timedelta(days=o) for o in offsets]


# --- streaks ----------------------------------------------------------------

def test_streaks_empty():
    assert streaks([], D) == (0, 0)


def test_current_streak_ends_today():
    assert streaks(days(-2, -1, 0), D) == (3, 3)


def test_current_streak_survives_an_idle_today():
    assert streaks(days(-3, -2, -1), D) == (3, 3)


def test_current_streak_broken_two_days_ago():
    assert streaks(days(-5, -4, -3, -2), D) == (0, 4)


def test_longest_is_the_best_run_anywhere():
    assert streaks(days(-10, -9, -8, -7, -3, -1, 0), D) == (2, 4)


def test_duplicates_and_future_days_ignored():
    assert streaks(days(0, 0, -1, 3, 4), D) == (2, 2)


# --- CSV --------------------------------------------------------------------

def test_cell_formats():
    assert cell(None) == ""
    assert cell(True) == "true"
    assert cell(datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)) == "2026-01-02T03:04:05Z"
    assert cell(date(2026, 1, 2)) == "2026-01-02"
    assert cell(1.23456789) == 1.234568
    assert cell(42) == 42


def test_cell_neutralises_formulas_but_not_numbers():
    assert cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert cell("@sum") == "'@sum"
    assert cell("-x") == "'-x"
    assert cell("plain") == "plain"
    assert cell(-5) == -5


def test_cell_truncates_to_excel_limit():
    out = cell("x" * 50_000)
    assert len(out) <= EXCEL_SAFE_UNITS and out.endswith("[truncated]")
    short = "x" * (EXCEL_SAFE_UNITS - 1)
    assert cell(short) == short  # fits: untouched


def test_cell_limit_counts_what_excel_counts():
    # A real 32,766-character prompt with 144 `"` still spilled into a second
    # Excel row: the import limit counts the escaped field and UTF-16 units.
    for text in ("😀" * 20_000, 'say "hi" ' * 4_000, "=" + "😀" * 20_000):
        out = cell(text)
        assert excel_units(out) <= EXCEL_SAFE_UNITS < EXCEL_CELL_MAX, text[:12]
        assert out.endswith("[truncated]")
    assert excel_units('a"b😀') == 1 + 2 + 1 + 2


def test_csv_lines_round_trip():
    text = "".join(csv_lines(("a", "b"), [{"a": 1, "b": 'he said "hi",\nbye'}, {"a": None}]))
    assert text.startswith(BOM)
    rows = list(csv.reader(io.StringIO(text[len(BOM):])))
    assert rows == [["a", "b"], ["1", 'he said "hi",\nbye'], ["", ""]]


# --- session insights -------------------------------------------------------

def _ts(minute):
    return datetime(2026, 6, 10, 12, minute, tzinfo=timezone.utc)


def _turn(uuid, minute, side=False, agent=None, **tok):
    base = dict(input_tokens=0, output_tokens=0, cache_read_tokens=0,
                cache_create_5m_tokens=0, cache_create_1h_tokens=0)
    base.update(tok)
    return dict(uuid=uuid, timestamp=_ts(minute), model="claude-haiku-4-5",
                is_sidechain=side, agent_id=agent, **base)


def test_build_insights_shapes():
    pricing = load_pricing()
    turns = [
        _turn("a1", 0, input_tokens=10, cache_read_tokens=1000, cache_create_5m_tokens=50,
              output_tokens=5),
        _turn("s1", 1, side=True, agent="ag1", input_tokens=100, output_tokens=20),
        _turn("s2", 2, side=True, agent="ag1", input_tokens=200, output_tokens=30),
        _turn("a2", 3, input_tokens=5, cache_read_tokens=2000, output_tokens=7),
    ]
    tools = [
        dict(timestamp=_ts(0), tool_name="Read", target="a.py", message_uuid="a1",
             tool_use_id="t1", is_error=0),
        dict(timestamp=_ts(0), tool_name="Agent", target="Explore", message_uuid="a1",
             tool_use_id="t2", is_error=None),
        dict(timestamp=_ts(1), tool_name="Edit", target="a.py", message_uuid="s1",
             tool_use_id=None, is_error=None),
        dict(timestamp=_ts(2), tool_name="Bash", target="ls", message_uuid="s2",
             tool_use_id="t3", is_error=1),
        dict(timestamp=_ts(3), tool_name="Write", target="b.py", message_uuid="a2",
             tool_use_id="t4", is_error=0),
    ]
    branches = [dict(git_branch="main", first_ts=_ts(0), last_ts=_ts(2)),
                dict(git_branch=None, first_ts=_ts(1), last_ts=_ts(3)),
                dict(git_branch="feat", first_ts=_ts(2), last_ts=_ts(3))]
    out = build_insights(turns, tools, branches, pricing)

    assert [p["context_tokens"] for p in out["context_growth"]] == [1060, 100, 200, 2005]
    assert [p["is_sidechain"] for p in out["context_growth"]] == [False, True, True, False]
    assert all(p["cost"] > 0 for p in out["context_growth"])

    assert [e["is_error"] for e in out["tool_timeline"]] == [False, None, None, True, False]
    assert out["tool_calls_linked"] == 4

    (agent,) = out["subagents"]
    assert agent["agent_id"] == "ag1" and agent["turns"] == 2 and agent["tokens"] == 350
    assert (agent["first_ts"], agent["last_ts"]) == (_ts(1), _ts(2))
    assert out["subagent_invocations"] == [
        {"ts": _ts(0), "subagent_type": "Explore", "message_uuid": "a1"}]

    assert out["files"][0] == {"path": "a.py", "read": 1, "edit": 1, "write": 0, "total": 2}
    assert out["files_total"] == 2
    assert out["branches"] == ["main", "feat"]
    assert out["models"] == [{"model": "claude-haiku-4-5", "turns": 4,
                              "cost": round(sum(p["cost"] for p in out["context_growth"]), 6)}]
    assert out["duration_s"] == 180
    assert abs(out["cost_usd"] - sum(p["cost"] for p in out["context_growth"])) < 1e-9


def test_build_insights_empty_session():
    out = build_insights([], [], [], load_pricing())
    assert out["context_growth"] == [] and out["duration_s"] is None and out["cost_usd"] == 0
