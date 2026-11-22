"""Session titles (ported from tests/test_scanner_titles.py, scan part).

The query-side assertions (recent_sessions etc.) move to phase 03 with the
queries; here we check what lands in Postgres.
"""
from claude_lens.collector.ingest import scan
from helpers import append_jsonl, bump_mtime, q, q1, user_record, write_jsonl

MACHINE = "test-pc"


def _assistant(uuid, parent, sid, ts):
    return {
        "type": "assistant", "uuid": uuid, "parentUuid": parent, "sessionId": sid,
        "timestamp": ts, "isSidechain": False,
        "message": {"id": "m-" + uuid, "model": "claude-opus-4-7",
                    "usage": {"input_tokens": 5, "output_tokens": 5}},
    }


def _title(sid, text):
    return {"type": "ai-title", "sessionId": sid, "aiTitle": text}


def _session_title(conn, sid="s1"):
    return q1(conn, "SELECT title FROM session_titles WHERE session_id = %s", (sid,))


def test_latest_title_wins(db, projects):
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [
        _title("s1", "First guess"),
        user_record(text="hello"),
        _assistant("a1", "u1", "s1", "2026-04-10T00:00:01Z"),
        _title("s1", "Refined title"),  # refined later in the file: last one wins
    ])
    n = scan(root, db, MACHINE)
    assert n["titles"] == 2
    assert _session_title(db) == "Refined title"


def test_latest_title_wins_across_batches(db, projects):
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [_title("s1", "One"), user_record(), _title("s1", "Two")])
    scan(root, db, MACHINE, batch_lines=1)
    assert _session_title(db) == "Two"


def test_legacy_summary_record(db, projects):
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [{"type": "summary", "sessionId": "s1", "summary": " Do thing "}])
    scan(root, db, MACHINE)
    assert _session_title(db) == "Do thing"


def test_full_rescan_backfills_titles(db, projects):
    """Replaces the SQLite offset-reset migration test: `full=True` re-reads everything."""
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [
        _title("s1", "Backfilled"), user_record(), _assistant("a1", "u1", "s1", "2026-04-10T00:00:01Z"),
    ])
    scan(root, db, MACHINE)
    db.execute("DELETE FROM session_titles")
    db.commit()
    assert scan(root, db, MACHINE)["files"] == 0
    scan(root, db, MACHINE, full=True)
    assert _session_title(db) == "Backfilled"


def test_session_without_title_yields_none(db, projects):
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [user_record(), _assistant("a1", "u1", "s1", "2026-04-10T00:00:01Z")])
    scan(root, db, MACHINE)
    assert _session_title(db) is None


def test_title_does_not_inflate_message_or_token_counts(db, projects):
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [
        _title("s1", "T"), user_record(), _assistant("a1", "u1", "s1", "2026-04-10T00:00:01Z"),
    ])
    n = scan(root, db, MACHINE)
    assert n["messages"] == 2 and n["titles"] == 1
    # One user turn, 10 assistant tokens (5 in + 5 out).
    assert q1(db, "SELECT count(*) FROM messages WHERE type = 'user'") == 1
    assert q1(db, "SELECT sum(input_tokens + output_tokens) FROM messages") == 10


def test_new_title_on_incremental_rescan_updates(db, projects):
    root, proj = projects
    path = proj / "s1.jsonl"
    write_jsonl(path, [_title("s1", "Old"), user_record()])
    scan(root, db, MACHINE)
    append_jsonl(path, [_title("s1", "New")])
    bump_mtime(path)
    scan(root, db, MACHINE)
    assert _session_title(db) == "New"
