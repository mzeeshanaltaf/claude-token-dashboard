"""Directory walk (ported from tests/test_scanner_walk.py): same totals on the fixture."""
import shutil
from datetime import datetime, timezone
from pathlib import Path

from claude_lens.collector.ingest import scan
from helpers import q, q1, write_jsonl, user_record

FIXTURE = Path(__file__).parent / "fixtures" / "sample_session.jsonl"
MACHINE = "test-pc"


def _with_fixture(projects):
    root, proj = projects
    shutil.copy(FIXTURE, proj / "s1.jsonl")
    return root, proj


def test_scan_writes_messages_and_tools(db, projects):
    root, _ = _with_fixture(projects)
    n = scan(root, db, MACHINE)
    assert n["messages"] == 3
    assert n["tools"] == 2  # 1 tool_use + 1 tool_result
    assert n["files"] == 1
    assert q1(db, "SELECT project_slug FROM messages WHERE uuid = 'u1'") == "C--work-sample"
    assert q1(db, "SELECT count(*) FROM messages") == 3
    assert q1(db, "SELECT count(*) FROM tool_calls") == 2


def test_rescan_skips_unchanged_files(db, projects):
    root, _ = _with_fixture(projects)
    n1 = scan(root, db, MACHINE)
    n2 = scan(root, db, MACHINE)
    assert n1["messages"] == 3
    assert n2["messages"] == 0 and n2["files"] == 0


def test_rescan_picks_up_appended_lines(db, projects):
    root, proj = _with_fixture(projects)
    scan(root, db, MACHINE)
    with open(proj / "s1.jsonl", "a", encoding="utf-8") as f:
        f.write('{"type":"assistant","uuid":"a2","sessionId":"s1","timestamp":"2026-04-10T00:00:03Z",'
                '"isSidechain":false,"message":{"model":"claude-haiku-4-5",'
                '"usage":{"input_tokens":1,"output_tokens":1}}}\n')
    n2 = scan(root, db, MACHINE)
    assert n2["messages"] == 1
    assert q1(db, "SELECT count(*) FROM messages") == 4


def test_column_types_and_values(db, projects):
    root, _ = _with_fixture(projects)
    scan(root, db, MACHINE)
    row = q(db, "SELECT timestamp, is_sidechain, machine, cwd, git_branch, cc_version, entrypoint,"
                " prompt_text, prompt_chars FROM messages WHERE uuid = 'u1'")[0]
    assert row == (datetime(2026, 4, 10, tzinfo=timezone.utc), False, MACHINE, "/c/work", "main",
                   "2.1.98", "cli", "plan the refactor", 17)
    a1 = q(db, "SELECT model, input_tokens, output_tokens, cache_read_tokens, tool_calls_json"
               " FROM messages WHERE uuid = 'a1'")[0]
    assert a1 == ("claude-opus-4-7", 10, 5, 50, [{"name": "Read", "target": "foo.py"}])
    tools = q(db, "SELECT tool_name, target, tool_use_id, result_tokens, is_error, message_uuid"
                  " FROM tool_calls ORDER BY id")
    assert tools == [
        ("Read", "foo.py", "tu1", None, 0, "a1"),
        ("_tool_result", "tu1", "tu1", len("file contents") // 4, 0, "u2"),
    ]


def test_nested_files_take_the_top_level_project_slug(db, projects):
    root, proj = projects
    sub = proj / "s1" / "subagents"
    sub.mkdir(parents=True)
    write_jsonl(sub / "agent-x.jsonl", [user_record(uuid="x1")])
    scan(root, db, MACHINE)
    assert q1(db, "SELECT project_slug FROM messages WHERE uuid = 'x1'") == "C--work-sample"


def test_missing_root_returns_zero_totals(db, tmp_path):
    n = scan(tmp_path / "nope", db, MACHINE)
    assert n == {"messages": 0, "tools": 0, "titles": 0, "files": 0, "batches": 0}
