"""Phase 06 endpoints over a seeded test schema: activity, insights, tools, search, export."""
import csv
import io
from datetime import datetime, timedelta, timezone

from claude_lens.core.csv_export import BOM
from claude_lens.db.queries.search import HL_START, HL_STOP
from helpers import insert_messages, insert_tools

HAIKU = "claude-haiku-4-5"


def utc_today():
    return datetime.now(timezone.utc).date()


def iso(d, hhmm="12:00"):
    return f"{d.isoformat()}T{hhmm}:00Z"


def _assistant(uuid, ts, sid="s", project="p", **kw):
    return {"uuid": uuid, "session_id": sid, "project_slug": project, "timestamp": ts,
            "model": HAIKU, "input_tokens": 1000, "output_tokens": 100, **kw}


def _user(uuid, ts, sid="s", project="p", text=None, **kw):
    return dict(uuid=uuid, session_id=sid, project_slug=project, timestamp=ts, type="user",
                prompt_text=text, prompt_chars=len(text) if text else None, **kw)


# --- activity -----------------------------------------------------------------

def test_calendar_buckets_by_timezone_across_utc_midnight(client, db):
    d = utc_today() - timedelta(days=1)
    insert_messages(db, [
        _assistant("early", iso(d, "00:30")),  # NY: the evening before
        _assistant("late", iso(d, "23:30")),   # NY: the same day
    ])
    body = client.get("/api/activity/calendar").json()
    assert body["metric"] == "cost" and body["timezone"] == "UTC"
    assert [x["day"] for x in body["days"]] == [d.isoformat()]
    (day,) = body["days"]
    assert day["tokens"] == 2200 and day["value"] == day["cost_usd"] > 0
    assert body["end"] == utc_today().isoformat()

    assert client.post("/api/settings", json={"timezone": "America/New_York"}).status_code == 200
    body = client.get("/api/activity/calendar", params={"metric": "tokens"}).json()
    assert [x["day"] for x in body["days"]] == [(d - timedelta(days=1)).isoformat(), d.isoformat()]
    assert [x["value"] for x in body["days"]] == [1100, 1100]


def test_calendar_window_excludes_older_days(client, db):
    insert_messages(db, [_assistant("old", iso(utc_today() - timedelta(days=40)))])
    assert client.get("/api/activity/calendar", params={"days": 30}).json()["days"] == []
    assert len(client.get("/api/activity/calendar", params={"days": 60}).json()["days"]) == 1
    assert client.get("/api/activity/calendar", params={"metric": "bogus"}).status_code == 422


def test_hourly_grid(client, db):
    # 2026-04-20 is a Monday
    insert_messages(db, [
        _user("u", "2026-04-20T09:15:00Z"),
        _assistant("a", "2026-04-20T09:16:00Z"),
        _user("u2", "2026-04-26T23:59:00Z"),  # Sunday
    ])
    cells = client.get("/api/activity/hourly").json()["cells"]
    assert len(cells) == 168 and (cells[0]["dow"], cells[0]["hour"]) == (1, 0)
    by = {(c["dow"], c["hour"]): c for c in cells}
    assert by[(1, 9)]["turns"] == 1 and by[(1, 9)]["tokens"] == 1100 and by[(1, 9)]["cost_usd"] > 0
    assert by[(7, 23)]["turns"] == 1
    assert sum(c["turns"] for c in cells) == 2


def test_summary_streaks_busiest_and_top_project(client, db):
    t = utc_today()
    rows = []
    for back in (5, 4, 3, 1, 0):  # a 3-day run, a gap, then yesterday + today
        d = t - timedelta(days=back)
        rows += [_user(f"u{back}", iso(d, "08:00"), sid=f"s{back}", project="p"),
                 _assistant(f"a{back}", iso(d, "08:01"), sid=f"s{back}", project="p")]
    rows.append(_assistant("big", iso(t - timedelta(days=4), "09:00"), sid="s4",
                           project="p", output_tokens=50_000))
    rows.append(_user("q1", iso(t, "10:00"), sid="sq", project="q"))
    insert_messages(db, rows)

    s = client.get("/api/activity/summary").json()
    assert s["active_days"] == 5 and s["days_in_range"] == 6
    assert (s["current_streak"], s["longest_streak"]) == (2, 3)
    assert s["busiest_day"]["day"] == (t - timedelta(days=4)).isoformat()
    assert s["top_project"]["project_slug"] == "p" and s["top_project"]["turns"] == 5
    assert s["top_project"]["cost_usd"] > 0
    assert s["peak_hour"] == {"hour": 8, "turns": 5}
    assert abs(s["avg_cost_per_active_day"] - s["total_cost_usd"] / 5) < 1e-3

    # `until` (exclusive) ends the range before today: the current streak is then
    # measured from the day before `until`.
    until = (t - timedelta(days=1)).isoformat()
    s = client.get("/api/activity/summary", params={"until": until}).json()
    assert s["last_day"] == (t - timedelta(days=2)).isoformat()
    assert (s["active_days"], s["current_streak"], s["longest_streak"]) == (3, 3, 3)


def test_summary_empty(client):
    s = client.get("/api/activity/summary").json()
    assert s["active_days"] == 0 and s["busiest_day"] is None and s["top_project"] is None
    assert s["peak_hour"] is None and s["first_day"] is None


# --- session insights -----------------------------------------------------------

def test_session_insights(client, db):
    insert_messages(db, [
        _user("u1", "2026-05-01T10:00:00Z", text="go", git_branch="main"),
        _assistant("a1", "2026-05-01T10:00:05Z", cache_read_tokens=5000, git_branch="main"),
        _assistant("s1", "2026-05-01T10:01:00Z", is_sidechain=True, agent_id="ag",
                   git_branch="main"),
        _assistant("a2", "2026-05-01T10:30:00Z", git_branch="feature/x",
                   model="claude-opus-4-7"),
    ])
    insert_tools(db, [
        dict(message_uuid="a1", session_id="s", tool_name="Read", target="src/a.py",
             tool_use_id="t1", timestamp="2026-05-01T10:00:05Z"),
        dict(message_uuid="u2", session_id="s", tool_name="_tool_result", target="t1",
             tool_use_id="t1", result_tokens=40, is_error=1, timestamp="2026-05-01T10:00:06Z"),
        dict(message_uuid="a1", session_id="s", tool_name="Agent", target="Explore",
             tool_use_id="t2", timestamp="2026-05-01T10:00:05Z"),
        dict(message_uuid="a2", session_id="s", tool_name="Edit", target="src/a.py",
             timestamp="2026-05-01T10:30:00Z"),  # migrated: no tool_use_id
    ])
    body = client.get("/api/sessions/s/insights").json()
    assert [p["context_tokens"] for p in body["context_growth"]] == [6000, 1000, 1000]
    assert [p["is_sidechain"] for p in body["context_growth"]] == [False, True, False]
    assert [(e["tool_name"], e["is_error"]) for e in body["tool_timeline"]] == [
        ("Read", True), ("Agent", None), ("Edit", None)]
    assert body["tool_calls_linked"] == 2
    assert body["subagents"][0]["agent_id"] == "ag" and body["subagents"][0]["turns"] == 1
    assert body["subagent_invocations"][0]["subagent_type"] == "Explore"
    assert body["files"] == [{"path": "src/a.py", "read": 1, "edit": 1, "write": 0, "total": 2}]
    assert body["branches"] == ["main", "feature/x"]
    assert {m["model"] for m in body["models"]} == {HAIKU, "claude-opus-4-7"}
    assert body["duration_s"] == 1800
    assert client.get("/api/sessions/nope/insights").json()["context_growth"] == []


# --- tools insights -----------------------------------------------------------

def test_tools_insights(client, db):
    ts = "2026-05-02T00:00:00Z"
    insert_tools(db, [
        dict(message_uuid="m", session_id="s", tool_name="Bash", target="git status",
             tool_use_id="b1", timestamp=ts),
        dict(message_uuid="r", session_id="s", tool_name="_tool_result", target="b1",
             tool_use_id="b1", result_tokens=10, is_error=1, timestamp=ts),
        dict(message_uuid="m", session_id="s", tool_name="Bash", target="git status",
             tool_use_id="b2", timestamp=ts),
        dict(message_uuid="r", session_id="s", tool_name="_tool_result", target="b2",
             tool_use_id="b2", result_tokens=5, timestamp=ts),
        dict(message_uuid="m", session_id="s", tool_name="Bash", target="ls", timestamp=ts),
        dict(message_uuid="m", session_id="s", tool_name="PowerShell", target="Get-Date",
             timestamp=ts),
        dict(message_uuid="m", session_id="s", tool_name="Read", target="a.py", timestamp=ts),
        dict(message_uuid="m", session_id="s", tool_name="Edit", target="a.py", timestamp=ts),
        dict(message_uuid="m", session_id="s", tool_name="WebFetch",
             target="https://www.Example.com/docs?x=1", timestamp=ts),
        dict(message_uuid="m", session_id="s", tool_name="WebFetch",
             target="http://example.com:8080/", timestamp=ts),
    ])
    body = client.get("/api/tools/insights").json()
    bash = next(t for t in body["tools"] if t["tool_name"] == "Bash")
    assert (bash["calls"], bash["linked"], bash["errors"], bash["result_tokens"]) == (3, 2, 1, 15)
    assert bash["error_rate"] == 0.5
    read = next(t for t in body["tools"] if t["tool_name"] == "Read")
    assert read["linked"] == 0 and read["error_rate"] is None
    assert (body["calls"], body["linked"]) == (8, 2) and "2 of 8" in body["linked_note"]
    assert body["files"][0]["path"] == "a.py" and body["files"][0]["total"] == 2
    assert [(c["command"], c["calls"]) for c in body["commands"]][:1] == [("git status", 2)]
    assert {c["tool_name"] for c in body["commands"]} == {"Bash", "PowerShell"}
    assert body["domains"] == [{"domain": "example.com", "calls": 2, "last_used": ts}]


# --- search -----------------------------------------------------------------------

def test_search_groups(client, db):
    insert_messages(db, [
        _user("u1", "2026-05-03T00:00:00Z", sid="s1", project="C--work-lens",
              text="Please refactor the websocket reconnection logic", cwd="C:/work/lens"),
        _user("u2", "2026-05-04T00:00:00Z", sid="s2", project="C--work-other",
              text="Nothing relevant here"),
    ])
    db.execute("INSERT INTO session_titles VALUES ('s1', 'Websocket cleanup'), ('s2', 'Other')")
    db.commit()

    body = client.get("/api/search", params={"q": "websockets reconnect"}).json()
    (hit,) = body["prompts"]
    assert hit["user_uuid"] == "u1" and hit["session_id"] == "s1"
    assert f"{HL_START}websocket{HL_STOP}" in hit["snippet"]
    assert "<b>" not in hit["snippet"]
    assert [s["session_id"] for s in body["sessions"]] == []  # title search is ILIKE

    body = client.get("/api/search", params={"q": "websocket"}).json()
    assert [s["session_id"] for s in body["sessions"]] == ["s1"]
    body = client.get("/api/search", params={"q": "LENS"}).json()
    assert [p["project_slug"] for p in body["projects"]] == ["C--work-lens"]
    assert body["projects"][0]["project_name"] == "lens"
    assert client.get("/api/search", params={"q": "  "}).json()["prompts"] == []
    assert len(client.get("/api/search", params={"q": "x" * 201}).json()["detail"]) >= 1


# --- export -------------------------------------------------------------------------

def _csv(resp):
    text = resp.content.decode("utf-8")
    assert text.startswith(BOM)
    return list(csv.reader(io.StringIO(text[len(BOM):])))


def test_export_sessions_streams_every_page(client, db):
    n = 205  # more than one 200-row page
    rows = []
    for i in range(n):
        ts = (datetime(2026, 5, 5, tzinfo=timezone.utc) + timedelta(minutes=i)).isoformat()
        rows.append(_assistant(f"a{i}", ts, sid=f"s{i:03d}"))
    insert_messages(db, rows)

    r = client.get("/api/export/sessions.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    cd = r.headers["content-disposition"]
    assert cd.startswith('attachment; filename="claude-lens-sessions-') and cd.endswith('.csv"')
    out = _csv(r)
    assert out[0][:3] == ["session_id", "title", "project_name"]
    assert len(out) == n + 1
    assert len({row[0] for row in out[1:]}) == n  # no page repeated or skipped
    assert out[1][0] == "s204"  # default sort: most recently ended first

    out = _csv(client.get("/api/export/sessions.csv", params={"q": "s00", "sort": "started",
                                                               "order": "asc"}))
    assert [row[0] for row in out[1:]] == [f"s00{i}" for i in range(10)]
    assert client.get("/api/export/sessions.csv", params={"sort": "nope"}).status_code == 422


def test_export_prompts_and_projects(client, db):
    insert_messages(db, [
        _user("u", "2026-05-06T00:00:00Z", text="=1+1 then explain", project="p"),
        _assistant("a", "2026-05-06T00:00:01Z", parent_uuid="u", project="p"),
        _user("u2", "2026-05-07T00:00:00Z", sid="s2", text="other", project="q"),
        _assistant("a2", "2026-05-07T00:00:01Z", sid="s2", parent_uuid="u2", project="q"),
    ])
    out = _csv(client.get("/api/export/prompts.csv", params={"project": "p"}))
    assert out[0][0] == "timestamp" and out[0][-1] == "prompt_text"
    assert len(out) == 2 and out[1][-1] == "'=1+1 then explain"
    assert float(out[1][out[0].index("estimated_cost_usd")]) > 0

    out = _csv(client.get("/api/export/projects.csv"))
    assert out[0][:2] == ["project_name", "project_slug"] and len(out) == 3
    out = _csv(client.get("/api/export/projects.csv", params={"q": "Q"}))
    assert [row[1] for row in out[1:]] == ["q"]
    assert client.get("/api/export/projects.csv", params={"since": "2026-05-07"}).status_code == 200


def test_export_needs_login(anon):
    assert anon.get("/api/export/sessions.csv").status_code == 401
