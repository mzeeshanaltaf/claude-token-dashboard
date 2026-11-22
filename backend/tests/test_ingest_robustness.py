"""Inputs SQLite accepted but Postgres would reject; one bad line must not sink a batch."""
from claude_lens.collector.ingest import scan
from helpers import q, q1, user_record, write_jsonl

MACHINE = "test-pc"


def test_nul_and_lone_surrogates_are_cleaned(db, projects):
    root, proj = projects
    bad_tool = {
        "type": "assistant", "uuid": "a1", "sessionId": "s1", "timestamp": "2026-04-10T00:00:01Z",
        "message": {"id": "m1", "content": [
            {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "echo \x00 \ud800"}},
        ]},
    }
    write_jsonl(proj / "s1.jsonl", [user_record(text="a\x00b \ud83d c"), bad_tool])
    n = scan(root, db, MACHINE)
    assert n["messages"] == 2
    assert q1(db, "SELECT prompt_text FROM messages WHERE uuid = 'u1'") == "ab � c"
    assert q1(db, "SELECT target FROM tool_calls WHERE tool_name = 'Bash'") == "echo  �"
    assert q1(db, "SELECT tool_calls_json FROM messages WHERE uuid = 'a1'") == [
        {"name": "Bash", "target": "echo  �"}
    ]


def test_valid_emoji_survives(db, projects):
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [user_record(text="ship it \U0001F680")])
    scan(root, db, MACHINE)
    assert q1(db, "SELECT prompt_text FROM messages") == "ship it \U0001F680"


def test_unusable_records_are_skipped_not_fatal(db, projects):
    root, proj = projects
    path = proj / "s1.jsonl"
    write_jsonl(path, [
        user_record(uuid="bad-ts", ts="not a timestamp"),
        user_record(uuid="num-ts", ts=12345),
        {"type": None, "uuid": "no-type", "sessionId": "s1", "timestamp": "2026-04-10T00:00:00Z"},
        {"type": "user", "uuid": None, "sessionId": "s1", "timestamp": "2026-04-10T00:00:00Z"},
        {"type": "assistant", "uuid": "bad-usage", "sessionId": "s1", "timestamp": "2026-04-10T00:00:00Z",
         "message": {"usage": {"input_tokens": "lots"}}},
        user_record(uuid="good"),
    ])
    with open(path, "a", encoding="utf-8") as f:
        f.write("{not json}\n\n")
    scan(root, db, MACHINE)
    assert q(db, "SELECT uuid FROM messages") == [("good",)]
    assert q1(db, "SELECT bytes_read FROM files") == path.stat().st_size


def test_naive_timestamp_is_treated_as_utc(db, projects):
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [user_record(ts="2026-04-10T05:06:07.123")])
    scan(root, db, MACHINE)
    assert q1(db, "SELECT to_char(timestamp AT TIME ZONE 'UTC', 'HH24:MI:SS.MS') FROM messages") == "05:06:07.123"


def test_huge_prompt_inserts_and_is_searchable(db, projects):
    root, proj = projects
    # ~1.4M chars of distinct words: unbounded, its tsvector would exceed the 1 MB cap.
    text = "needle " + " ".join(f"w{i}" for i in range(200_000))
    write_jsonl(proj / "s1.jsonl", [user_record(text=text), user_record(uuid="u2", text="unrelated")])
    scan(root, db, MACHINE)
    assert q1(db, "SELECT prompt_chars FROM messages WHERE uuid = 'u1'") == len(text)
    hits = q(db, "SELECT uuid FROM messages WHERE prompt_tsv @@ plainto_tsquery('english', 'needle')")
    assert hits == [("u1",)]
