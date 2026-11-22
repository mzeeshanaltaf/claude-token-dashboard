import json

import pytest

from claude_lens.collector.parse import _session_title, parse_record


# --- message rows -----------------------------------------------------------

def test_parses_assistant_usage(load_fixture):
    msg, tools = parse_record(load_fixture("simple_assistant.json"), project_slug="proj-x")
    assert msg["uuid"] == "msg-1"
    assert msg["session_id"] == "sess-1"
    assert msg["project_slug"] == "proj-x"
    assert msg["model"] == "claude-opus-4-7"
    assert msg["message_id"] == "msg_x"
    assert msg["input_tokens"] == 10
    assert msg["output_tokens"] == 5
    assert msg["cache_read_tokens"] == 100
    assert msg["cache_create_5m_tokens"] == 30
    assert msg["cache_create_1h_tokens"] == 20
    assert msg["is_sidechain"] == 0
    assert msg["agent_id"] is None
    assert tools == []


def test_user_prompt_text_from_string_and_blocks():
    msg, _ = parse_record({"type": "user", "uuid": "u", "message": {"content": "hello"}}, "p")
    assert (msg["prompt_text"], msg["prompt_chars"]) == ("hello", 5)
    msg, _ = parse_record({"type": "user", "uuid": "u", "message": {"content": [
        {"type": "text", "text": "ab"}, {"type": "image"}, {"type": "text", "text": "cd"},
    ]}}, "p")
    assert (msg["prompt_text"], msg["prompt_chars"]) == ("abcd", 4)


# --- tool rows --------------------------------------------------------------

def test_extracts_tool_uses(load_fixture):
    msg, tools = parse_record(load_fixture("tool_use_assistant.json"), project_slug="p")
    assert [t["tool_name"] for t in tools] == ["Read", "Bash"]
    assert tools[0]["target"] == "C:/proj/foo.py"
    assert tools[1]["target"] == "npm run lint"
    parsed = json.loads(msg["tool_calls_json"])
    assert parsed[0]["name"] == "Read"
    assert parsed[1]["target"] == "npm run lint"


def test_tool_use_rows_capture_tool_use_id(load_fixture):
    _, tools = parse_record(load_fixture("tool_use_assistant.json"), project_slug="p")
    assert [t["tool_use_id"] for t in tools] == ["tu1", "tu2"]
    for t in tools:
        assert t["message_uuid"] == "msg-2"
        assert t["session_id"] == "sess-1"
        assert t["project_slug"] == "p"


def test_tool_use_without_id_yields_none():
    rec = {"type": "assistant", "uuid": "a", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
    ]}}
    _, tools = parse_record(rec, "p")
    assert tools[0]["tool_use_id"] is None


def test_tool_use_id_not_in_tool_calls_json(load_fixture):
    msg, _ = parse_record(load_fixture("tool_use_assistant.json"), project_slug="p")
    for entry in json.loads(msg["tool_calls_json"]):
        assert set(entry) == {"name", "target"}


def test_is_sidechain_flag_propagates():
    rec = {
        "type": "assistant", "uuid": "u", "sessionId": "s",
        "timestamp": "t", "isSidechain": True, "agentId": "agent-explore-1",
        "message": {"model": "claude-sonnet-4-6", "usage": {"input_tokens": 1, "output_tokens": 1}},
    }
    msg, _ = parse_record(rec, project_slug="p")
    assert msg["is_sidechain"] == 1
    assert msg["agent_id"] == "agent-explore-1"


def test_tool_result_estimates_tokens_and_links_tool_use_id():
    rec = {
        "type": "user", "uuid": "u2", "sessionId": "s",
        "timestamp": "t", "isSidechain": False,
        "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu1", "content": "x" * 4000, "is_error": True}
        ]},
    }
    msg, tools = parse_record(rec, project_slug="p")
    assert msg["type"] == "user"
    assert len(tools) == 1
    assert tools[0]["tool_name"] == "_tool_result"
    assert tools[0]["result_tokens"] == pytest.approx(1000, abs=10)
    assert tools[0]["is_error"] == 1
    # tool_use_id links back to the tool_use row; target keeps the old behaviour
    assert tools[0]["tool_use_id"] == "tu1"
    assert tools[0]["target"] == "tu1"


def test_all_tool_rows_share_the_same_keys(load_fixture):
    _, uses = parse_record(load_fixture("tool_use_assistant.json"), "p")
    _, results = parse_record({"type": "user", "uuid": "u", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "tu1", "content": [{"type": "text", "text": "ok"}]},
    ]}}, "p")
    keys = {frozenset(t) for t in uses + results}
    assert len(keys) == 1


# --- session titles ---------------------------------------------------------

def test_ai_title_record():
    assert _session_title({"type": "ai-title", "sessionId": "s1", "aiTitle": " Fix bug "}) == ("s1", "Fix bug")


def test_legacy_summary_record():
    assert _session_title({"type": "summary", "sessionId": "s1", "summary": "Do thing"}) == ("s1", "Do thing")


def test_non_title_record_ignored():
    assert _session_title({"type": "assistant", "uuid": "a1"}) is None
    assert _session_title("not a dict") is None


def test_blank_title_ignored():
    assert _session_title({"type": "ai-title", "sessionId": "s1", "aiTitle": "  "}) is None
    assert _session_title({"type": "ai-title", "aiTitle": "x"}) is None
