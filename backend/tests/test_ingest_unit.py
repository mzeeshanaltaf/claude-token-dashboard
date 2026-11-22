"""Pure parts of the collector (no database needed)."""
import json
from datetime import datetime, timezone
from pathlib import Path

from claude_lens.collector.ingest import (
    _Record, _clean_json, _clean_text, _iter_lines, _parse_line, _parse_ts, _project_slug,
    dedup_records,
)


def _rec(uuid, mid=None, sid="s1"):
    return _Record({"uuid": uuid, "message_id": mid, "session_id": sid}, [])


def _uuids(records):
    return [r.msg["uuid"] for r in records]


def test_dedup_keeps_last_snapshot_per_message_id():
    recs = [_rec("u1"), _rec("r1", "m"), _rec("r2", "m"), _rec("r3", "m")]
    assert _uuids(dedup_records(recs)) == ["u1", "r3"]


def test_dedup_message_id_is_scoped_to_session():
    recs = [_rec("r1", "m", "s1"), _rec("r2", "m", "s2")]
    assert _uuids(dedup_records(recs)) == ["r1", "r2"]


def test_dedup_keeps_last_occurrence_per_uuid():
    a = _rec("u1")
    b = _rec("u1")
    out = dedup_records([a, _rec("u2"), b])
    assert _uuids(out) == ["u2", "u1"] and out[1] is b


def test_dedup_without_message_id_keeps_every_uuid():
    assert _uuids(dedup_records([_rec("a1"), _rec("a2")])) == ["a1", "a2"]


def test_iter_lines_stops_at_partial_line(tmp_path: Path):
    p = tmp_path / "x.jsonl"
    p.write_bytes(b'{"a":1}\n{"b":2}\n{"c":')
    assert list(_iter_lines(p, 0)) == [(b'{"a":1}\n', 8), (b'{"b":2}\n', 16)]
    assert list(_iter_lines(p, 8)) == [(b'{"b":2}\n', 16)]


def test_iter_lines_handles_crlf(tmp_path: Path):
    p = tmp_path / "x.jsonl"
    p.write_bytes(b'{"a":1}\r\n')
    assert list(_iter_lines(p, 0)) == [(b'{"a":1}\r\n', 9)]


def test_parse_ts():
    assert _parse_ts("2026-04-10T00:00:00Z") == datetime(2026, 4, 10, tzinfo=timezone.utc)
    assert _parse_ts("2026-04-10T00:00:00.5+02:00").utcoffset().total_seconds() == 7200
    assert _parse_ts("2026-04-10T00:00:00").tzinfo == timezone.utc
    assert _parse_ts("garbage") is None
    assert _parse_ts(None) is None
    assert _parse_ts(17) is None


def test_clean_text():
    assert _clean_text(None) is None
    assert _clean_text("a\x00b") == "ab"
    assert _clean_text("x\udc80y") == "x�y"
    assert _clean_text("ok \U0001F680") == "ok \U0001F680"
    assert _clean_text(5) == "5"
    assert _clean_text({"k": 1}) == '{"k": 1}'


def test_clean_json_only_rebuilds_when_needed():
    plain = json.dumps([{"name": "Read", "target": "a.py"}])
    assert _clean_json(plain) is plain
    emoji = json.dumps([{"target": "\U0001F680"}])  # a valid surrogate pair escape
    assert json.loads(_clean_json(emoji)) == [{"target": "\U0001F680"}]
    assert json.loads(_clean_json(json.dumps([{"target": "a\x00b"}]))) == [{"target": "ab"}]


def test_parse_line_title_and_skip():
    assert _parse_line(b'{"type":"ai-title","sessionId":"s1","aiTitle":" T "}\n', "p", "m") == ("title", ("s1", "T"))
    assert _parse_line(b"\n", "p", "m") is None
    assert _parse_line(b"{oops\n", "p", "m") is None
    assert _parse_line(b'{"type":"progress"}\n', "p", "m") is None


def test_parse_line_message_row():
    raw = json.dumps({
        "type": "assistant", "uuid": "a1", "sessionId": "s1", "timestamp": "2026-04-10T00:00:01Z",
        "isSidechain": True,
        "message": {"id": "m1", "content": [{"type": "tool_use", "id": "t1", "name": "Read",
                                             "input": {"file_path": "f.py"}}]},
    }).encode() + b"\n"
    kind, rec = _parse_line(raw, "proj", "pc")
    assert kind == "msg"
    assert rec.msg["machine"] == "pc" and rec.msg["project_slug"] == "proj"
    assert rec.msg["is_sidechain"] is True
    assert rec.msg["timestamp"] == datetime(2026, 4, 10, 0, 0, 1, tzinfo=timezone.utc)
    assert rec.tools[0]["timestamp"] == rec.msg["timestamp"]
    assert rec.tools[0]["tool_use_id"] == "t1"


def test_project_slug():
    root = Path("/x/projects")
    assert _project_slug(root / "C--a" / "s.jsonl", root) == "C--a"
    assert _project_slug(root / "C--a" / "s" / "subagents" / "x.jsonl", root) == "C--a"
