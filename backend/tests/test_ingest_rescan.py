"""Re-scanning must not duplicate or lose rows (ported from tests/test_scanner_rescan.py)."""
import json
import os

from claude_lens.collector.ingest import scan
from helpers import bump_mtime, q, q1, user_record, write_jsonl

MACHINE = "test-pc"


def _assistant_with_tool_use(uuid, msg_id, ts, output_tokens):
    return {
        "type": "assistant", "uuid": uuid, "parentUuid": "u1", "sessionId": "s1",
        "timestamp": ts, "isSidechain": False,
        "message": {
            "id": msg_id, "model": "claude-opus-4-7",
            "content": [{"type": "tool_use", "id": "tu-" + uuid, "name": "Read",
                         "input": {"file_path": "foo.py"}}],
            "usage": {"input_tokens": 10, "output_tokens": output_tokens},
        },
    }


def _count_tools(conn):
    return q1(conn, "SELECT count(*) FROM tool_calls WHERE tool_name = 'Read'")


def test_partial_line_at_eof_is_not_skipped_on_next_scan(db, projects):
    """A line mid-flush (no trailing newline) is picked up once it completes."""
    root, proj = projects
    path = proj / "s1.jsonl"
    rec_a = _assistant_with_tool_use("a1", "msg_A", "2026-04-10T00:00:01Z", 10)
    partial_b = json.dumps(_assistant_with_tool_use("a2", "msg_B", "2026-04-10T00:00:02Z", 20))
    half = len(partial_b) // 2
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(user_record()) + "\n")
        f.write(json.dumps(rec_a) + "\n")
        f.write(partial_b[:half])  # truncated, no "\n"

    scan(root, db, MACHINE)
    assert [r[0] for r in q(db, "SELECT uuid FROM messages ORDER BY uuid")] == ["a1", "u1"]
    stored = q1(db, "SELECT bytes_read FROM files")
    assert stored == path.stat().st_size - half, "offset stops at the last complete line"

    rec_c = _assistant_with_tool_use("a3", "msg_C", "2026-04-10T00:00:03Z", 30)
    with open(path, "a", encoding="utf-8") as f:
        f.write(partial_b[half:] + "\n")
        f.write(json.dumps(rec_c) + "\n")
    bump_mtime(path)

    scan(root, db, MACHINE)
    assert [r[0] for r in q(db, "SELECT uuid FROM messages ORDER BY uuid")] == ["a1", "a2", "a3", "u1"]


def test_rescan_with_same_content_does_not_duplicate_tool_calls(db, projects):
    """Full re-read (mtime changed, content unchanged) must not grow tool_calls."""
    root, proj = projects
    path = proj / "s1.jsonl"
    write_jsonl(path, [user_record(), _assistant_with_tool_use("a1", "msg_X", "2026-04-10T00:00:01Z", 42)])

    scan(root, db, MACHINE)
    assert _count_tools(db) == 1
    bump_mtime(path)  # same size, new mtime: re-read from offset 0
    n = scan(root, db, MACHINE)
    assert n["files"] == 1 and n["messages"] == 2
    assert _count_tools(db) == 1, "rescan must not duplicate tool_calls"


def test_unchanged_file_is_skipped_via_exact_mtime_roundtrip(db, projects):
    """The stored float8 mtime must compare equal to st_mtime after a round trip."""
    root, proj = projects
    path = proj / "s1.jsonl"
    write_jsonl(path, [user_record()])
    os.utime(path, (path.stat().st_atime, 1765432109.1234567))  # awkward fractional mtime
    scan(root, db, MACHINE)
    assert q1(db, "SELECT mtime FROM files") == path.stat().st_mtime
    assert scan(root, db, MACHINE)["files"] == 0


def test_full_rescan_ignores_offsets_and_backfills_tool_use_id(db, projects):
    root, proj = projects
    path = proj / "s1.jsonl"
    write_jsonl(path, [user_record(), _assistant_with_tool_use("a1", "msg_X", "2026-04-10T00:00:01Z", 42)])
    scan(root, db, MACHINE)
    # Simulate rows migrated from SQLite, which have no tool_use_id.
    db.execute("UPDATE tool_calls SET tool_use_id = NULL")
    db.commit()
    assert scan(root, db, MACHINE)["files"] == 0

    n = scan(root, db, MACHINE, full=True)
    assert n["files"] == 1 and n["messages"] == 2 and n["tools"] == 1
    assert q(db, "SELECT tool_use_id FROM tool_calls") == [("tu-a1",)]
    assert q1(db, "SELECT count(*) FROM messages") == 2


def test_offsets_are_per_machine(db, projects):
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [user_record()])
    assert scan(root, db, "pc-one")["files"] == 1
    assert scan(root, db, "pc-one")["files"] == 0
    assert scan(root, db, "pc-two")["files"] == 1
    assert q(db, "SELECT machine FROM files ORDER BY machine") == [("pc-one",), ("pc-two",)]
    assert q(db, "SELECT machine FROM messages") == [("pc-two",)]


def test_big_file_is_split_into_batches_and_resumes(db, projects):
    root, proj = projects
    path = proj / "s1.jsonl"
    recs = [user_record(uuid=f"u{i}", ts=f"2026-04-10T00:00:{i:02d}Z") for i in range(25)]
    write_jsonl(path, recs)
    n = scan(root, db, MACHINE, batch_lines=10)
    assert n["batches"] == 3 and n["messages"] == 25
    assert q1(db, "SELECT bytes_read FROM files") == path.stat().st_size
    assert q1(db, "SELECT count(*) FROM messages") == 25
