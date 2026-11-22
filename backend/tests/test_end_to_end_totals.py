"""End-to-end accounting invariant: JSONL on disk → collector → overview numbers.

Ported from tests/test_end_to_end_totals.py: a hand-computed fixture goes
through the real `scan` pipeline into Postgres, and every token-bucket SUM in
`overview_totals` (and the API's overview cost) must match.
"""
from claude_lens.collector.ingest import scan
from claude_lens.core.costs import overview_costs
from claude_lens.core.pricing import load_pricing
from claude_lens.db.queries.analytics import model_breakdown, overview_totals
from helpers import q, q1, write_jsonl


def _user(uuid, ts, text):
    return {"type": "user", "uuid": uuid, "sessionId": "s1", "timestamp": ts,
            "isSidechain": False, "message": {"role": "user", "content": text}}


def _assistant(uuid, parent, msg_id, ts, usage, tool_uses=None):
    content = [{"type": "text", "text": "..."}] + list(tool_uses or [])
    return {"type": "assistant", "uuid": uuid, "parentUuid": parent, "sessionId": "s1",
            "timestamp": ts, "isSidechain": False,
            "message": {"id": msg_id, "model": "claude-opus-4-7", "content": content,
                        "usage": usage}}


def _usage(inp, out, cr, c5, c1):
    return {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": cr,
            "cache_creation": {"ephemeral_5m_input_tokens": c5, "ephemeral_1h_input_tokens": c1}}


def test_scan_totals_match_hand_computed_sums(db, projects):
    root, proj = projects
    write_jsonl(proj / "s1.jsonl", [
        _user("u1", "2026-04-10T00:00:00Z", "prompt 1"),
        # streaming partial for msg_A, evicted by the final snapshot below
        _assistant("a1", "u1", "msg_A", "2026-04-10T00:00:01Z", _usage(100, 10, 500, 200, 0)),
        _assistant("a2", "u1", "msg_A", "2026-04-10T00:00:02Z", _usage(100, 200, 500, 200, 50)),
        _user("u2", "2026-04-10T00:01:00Z", "prompt 2"),
        _assistant("a3", "u2", "msg_B", "2026-04-10T00:01:01Z", _usage(50, 80, 300, 0, 100),
                   tool_uses=[{"type": "tool_use", "id": "tu1", "name": "Read",
                               "input": {"file_path": "foo.py"}}]),
        _assistant("a4", "u2", "msg_C", "2026-04-10T00:01:02Z", _usage(60, 120, 350, 30, 0)),
    ])
    scan(root, db, "test-pc")

    totals = overview_totals(db)
    # a1 evicted; a2 + a3 + a4 survive
    assert totals["sessions"] == 1
    assert totals["turns"] == 2
    assert totals["input_tokens"] == 100 + 50 + 60
    assert totals["output_tokens"] == 200 + 80 + 120
    assert totals["cache_read_tokens"] == 500 + 300 + 350
    assert totals["cache_create_5m_tokens"] == 200 + 0 + 30
    assert totals["cache_create_1h_tokens"] == 50 + 100 + 0

    assert sorted(r[0] for r in q(db, "SELECT uuid FROM messages WHERE type = 'assistant'")) == [
        "a2", "a3", "a4"]
    assert q1(db, "SELECT count(*) FROM tool_calls WHERE tool_name = 'Read'") == 1

    # opus-4-7: input $5, output $25, cache_read $0.50, 5m $6.25, 1h $10 per million
    costs = overview_costs(model_breakdown(db), load_pricing())
    expected = (210 * 5 + 400 * 25 + 1150 * 0.5 + 230 * 6.25 + 150 * 10) / 1_000_000
    assert costs["cost_usd"] == round(expected, 4)
    assert costs["cost_cache_create_usd"] == round((230 * 6.25 + 150 * 10) / 1_000_000, 4)
