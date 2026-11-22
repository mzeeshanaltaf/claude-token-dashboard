"""Streaming-snapshot dedup (ported from tests/test_scanner_dedup.py).

Claude Code writes the same API response 2-3 times while streaming, each as its
own JSONL line with a distinct top-level `uuid` but identical `message.id`.
Only the final snapshot matches billing; summing them over-counts tokens.
"""
from claude_lens.collector.ingest import scan
from helpers import append_jsonl, q, q1, user_record, write_jsonl

MACHINE = "test-pc"


def _streaming_partial(uuid, msg_id, session, ts, output_tokens):
    return {
        "type": "assistant", "uuid": uuid, "parentUuid": "u1", "sessionId": session,
        "timestamp": ts, "isSidechain": False,
        "message": {
            "id": msg_id, "model": "claude-opus-4-7",
            "content": [{"type": "text", "text": "streaming..."}],
            "usage": {
                "input_tokens": 100, "output_tokens": output_tokens,
                "cache_read_input_tokens": 500,
                "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 200},
            },
        },
    }


def _rec_with_tool(uuid, ts, out, msg_id="msg_Z"):
    return {
        "type": "assistant", "uuid": uuid, "parentUuid": "u1", "sessionId": "s1",
        "timestamp": ts, "isSidechain": False,
        "message": {
            "id": msg_id, "model": "claude-opus-4-7",
            "content": [{"type": "tool_use", "id": "tu1", "name": "Read",
                         "input": {"file_path": "foo.py"}}],
            "usage": {"input_tokens": 1, "output_tokens": out},
        },
    }


def test_within_file_streaming_dupes_collapse_to_final(db, projects):
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [
        user_record(),
        _streaming_partial("r1", "msg_X", "s1", "2026-04-10T00:00:01Z", 27),
        _streaming_partial("r2", "msg_X", "s1", "2026-04-10T00:00:02Z", 27),
        _streaming_partial("r3", "msg_X", "s1", "2026-04-10T00:00:03Z", 303),
    ])
    scan(root, db, MACHINE)

    rows = q(db, "SELECT uuid, input_tokens, output_tokens, cache_read_tokens, cache_create_1h_tokens"
                 " FROM messages WHERE type = 'assistant'")
    assert len(rows) == 1, "streaming duplicates must collapse to one row"
    # Final snapshot wins: output_tokens = 303, not the sum (357) nor a partial (27).
    assert rows[0] == ("r3", 100, 303, 500, 200)


def test_incremental_scan_final_replaces_partial(db, projects):
    """Partials written first, final appended later: scan twice, final wins."""
    root, proj = projects
    path = proj / "s1.jsonl"
    write_jsonl(path, [
        user_record(),
        _streaming_partial("r1", "msg_Y", "s1", "2026-04-10T00:00:01Z", 27),
        _streaming_partial("r2", "msg_Y", "s1", "2026-04-10T00:00:02Z", 27),
    ])
    scan(root, db, MACHINE)
    append_jsonl(path, [_streaming_partial("r3", "msg_Y", "s1", "2026-04-10T00:00:03Z", 303)])
    scan(root, db, MACHINE)

    rows = q(db, "SELECT uuid, output_tokens FROM messages WHERE type = 'assistant'")
    assert rows == [("r3", 303)], "final snapshot must replace earlier partial across scans"


def test_superseded_tool_calls_are_removed(db, projects):
    """A partial's tool_calls rows must not linger once the final replaces it."""
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [
        user_record(),
        _rec_with_tool("r1", "2026-04-10T00:00:01Z", 5),
        _rec_with_tool("r2", "2026-04-10T00:00:02Z", 50),
    ])
    scan(root, db, MACHINE)

    tools = q(db, "SELECT message_uuid, tool_name FROM tool_calls WHERE tool_name = 'Read'")
    assert tools == [("r2", "Read")], "only the winning record's tool_calls remain"


def test_superseded_tool_calls_are_removed_across_scans(db, projects):
    root, proj = projects
    path = proj / "s1.jsonl"
    write_jsonl(path, [user_record(), _rec_with_tool("r1", "2026-04-10T00:00:01Z", 5)])
    scan(root, db, MACHINE)
    append_jsonl(path, [_rec_with_tool("r2", "2026-04-10T00:00:02Z", 50)])
    scan(root, db, MACHINE)

    assert q(db, "SELECT message_uuid FROM tool_calls WHERE tool_name = 'Read'") == [("r2",)]
    assert q(db, "SELECT uuid FROM messages WHERE type = 'assistant'") == [("r2",)]


def test_assistant_without_message_id_falls_back_to_uuid(db, projects):
    """No message.id: each uuid is its own row."""
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [
        user_record(),
        {"type": "assistant", "uuid": "a1", "parentUuid": "u1", "sessionId": "s1",
         "timestamp": "2026-04-10T00:00:01Z", "isSidechain": False,
         "message": {"model": "claude-opus-4-7", "usage": {"input_tokens": 1, "output_tokens": 1}}},
        {"type": "assistant", "uuid": "a2", "parentUuid": "u1", "sessionId": "s1",
         "timestamp": "2026-04-10T00:00:02Z", "isSidechain": False,
         "message": {"model": "claude-opus-4-7", "usage": {"input_tokens": 2, "output_tokens": 2}}},
    ])
    scan(root, db, MACHINE)
    assert q(db, "SELECT uuid FROM messages WHERE type = 'assistant' ORDER BY uuid") == [("a1",), ("a2",)]


def test_snapshots_split_across_batches_collapse(db, projects):
    """With a tiny batch size, partials and the final land in different transactions."""
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [
        user_record(),
        _rec_with_tool("r1", "2026-04-10T00:00:01Z", 5, msg_id="msg_B"),
        _rec_with_tool("r2", "2026-04-10T00:00:02Z", 6, msg_id="msg_B"),
        _rec_with_tool("r3", "2026-04-10T00:00:03Z", 77, msg_id="msg_B"),
    ])
    n = scan(root, db, MACHINE, batch_lines=1)
    assert n["batches"] == 4
    assert q(db, "SELECT uuid, output_tokens FROM messages WHERE message_id = 'msg_B'") == [("r3", 77)]
    assert q1(db, "SELECT count(*) FROM tool_calls") == 1


def test_same_message_in_two_files_last_file_wins(db, projects):
    """A resumed session can repeat records in a second file; walk order decides, as before."""
    root, proj = projects
    write_jsonl(proj / "a.jsonl", [_streaming_partial("r1", "msg_W", "s1", "2026-04-10T00:00:01Z", 1)])
    write_jsonl(proj / "b.jsonl", [_streaming_partial("r2", "msg_W", "s1", "2026-04-10T00:00:02Z", 2)])
    order = [p.name for p in root.rglob("*.jsonl")]
    scan(root, db, MACHINE)
    winner = "r2" if order[-1] == "b.jsonl" else "r1"
    assert q(db, "SELECT uuid FROM messages WHERE message_id = 'msg_W'") == [(winner,)]
