"""Query layer on Postgres (ported from tests/test_queries.py, plus pagination,
filters, cost sorting, timezone bucketing, settings and sync status)."""
from datetime import datetime

import pytest

from claude_lens.core.pricing import load_pricing
from claude_lens.db.queries import analytics, projects, prompts, sessions, settings, sync
from claude_lens.db.queries.common import PageRequest, like_pattern, project_names
from helpers import insert_messages, insert_tools

PRICING = load_pricing()


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@pytest.fixture
def seeded(db):
    insert_messages(db, [
        dict(uuid="u1", session_id="s1", project_slug="projA", type="user",
             timestamp="2026-04-10T00:00:00Z", prompt_text="big prompt", prompt_chars=10),
        dict(uuid="a1", parent_uuid="u1", session_id="s1", project_slug="projA",
             timestamp="2026-04-10T00:00:01Z", model="claude-opus-4-7",
             input_tokens=100, output_tokens=200, cache_read_tokens=300),
        dict(uuid="u2", session_id="s2", project_slug="projB", type="user",
             timestamp="2026-04-11T00:00:00Z", prompt_text="small", prompt_chars=5),
        dict(uuid="a2", parent_uuid="u2", session_id="s2", project_slug="projB",
             timestamp="2026-04-11T00:00:01Z", model="claude-sonnet-4-6",
             input_tokens=5, output_tokens=5),
    ])
    insert_tools(db, [
        dict(message_uuid="a1", session_id="s1", project_slug="projA", tool_name="Read",
             target="foo.py", timestamp="2026-04-10T00:00:01Z"),
        dict(message_uuid="a1", session_id="s1", project_slug="projA", tool_name="Bash",
             target="npm test", timestamp="2026-04-10T00:00:01Z"),
    ])
    return db


def test_overview_totals(seeded):
    t = analytics.overview_totals(seeded)
    assert (t["sessions"], t["projects"], t["turns"]) == (2, 2, 2)
    assert (t["input_tokens"], t["output_tokens"], t["cache_read_tokens"]) == (105, 205, 300)
    assert all(type(v) is int for v in t.values())


def test_overview_totals_empty_db(db):
    t = analytics.overview_totals(db)
    assert t["sessions"] == 0 and t["input_tokens"] == 0


def test_prompts_order_by_tokens(seeded):
    page = prompts.prompts_page(seeded, PageRequest(page_size=10), PRICING)
    assert page["total"] == 2
    assert [r["prompt_text"] for r in page["items"]] == ["big prompt", "small"]
    assert page["items"][0]["core_tokens"] == 300


def test_prompts_sort_recent(seeded):
    page = prompts.prompts_page(seeded, PageRequest(sort="recent"), PRICING)
    assert [r["prompt_text"] for r in page["items"]] == ["small", "big prompt"]
    page = prompts.prompts_page(seeded, PageRequest(sort="recent", order="asc"), PRICING)
    assert [r["prompt_text"] for r in page["items"]] == ["big prompt", "small"]


def test_prompts_carry_all_five_token_types(seeded):
    row = prompts.prompts_page(seeded, PageRequest(), PRICING)["items"][0]
    assert (row["input_tokens"], row["output_tokens"], row["cache_read_tokens"]) == (100, 200, 300)
    assert row["model"] == "claude-opus-4-7" and row["assistant_uuid"] == "a1"


def test_prompts_filters(seeded):
    assert prompts.prompts_page(seeded, PageRequest(), PRICING, q="BIG")["total"] == 1
    assert prompts.prompts_page(seeded, PageRequest(), PRICING, project="projB")["total"] == 1
    page = prompts.prompts_page(seeded, PageRequest(), PRICING, model="claude-sonnet-4-6")
    assert [r["prompt_text"] for r in page["items"]] == ["small"]
    assert prompts.prompts_page(seeded, PageRequest(), PRICING, q="%")["total"] == 0
    since = prompts.prompts_page(seeded, PageRequest(), PRICING, since=ts("2026-04-11T00:00:00Z"))
    assert [r["prompt_text"] for r in since["items"]] == ["small"]


def test_prompts_sort_by_cost_uses_full_turn(db):
    # p1: huge cache read, few core tokens; p2: modest output. Cost ranks them
    # differently from core tokens (opus: cache_read $0.5/M, output $25/M).
    insert_messages(db, [
        dict(uuid="u1", session_id="s", type="user", timestamp="2026-04-10T00:00:00Z",
             prompt_text="p1"),
        dict(uuid="a1", parent_uuid="u1", session_id="s", timestamp="2026-04-10T00:00:01Z",
             model="claude-opus-4-7", output_tokens=10, cache_read_tokens=10_000_000),
        dict(uuid="u2", session_id="s", type="user", timestamp="2026-04-10T00:01:00Z",
             prompt_text="p2"),
        dict(uuid="a2", parent_uuid="u2", session_id="s", timestamp="2026-04-10T00:01:01Z",
             model="claude-opus-4-7", output_tokens=1000),
        dict(uuid="u3", session_id="s", type="user", timestamp="2026-04-10T00:02:00Z",
             prompt_text="p3 unpriced"),
        dict(uuid="a3", parent_uuid="u3", session_id="s", timestamp="2026-04-10T00:02:01Z",
             model="gpt-x", output_tokens=999_999),
    ])
    by_tokens = prompts.prompts_page(db, PageRequest(sort="tokens"), PRICING)["items"]
    assert [r["prompt_text"] for r in by_tokens] == ["p3 unpriced", "p2", "p1"]
    by_cost = prompts.prompts_page(db, PageRequest(sort="cost"), PRICING)["items"]
    assert [r["prompt_text"] for r in by_cost] == ["p1", "p2", "p3 unpriced"]  # NULLs last
    asc = prompts.prompts_page(db, PageRequest(sort="cost", order="asc"), PRICING)["items"]
    assert [r["prompt_text"] for r in asc] == ["p2", "p1", "p3 unpriced"]


def test_prompts_pagination(db):
    rows = []
    for i in range(5):
        rows += [
            dict(uuid=f"u{i}", session_id="s", type="user",
                 timestamp=f"2026-04-10T00:0{i}:00Z", prompt_text=f"prompt {i}"),
            dict(uuid=f"a{i}", parent_uuid=f"u{i}", session_id="s",
                 timestamp=f"2026-04-10T00:0{i}:01Z", model="claude-opus-4-7",
                 output_tokens=100 * (i + 1)),
        ]
    insert_messages(db, rows)
    p1 = prompts.prompts_page(db, PageRequest(page=1, page_size=2), PRICING)
    p3 = prompts.prompts_page(db, PageRequest(page=3, page_size=2), PRICING)
    p9 = prompts.prompts_page(db, PageRequest(page=9, page_size=2), PRICING)
    assert (p1["total"], p1["page"], p1["page_size"]) == (5, 1, 2)
    assert [r["prompt_text"] for r in p1["items"]] == ["prompt 4", "prompt 3"]
    assert [r["prompt_text"] for r in p3["items"]] == ["prompt 0"]
    assert p9["items"] == [] and p9["total"] == 5


def test_page_request_validation():
    with pytest.raises(ValueError):
        PageRequest(page=0)
    with pytest.raises(ValueError):
        PageRequest(page_size=201)
    with pytest.raises(ValueError):
        PageRequest(order="sideways")


def test_unknown_sort_rejected(seeded):
    with pytest.raises(ValueError):
        prompts.prompts_page(seeded, PageRequest(sort="; DROP TABLE messages"), PRICING)
    with pytest.raises(ValueError):
        sessions.sessions_page(seeded, PageRequest(sort="nope"))


def test_like_pattern_escapes_metacharacters():
    assert like_pattern("50%_off\\") == "%50\\%\\_off\\\\%"


def test_project_summary_groups(seeded):
    rows = {r["project_slug"]: r for r in projects.project_summary(seeded)}
    assert set(rows) == {"projA", "projB"}
    assert rows["projA"]["turns"] == 1
    assert rows["projA"]["core_tokens"] == 300
    assert rows["projA"]["total_tokens"] == 600
    assert rows["projA"]["last_active"] == ts("2026-04-10T00:00:01Z")


def test_project_model_tokens(seeded):
    rows = projects.project_model_tokens(seeded)
    assert {(r["project_slug"], r["model"]) for r in rows} == {
        ("projA", "claude-opus-4-7"), ("projB", "claude-sonnet-4-6")}


def test_tool_breakdown(seeded):
    names = {r["tool_name"]: r for r in analytics.tool_token_breakdown(seeded)}
    assert set(names) == {"Read", "Bash"}
    assert names["Read"]["calls"] == 1


def test_sessions_page_default_order(seeded):
    page = sessions.sessions_page(seeded, PageRequest(page_size=5))
    assert [r["session_id"] for r in page["items"]] == ["s2", "s1"]
    assert page["total"] == 2
    s1 = page["items"][1]
    assert (s1["turns"], s1["tokens"], s1["total_tokens"]) == (1, 300, 600)
    assert s1["project_name"] == "projA"


def test_sessions_page_filters_and_sorts(db):
    insert_messages(db, [
        dict(uuid="u1", session_id="s1", project_slug="pA", type="user",
             timestamp="2026-04-10T00:00:00Z"),
        dict(uuid="a1", session_id="s1", project_slug="pA", timestamp="2026-04-10T00:00:01Z",
             model="claude-opus-4-7", cache_read_tokens=10_000_000),
        dict(uuid="a2", session_id="s2", project_slug="pB", timestamp="2026-04-11T00:00:01Z",
             model="claude-haiku-4-5", output_tokens=5000),
        dict(uuid="a3", session_id="s3", project_slug="pB", timestamp="2026-04-12T00:00:01Z",
             model="claude-haiku-4-5", output_tokens=10),
    ])
    db.execute("INSERT INTO session_titles VALUES ('s2', 'Fix the 100% bug'), ('s3', 'Other')")
    db.commit()

    def ids(**kw):
        req = PageRequest(**{k: kw.pop(k) for k in ("sort", "order") if k in kw})
        return [r["session_id"] for r in sessions.sessions_page(db, req, pricing=PRICING, **kw)["items"]]

    assert ids() == ["s3", "s2", "s1"]
    assert ids(project="pB") == ["s3", "s2"]
    assert ids(model="claude-opus-4-7") == ["s1"]
    assert ids(q="100%") == ["s2"]
    assert ids(q="s1") == ["s1"]
    assert ids(sort="tokens") == ["s2", "s3", "s1"]
    assert ids(sort="cost") == ["s1", "s2", "s3"]  # $5 of cache reads beats $0.025 of output
    assert ids(sort="started", order="asc") == ["s1", "s2", "s3"]
    assert ids(sort="title") == ["s2", "s3", "s1"]  # ascending, untitled last
    assert ids(since=ts("2026-04-11T00:00:00Z"), until=ts("2026-04-12T00:00:00Z")) == ["s2"]


def test_session_turns(seeded):
    rows = sessions.session_turns(seeded, "s1")
    assert [r["uuid"] for r in rows] == ["u1", "a1"]
    assert rows[1]["is_sidechain"] is False


def test_session_turns_parse_tool_calls_json(db):
    insert_messages(db, [dict(uuid="a", session_id="s", timestamp="2026-04-10T00:00:00Z",
                              tool_calls_json=[{"name": "Read", "target": "x.py"}])])
    assert sessions.session_turns(db, "s")[0]["tool_calls_json"] == [{"name": "Read", "target": "x.py"}]


def test_session_model_tokens(seeded):
    assert sessions.session_model_tokens(seeded, []) == []
    rows = sessions.session_model_tokens(seeded, ["s1", "s2"])
    assert {(r["session_id"], r["model"], r["input_tokens"]) for r in rows} == {
        ("s1", "claude-opus-4-7", 100), ("s2", "claude-sonnet-4-6", 5)}
    assert sessions.session_model_tokens(seeded, ["s1"], since=ts("2026-04-11T00:00:00Z")) == []


def test_daily_token_breakdown_groups_by_day(seeded):
    days = {r["day"].isoformat(): r for r in analytics.daily_token_breakdown(seeded)}
    assert set(days) == {"2026-04-10", "2026-04-11"}
    d = days["2026-04-10"]
    assert (d["input_tokens"], d["output_tokens"], d["cache_read_tokens"]) == (100, 200, 300)


def test_daily_token_breakdown_respects_since(seeded):
    rows = analytics.daily_token_breakdown(seeded, since=ts("2026-04-11T00:00:00Z"))
    assert [r["day"].isoformat() for r in rows] == ["2026-04-11"]


def test_daily_buckets_by_timezone(db):
    # 2026-04-10T22:30Z is 2026-04-11 03:30 in Karachi (UTC+5) and 18:30 in New York.
    insert_messages(db, [dict(uuid="a", session_id="s", timestamp="2026-04-10T22:30:00Z",
                              input_tokens=7)])
    day = lambda tz: analytics.daily_token_breakdown(db, tz=tz)[0]["day"].isoformat()
    assert day("UTC") == "2026-04-10"
    assert day("Asia/Karachi") == "2026-04-11"
    assert day("America/New_York") == "2026-04-10"


def test_daily_model_tokens(seeded):
    rows = analytics.daily_model_tokens(seeded)
    got = {(r["day"].isoformat(), r["model"]): r["input_tokens"] for r in rows}
    assert got == {("2026-04-10", "claude-opus-4-7"): 100, ("2026-04-11", "claude-sonnet-4-6"): 5}
    per_project = analytics.daily_model_tokens(seeded, by_project=True)
    assert {(r["project_slug"], r["day"].isoformat()) for r in per_project} == {
        ("projA", "2026-04-10"), ("projB", "2026-04-11")}
    only_b = analytics.daily_model_tokens(seeded, project="projB")
    assert [r["model"] for r in only_b] == ["claude-sonnet-4-6"]


def test_cost_by_model_per_key(seeded):
    from claude_lens.core.costs import cost_by_model_per_key
    rows = analytics.daily_model_tokens(seeded, by_project=True)
    costs = cost_by_model_per_key(rows, ("project_slug", "day"), PRICING)
    key = ("projA", ts("2026-04-10T00:00:00Z").date())
    assert set(costs[key]) == {"claude-opus-4-7"} and costs[key]["claude-opus-4-7"] > 0


def test_model_breakdown_respects_since_and_groups(seeded):
    models = {r["model"]: r for r in analytics.model_breakdown(seeded)}
    assert set(models) == {"claude-opus-4-7", "claude-sonnet-4-6"}
    assert models["claude-opus-4-7"]["input_tokens"] == 100
    assert models["claude-opus-4-7"]["turns"] == 1
    filtered = analytics.model_breakdown(seeded, since=ts("2026-04-11T00:00:00Z"))
    assert [r["model"] for r in filtered] == ["claude-sonnet-4-6"]


# --- skills ----------------------------------------------------------------------

@pytest.fixture
def skills_seeded(db):
    insert_tools(db, [
        dict(message_uuid="a1", session_id="s1", project_slug="pA", tool_name="Skill",
             target="brainstorming", timestamp="2026-04-10T00:00:01Z"),
        dict(message_uuid="u1", session_id="s1", project_slug="pA", tool_name="_tool_result",
             target="use-123", result_tokens=500, timestamp="2026-04-10T00:00:05Z"),
        dict(message_uuid="a1", session_id="s1", project_slug="pA", tool_name="Skill",
             target="brainstorming", timestamp="2026-04-10T00:00:30Z"),
        dict(message_uuid="a2", session_id="s2", project_slug="pA", tool_name="Skill",
             target="create-skill", timestamp="2026-04-11T00:00:01Z"),
    ])
    db.execute("INSERT INTO skill_catalog (machine, slug, path, chars, tokens, updated_at) VALUES"
               " ('pc1', 'brainstorming', '/a', 400, 100, now() - interval '1 day'),"
               " ('pc2', 'brainstorming', '/b', 800, 200, now())")
    db.commit()
    return db


def test_skills_group_and_order(skills_seeded):
    rows = analytics.skill_breakdown(skills_seeded)
    by = {r["skill"]: r for r in rows}
    assert rows[0]["skill"] == "brainstorming"
    assert (by["brainstorming"]["invocations"], by["brainstorming"]["sessions"]) == (2, 1)
    assert by["create-skill"]["invocations"] == 1
    assert by["brainstorming"]["last_used"] == ts("2026-04-10T00:00:30Z")


def test_skills_tokens_per_call_from_catalog(skills_seeded):
    by = {r["skill"]: r for r in analytics.skill_breakdown(skills_seeded)}
    assert by["brainstorming"]["tokens_per_call"] == 200  # most recently updated machine
    assert by["create-skill"]["tokens_per_call"] is None


def test_skills_respect_since(skills_seeded):
    rows = analytics.skill_breakdown(skills_seeded, since=ts("2026-04-11T00:00:00Z"))
    assert [r["skill"] for r in rows] == ["create-skill"]


# --- project names -----------------------------------------------------------------

@pytest.fixture
def named(db):
    insert_messages(db, [
        dict(uuid="u1", session_id="s1", project_slug="C--Users-x-My-Repo", cwd="/Users/x/My Repo",
             type="user", timestamp="2026-04-10T00:00:00Z"),
        dict(uuid="a1", session_id="s1", project_slug="C--Users-x-My-Repo",
             cwd="/Users/x/My Repo/src", timestamp="2026-04-10T00:00:01Z", input_tokens=10),
        dict(uuid="u2", session_id="s2", project_slug="slugOnly", type="user",
             timestamp="2026-04-11T00:00:00Z"),
        dict(uuid="a2", session_id="s2", project_slug="slugOnly", timestamp="2026-04-11T00:00:01Z",
             input_tokens=5),
    ])
    return db


def test_project_summary_uses_cwd_basename(named):
    names = {r["project_slug"]: r["project_name"] for r in projects.project_summary(named)}
    assert names == {"C--Users-x-My-Repo": "My Repo", "slugOnly": "slugOnly"}


def test_sessions_and_project_sessions_have_project_name(named):
    items = sessions.sessions_page(named, PageRequest())["items"]
    assert {r["session_id"]: r["project_name"] for r in items} == {"s1": "My Repo", "s2": "slugOnly"}
    rows = projects.project_sessions(named, "C--Users-x-My-Repo")
    assert [(r["session_id"], r["project_name"]) for r in rows] == [("s1", "My Repo")]
    assert projects.project_sessions(named, "missing") == []


def test_project_names_is_one_query_for_many_slugs(named):
    assert project_names(named, []) == {}
    assert project_names(named, ["slugOnly", "C--Users-x-My-Repo", "unknown-slug"]) == {
        "slugOnly": "slugOnly", "C--Users-x-My-Repo": "My Repo", "unknown-slug": "slug"}


# --- settings & sync -----------------------------------------------------------------

def test_plan_and_timezone_settings(db):
    assert settings.get_plan(db) == "api"
    assert settings.get_setting(db, "plan") is None
    assert settings.get_timezone(db) == "UTC"
    settings.set_plan(db, "max")
    settings.set_plan(db, "pro")
    settings.set_timezone(db, "Asia/Karachi")
    db.commit()
    assert settings.get_plan(db) == "pro"
    assert settings.get_timezone(db) == "Asia/Karachi"
    with pytest.raises(ValueError):
        settings.set_timezone(db, "Mars/Olympus")
    db.rollback()


def test_sync_status(db):
    assert sync.sync_status(db) == {"last_synced_at": None, "machines": [], "runs": []}
    db.execute("""
      INSERT INTO sync_runs (machine, started_at, finished_at, status, files, error) VALUES
        ('pc', '2026-04-10T13:00Z', '2026-04-10T13:00:05Z', 'ok', 3, NULL),
        ('pc', '2026-04-11T13:00Z', '2026-04-11T13:00:09Z', 'error', NULL, 'boom'),
        ('laptop', '2026-04-09T13:00Z', '2026-04-09T13:00:02Z', 'ok', 1, NULL)
    """)
    db.commit()
    st = sync.sync_status(db)
    assert st["last_synced_at"] == ts("2026-04-10T13:00:05Z")
    assert [m["machine"] for m in st["machines"]] == ["pc", "laptop"]
    pc = st["machines"][0]
    assert pc["last_run"]["status"] == "error" and pc["last_run"]["error"] == "boom"
    assert pc["last_ok_at"] == ts("2026-04-10T13:00:05Z")
    assert len(st["runs"]) == 3 and st["runs"][0]["status"] == "error"
