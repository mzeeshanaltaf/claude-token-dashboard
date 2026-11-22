"""The API over a seeded test schema (ported from tests/test_server.py, plus every route)."""
import pytest

from claude_lens.core.pricing import load_pricing
from helpers import insert_messages, insert_tools, q1

PRICING = load_pricing()


@pytest.fixture
def seeded(client, db):
    insert_messages(db, [
        dict(uuid="u", session_id="s", project_slug="p", type="user",
             timestamp="2026-04-19T00:00:00Z", prompt_text="hi", prompt_chars=2, cwd="/w/p"),
        dict(uuid="a", parent_uuid="u", session_id="s", project_slug="p",
             timestamp="2026-04-19T00:00:01Z", model="claude-haiku-4-5",
             input_tokens=1000, output_tokens=2000, cache_read_tokens=3000,
             cache_create_5m_tokens=4000, cache_create_1h_tokens=5000,
             tool_calls_json=[{"name": "Read", "target": "x.py"}]),
        dict(uuid="u2", session_id="s2", project_slug="q", type="user",
             timestamp="2026-04-20T00:00:00Z", prompt_text="second", prompt_chars=6),
        dict(uuid="a2", parent_uuid="u2", session_id="s2", project_slug="q",
             timestamp="2026-04-20T00:00:01Z", model="mystery-model", output_tokens=7),
    ])
    insert_tools(db, [dict(message_uuid="a", session_id="s", tool_name="Read", target="x.py",
                           timestamp="2026-04-19T00:00:01Z")])
    return client


# haiku-4-5: input $1, output $5, cache_read $0.10, 5m $1.25, 1h $2 per million
HAIKU_TURN = (1000 * 1 + 2000 * 5 + 3000 * 0.1 + 4000 * 1.25 + 5000 * 2) / 1_000_000


def test_health_needs_no_login(anon):
    r = anon.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_overview_json(seeded):
    body = seeded.get("/api/overview").json()
    assert (body["sessions"], body["projects"], body["turns"]) == (2, 2, 2)
    assert body["input_tokens"] == 1000 and body["output_tokens"] == 2007
    assert body["cost_usd"] == round(HAIKU_TURN, 4)  # the unpriced model adds nothing
    assert body["cost_cache_create_usd"] == round((4000 * 1.25 + 5000 * 2) / 1e6, 4)


def test_overview_range(seeded):
    body = seeded.get("/api/overview", params={"since": "2026-04-20T00:00:00Z"}).json()
    assert body["sessions"] == 1 and body["cost_usd"] == 0
    body = seeded.get("/api/overview", params={"until": "2026-04-20"}).json()
    assert body["sessions"] == 1 and body["input_tokens"] == 1000


def test_bad_range_is_422(seeded):
    assert seeded.get("/api/overview", params={"since": "last tuesday"}).status_code == 422


def test_prompts_envelope_and_full_turn_cost(seeded):
    body = seeded.get("/api/prompts", params={"page_size": 10}).json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert (body["total"], body["page"], body["page_size"]) == (2, 1, 10)
    row = next(r for r in body["items"] if r["user_uuid"] == "u")
    assert row["core_tokens"] == 1000 + 2000 + 4000 + 5000
    # the fix: all five token types, not just cache reads
    assert row["estimated_cost_usd"] == pytest.approx(HAIKU_TURN)
    assert row["cost_cache_read_usd"] == pytest.approx(3000 * 0.1 / 1e6)
    other = next(r for r in body["items"] if r["user_uuid"] == "u2")
    assert other["estimated_cost_usd"] is None


def test_prompts_params(seeded):
    assert seeded.get("/api/prompts", params={"q": "seco"}).json()["total"] == 1
    assert seeded.get("/api/prompts", params={"project": "p"}).json()["total"] == 1
    assert seeded.get("/api/prompts", params={"model": "mystery-model"}).json()["total"] == 1
    recent = seeded.get("/api/prompts", params={"sort": "recent"}).json()["items"]
    assert [r["user_uuid"] for r in recent] == ["u2", "u"]
    by_cost = seeded.get("/api/prompts", params={"sort": "cost"}).json()["items"]
    assert by_cost[0]["user_uuid"] == "u"
    assert seeded.get("/api/prompts", params={"sort": "bogus"}).status_code == 422
    assert seeded.get("/api/prompts", params={"page_size": 201}).status_code == 422
    assert seeded.get("/api/prompts", params={"page": 0}).status_code == 422


def test_projects_json(seeded):
    body = seeded.get("/api/projects").json()
    by = {r["project_slug"]: r for r in body}
    assert body[0]["project_slug"] == "p"  # most core tokens first
    assert by["p"]["project_name"] == "p"
    assert by["p"]["estimated_cost_usd"] == round(HAIKU_TURN, 4)
    assert by["p"]["cost_cache_write_usd"] == round((4000 * 1.25 + 5000 * 2) / 1e6, 4)
    assert by["q"]["estimated_cost_usd"] is None and by["q"]["cost_input_usd"] is None


def test_project_sessions(seeded):
    rows = seeded.get("/api/projects/p/sessions").json()
    assert [r["session_id"] for r in rows] == ["s"]
    assert rows[0]["estimated_cost_usd"] == round(HAIKU_TURN, 4)
    assert seeded.get("/api/projects/nope/sessions").json() == []


def test_sessions_envelope(seeded):
    body = seeded.get("/api/sessions", params={"page_size": 1}).json()
    assert (body["total"], body["page"], body["page_size"]) == (2, 1, 1)
    assert [r["session_id"] for r in body["items"]] == ["s2"]
    page2 = seeded.get("/api/sessions", params={"page_size": 1, "page": 2}).json()
    s = page2["items"][0]
    assert s["session_id"] == "s" and s["estimated_cost_usd"] == round(HAIKU_TURN, 4)
    assert s["cache_write_tokens"] == 9000 and s["total_tokens"] == 15000
    assert s["started"] == "2026-04-19T00:00:00Z"
    by_cost = seeded.get("/api/sessions", params={"sort": "cost"}).json()["items"]
    assert [r["session_id"] for r in by_cost] == ["s", "s2"]


def test_session_detail(seeded):
    rows = seeded.get("/api/sessions/s").json()
    assert [r["uuid"] for r in rows] == ["u", "a"]
    user, asst = rows
    assert user["estimated_cost_usd"] is None
    assert asst["estimated_cost_usd"] == pytest.approx(HAIKU_TURN)
    assert asst["tool_calls_json"] == [{"name": "Read", "target": "x.py"}]
    assert asst["is_sidechain"] is False
    assert seeded.get("/api/sessions/missing").json() == []


def test_by_model(seeded):
    rows = {r["model"]: r for r in seeded.get("/api/by-model").json()}
    assert rows["claude-haiku-4-5"]["cost_usd"] == pytest.approx(HAIKU_TURN)
    assert rows["claude-haiku-4-5"]["cost_estimated"] is False
    assert rows["mystery-model"]["cost_usd"] is None


def test_daily_uses_timezone_setting(seeded):
    days = [r["day"] for r in seeded.get("/api/daily").json()]
    assert days == ["2026-04-19", "2026-04-20"]
    r = seeded.post("/api/settings", json={"timezone": "America/New_York"})
    assert r.status_code == 200 and r.json()["timezone"] == "America/New_York"
    days = [r["day"] for r in seeded.get("/api/daily").json()]
    assert days == ["2026-04-18", "2026-04-19"]  # both events are just after UTC midnight


def test_daily_carries_cost(seeded):
    days = {r["day"]: r for r in seeded.get("/api/daily").json()}
    assert days["2026-04-19"]["cost_usd"] == round(HAIKU_TURN, 4)
    assert days["2026-04-19"]["cost_by_model"] == {"claude-haiku-4-5": round(HAIKU_TURN, 4)}
    assert (days["2026-04-19"]["sessions"], days["2026-04-19"]["turns"]) == (1, 1)
    # an unpriced model contributes nothing, but the day is still listed
    assert days["2026-04-20"]["cost_usd"] == 0 and days["2026-04-20"]["cost_by_model"] == {}
    total = seeded.get("/api/overview").json()["cost_usd"]
    assert sum(d["cost_usd"] for d in days.values()) == pytest.approx(total)


def test_project_filter_on_overview_daily_by_model(seeded):
    o = seeded.get("/api/overview", params={"project": "q"}).json()
    assert (o["sessions"], o["projects"], o["output_tokens"], o["cost_usd"]) == (1, 1, 7, 0)
    o = seeded.get("/api/overview", params={"project": "p"}).json()
    assert o["cost_usd"] == round(HAIKU_TURN, 4) and o["input_tokens"] == 1000
    assert [r["day"] for r in seeded.get("/api/daily", params={"project": "p"}).json()] == ["2026-04-19"]
    assert [r["model"] for r in seeded.get("/api/by-model", params={"project": "q"}).json()] == ["mystery-model"]
    # an empty value means "no filter"
    assert seeded.get("/api/overview", params={"project": ""}).json()["sessions"] == 2


def test_projects_daily(seeded):
    rows = seeded.get("/api/projects/daily").json()
    assert rows == [{"project_slug": "p", "day": "2026-04-19", "cost_usd": round(HAIKU_TURN, 4)}]
    assert seeded.get("/api/projects/daily", params={"since": "2026-04-20T00:00:00Z"}).json() == []


def test_tools_and_skills(seeded, db):
    assert seeded.get("/api/tools").json() == [
        {"tool_name": "Read", "calls": 1, "result_tokens": 0}]
    insert_tools(db, [dict(message_uuid="a", session_id="s", tool_name="Skill",
                           target="brainstorming", timestamp="2026-04-19T00:00:01Z")])
    db.execute("INSERT INTO skill_catalog (machine, slug, path, chars, tokens)"
               " VALUES ('pc', 'brainstorming', '/x', 40, 10)")
    db.commit()
    skills = seeded.get("/api/skills").json()
    assert [(s["skill"], s["invocations"], s["tokens_per_call"]) for s in skills] == [
        ("brainstorming", 1, 10)]


def test_plan_json(client):
    body = client.get("/api/plan").json()
    assert body["plan"] == "api"
    assert set(body["pricing"]) >= {"models", "tier_fallback", "plans"}
    assert client.post("/api/plan", json={"plan": "max"}).json() == {"ok": True}
    assert client.get("/api/plan").json()["plan"] == "max"
    assert client.post("/api/plan", json={"plan": "platinum"}).status_code == 422


def test_settings(client, db):
    assert client.get("/api/settings").json() == {"plan": None, "timezone": "UTC"}
    r = client.post("/api/settings", json={"plan": "pro", "timezone": "Asia/Karachi"})
    assert r.json() == {"plan": "pro", "timezone": "Asia/Karachi"}
    assert q1(db, "SELECT v FROM settings WHERE k = 'plan'") == "pro"  # jsonb string
    bad = client.post("/api/settings", json={"timezone": "Nowhere/Land"})
    assert bad.status_code == 422
    assert client.get("/api/settings").json()["timezone"] == "Asia/Karachi"


def test_tips_and_dismiss(client, db):
    insert_messages(db, [dict(uuid="m", session_id="s", project_slug="projZ",
                              timestamp="now", model="claude-opus-4-7", input_tokens=100,
                              cache_read_tokens=10, cache_create_5m_tokens=1_000_000)])
    tips = client.get("/api/tips").json()
    assert [t["key"] for t in tips] == ["cache:projZ"]
    assert client.post("/api/tips/dismiss", json={"key": "cache:projZ"}).json() == {"ok": True}
    assert client.get("/api/tips").json() == []
    assert client.post("/api/tips/dismiss", json={"key": ""}).status_code == 422
    # undo
    assert client.post("/api/tips/restore", json={"key": "cache:projZ"}).json() == {"ok": True}
    assert [t["key"] for t in client.get("/api/tips").json()] == ["cache:projZ"]
    assert client.post("/api/tips/restore", json={"key": "never-dismissed"}).status_code == 200


def test_sync_status(client, db):
    assert client.get("/api/sync-status").json() == {
        "last_synced_at": None, "machines": [], "runs": []}
    db.execute("INSERT INTO sync_runs (machine, started_at, finished_at, status, files)"
               " VALUES ('pc', '2026-04-10T13:00Z', '2026-04-10T13:00:05Z', 'ok', 3)")
    db.commit()
    body = client.get("/api/sync-status").json()
    assert body["last_synced_at"] == "2026-04-10T13:00:05Z"
    assert body["machines"][0]["machine"] == "pc"
    assert body["machines"][0]["last_run"]["files"] == 3


def test_openapi_lists_every_endpoint(anon):
    paths = anon.get("/openapi.json").json()["paths"]
    expected = {
        "/api/health", "/api/auth/login", "/api/auth/logout", "/api/auth/me",
        "/api/auth/password", "/api/overview", "/api/daily", "/api/by-model", "/api/tools",
        "/api/skills", "/api/projects", "/api/projects/daily", "/api/projects/{slug}/sessions",
        "/api/sessions",
        "/api/sessions/{session_id}", "/api/prompts", "/api/tips", "/api/tips/dismiss",
        "/api/tips/restore",
        "/api/plan", "/api/settings", "/api/sync-status",
        # phase 06
        "/api/activity/calendar", "/api/activity/hourly", "/api/activity/summary",
        "/api/sessions/{session_id}/insights", "/api/tools/insights", "/api/search",
        "/api/export/sessions.csv", "/api/export/prompts.csv", "/api/export/projects.csv",
    }
    assert set(paths) == expected
    assert anon.get("/docs").status_code == 200
