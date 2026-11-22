"""Tips engine on Postgres (ported from tests/test_tips.py, plus the 14-day expiry)."""
from datetime import datetime, timezone

from claude_lens.core.tips import (
    all_tips, cache_discipline_tips, dismiss_tip, dismissed_keys, outlier_tips,
    repeated_target_tips, right_size_tips,
)
from helpers import insert_messages, insert_tools

TODAY = datetime(2026, 4, 19, tzinfo=timezone.utc)


def _cache_row(ts, project, cache_read, cache_create, uuid=None):
    return dict(uuid=uuid or f"uuid-{project}-{ts}", session_id="s", project_slug=project,
                timestamp=ts, model="claude-opus-4-7", input_tokens=100, output_tokens=100,
                cache_read_tokens=cache_read, cache_create_5m_tokens=cache_create)


def test_low_cache_hit_emits_tip(db):
    insert_messages(db, [_cache_row("2026-04-15T00:00:00Z", "projX", 10, 1_000_000)])
    tips = cache_discipline_tips(db, TODAY)
    assert [t["category"] for t in tips] == ["cache"]
    assert tips[0]["key"] == "cache:projX" and "0%" in tips[0]["body"]


def test_healthy_cache_no_tip(db):
    insert_messages(db, [_cache_row(f"2026-04-15T00:00:0{i}Z", "projY", 1_000_000, 50)
                         for i in range(10)])
    assert cache_discipline_tips(db, TODAY) == []


def test_old_activity_is_outside_the_window(db):
    insert_messages(db, [_cache_row("2026-04-01T00:00:00Z", "projX", 10, 1_000_000)])
    assert cache_discipline_tips(db, TODAY) == []


def test_repeated_file_and_bash_emit_tips(db):
    insert_messages(db, [dict(uuid="m1", session_id="s1", timestamp="2026-04-15T00:00:00Z",
                              model="claude-opus-4-7")])
    insert_tools(db, [dict(message_uuid="m1", session_id="s1", tool_name="Read",
                           target="src/Root.tsx", timestamp="2026-04-15T00:00:00Z")] * 15
                 + [dict(message_uuid="m1", session_id="s1", tool_name="Bash",
                         target="npm run lint", timestamp="2026-04-15T00:00:00Z")] * 20)
    tips = repeated_target_tips(db, TODAY)
    by_cat = {t["category"]: t for t in tips}
    assert set(by_cat) == {"repeat-file", "repeat-bash"}
    assert by_cat["repeat-file"]["title"] == "src/Root.tsx read 15 times"
    assert "across 1 sessions" in by_cat["repeat-file"]["body"]
    assert by_cat["repeat-bash"]["title"] == "`npm run lint` ran 20 times"


def test_short_opus_turns_flagged(db):
    insert_messages(db, [dict(uuid=f"a{i}", session_id="s", timestamp="2026-04-18T00:00:00Z",
                              model="claude-opus-4-7", input_tokens=1_000_000, output_tokens=200)
                         for i in range(10)])
    tips = right_size_tips(db, TODAY)
    assert [t["category"] for t in tips] == ["right-size"]
    assert tips[0]["title"] == "10 short Opus turns might fit on Sonnet"


def test_sidechain_opus_turns_not_flagged(db):
    insert_messages(db, [dict(uuid=f"a{i}", session_id="s", timestamp="2026-04-18T00:00:00Z",
                              model="claude-opus-4-7", input_tokens=1_000_000, output_tokens=200,
                              is_sidechain=True)
                         for i in range(10)])
    assert right_size_tips(db, TODAY) == []


def test_giant_tool_result_flagged(db):
    insert_messages(db, [dict(uuid=f"u{i}", session_id="s", type="user",
                              timestamp="2026-04-18T00:00:00Z") for i in range(20)])
    insert_tools(db, [dict(message_uuid=f"u{i}", session_id="s", tool_name="_tool_result",
                           target="tu", result_tokens=100_000, timestamp="2026-04-18T00:00:00Z")
                      for i in range(20)])
    tips = outlier_tips(db, TODAY)
    assert [t["category"] for t in tips] == ["tool-bloat"]
    assert "100,000 tokens" in tips[0]["body"]


def test_subagent_outlier_flagged(db):
    rows = [dict(uuid=f"a{i}", session_id="s", timestamp="2026-04-18T00:00:00Z",
                 is_sidechain=True, agent_id="agent-7", input_tokens=1000) for i in range(19)]
    rows.append(dict(uuid="big", session_id="s", timestamp="2026-04-18T00:00:00Z",
                     is_sidechain=True, agent_id="agent-7", input_tokens=200_000))
    insert_messages(db, rows)
    tips = outlier_tips(db, TODAY)
    assert [t["key"] for t in tips] == ["subagent-outlier:agent-7"]


def test_dismissed_tip_doesnt_reappear(db):
    insert_messages(db, [_cache_row("2026-04-15T00:00:00Z", "projZ", 10, 1_000_000)])
    before = cache_discipline_tips(db, TODAY)
    assert before
    dismiss_tip(db, before[0]["key"])
    dismiss_tip(db, before[0]["key"])  # idempotent (ON CONFLICT)
    db.commit()
    assert cache_discipline_tips(db, TODAY) == []
    assert all_tips(db, TODAY) == []


def test_dismissal_expires_after_14_days(db):
    insert_messages(db, [_cache_row("2026-04-15T00:00:00Z", "projZ", 10, 1_000_000)])
    db.execute("INSERT INTO dismissed_tips VALUES ('cache:projZ', now() - interval '15 days'),"
               " ('other:x', now() - interval '13 days')")
    db.commit()
    assert dismissed_keys(db) == {"other:x"}
    assert [t["key"] for t in cache_discipline_tips(db, TODAY)] == ["cache:projZ"]


def test_all_tips_combines_rule_sets(db):
    insert_messages(db, [_cache_row("2026-04-15T00:00:00Z", "projX", 10, 1_000_000)]
                    + [dict(uuid=f"a{i}", session_id="s", timestamp="2026-04-18T00:00:00Z",
                            model="claude-opus-4-7", input_tokens=1_000_000, output_tokens=200)
                       for i in range(10)])
    # the opus rows (project "p", no cache reads) also trip the cache rule
    keys = [t["key"] for t in all_tips(db, TODAY)]
    assert keys == ["cache:p", "cache:projX", "right-size:opus-short-turns-7d"]
