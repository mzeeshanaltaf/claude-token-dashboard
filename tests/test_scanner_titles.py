"""Session titles: Claude Code writes standalone `ai-title` records (no
top-level uuid) that name the session. The scanner must capture the latest
one per session and surface it through the session/prompt queries."""
import json
import os
import sqlite3
import tempfile
import time
import unittest

from token_dashboard.db import (
    init_db, recent_sessions, project_sessions, expensive_prompts, session_turns,
)
from token_dashboard.scanner import scan_dir, _session_title


def _user(uuid, sid, ts, text):
    return {
        "type": "user", "uuid": uuid, "sessionId": sid, "timestamp": ts,
        "isSidechain": False, "message": {"role": "user", "content": text},
    }


def _assistant(uuid, parent, sid, ts):
    return {
        "type": "assistant", "uuid": uuid, "parentUuid": parent,
        "sessionId": sid, "timestamp": ts, "isSidechain": False,
        "message": {"id": "m-" + uuid, "model": "claude-opus-4-7",
                    "usage": {"input_tokens": 5, "output_tokens": 5}},
    }


def _write(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


class SessionTitleExtractionTests(unittest.TestCase):
    def test_ai_title_record(self):
        self.assertEqual(
            _session_title({"type": "ai-title", "sessionId": "s1", "aiTitle": " Fix bug "}),
            ("s1", "Fix bug"),
        )

    def test_legacy_summary_record(self):
        self.assertEqual(
            _session_title({"type": "summary", "sessionId": "s1", "summary": "Do thing"}),
            ("s1", "Do thing"),
        )

    def test_non_title_record_ignored(self):
        self.assertIsNone(_session_title({"type": "assistant", "uuid": "a1"}))

    def test_blank_title_ignored(self):
        self.assertIsNone(_session_title({"type": "ai-title", "sessionId": "s1", "aiTitle": "  "}))
        self.assertIsNone(_session_title({"type": "ai-title", "aiTitle": "x"}))


class SessionTitleScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "t.db")
        self.proj_root = os.path.join(self.tmp, "projects")
        self.proj_dir = os.path.join(self.proj_root, "C--work-sample")
        os.makedirs(self.proj_dir)
        init_db(self.db)

    def _path(self):
        return os.path.join(self.proj_dir, "s1.jsonl")

    def test_latest_title_wins_and_surfaces_in_queries(self):
        _write(self._path(), [
            {"type": "ai-title", "sessionId": "s1", "aiTitle": "First guess"},
            _user("u1", "s1", "2026-04-10T00:00:00Z", "hello"),
            _assistant("a1", "u1", "s1", "2026-04-10T00:00:01Z"),
            # Title refined later in the file — last one must win.
            {"type": "ai-title", "sessionId": "s1", "aiTitle": "Refined title"},
        ])
        n = scan_dir(self.proj_root, self.db)
        self.assertEqual(n["titles"], 2)

        with sqlite3.connect(self.db) as c:
            row = c.execute(
                "SELECT title FROM session_titles WHERE session_id='s1'"
            ).fetchone()
        self.assertEqual(row[0], "Refined title")

        sess = {r["session_id"]: r for r in recent_sessions(self.db)}
        self.assertEqual(sess["s1"]["title"], "Refined title")

        proj = {r["session_id"]: r for r in project_sessions(self.db, "C--work-sample")}
        self.assertEqual(proj["s1"]["title"], "Refined title")

        prompts = expensive_prompts(self.db)
        self.assertEqual(prompts[0]["title"], "Refined title")

        turns = session_turns(self.db, "s1")
        self.assertTrue(turns)
        self.assertTrue(all(t["title"] == "Refined title" for t in turns))

    def test_backfill_replays_already_scanned_files(self):
        """Simulates an existing DB: the file is fully scanned, then the
        session_titles table is dropped (as if the pre-title schema). init_db's
        migration must reset offsets so the next scan captures the title."""
        _write(self._path(), [
            {"type": "ai-title", "sessionId": "s1", "aiTitle": "Backfilled"},
            _user("u1", "s1", "2026-04-10T00:00:00Z", "hello"),
            _assistant("a1", "u1", "s1", "2026-04-10T00:00:01Z"),
        ])
        scan_dir(self.proj_root, self.db)

        # Emulate a DB created before the feature existed.
        with sqlite3.connect(self.db) as c:
            c.execute("DROP TABLE session_titles")
            c.commit()

        init_db(self.db)  # migration should clear file offsets
        scan_dir(self.proj_root, self.db)

        sess = {r["session_id"]: r for r in recent_sessions(self.db)}
        self.assertEqual(sess["s1"]["title"], "Backfilled")

    def test_session_without_title_yields_none(self):
        _write(self._path(), [
            _user("u1", "s1", "2026-04-10T00:00:00Z", "hello"),
            _assistant("a1", "u1", "s1", "2026-04-10T00:00:01Z"),
        ])
        scan_dir(self.proj_root, self.db)
        sess = {r["session_id"]: r for r in recent_sessions(self.db)}
        self.assertIsNone(sess["s1"]["title"])

    def test_title_does_not_inflate_message_or_token_counts(self):
        _write(self._path(), [
            {"type": "ai-title", "sessionId": "s1", "aiTitle": "T"},
            _user("u1", "s1", "2026-04-10T00:00:00Z", "hello"),
            _assistant("a1", "u1", "s1", "2026-04-10T00:00:01Z"),
        ])
        scan_dir(self.proj_root, self.db)
        sess = {r["session_id"]: r for r in recent_sessions(self.db)}
        # One user turn, 10 assistant tokens (5 in + 5 out) — the title record
        # must not be counted as a message or add to the token sums.
        self.assertEqual(sess["s1"]["turns"], 1)
        self.assertEqual(sess["s1"]["tokens"], 10)

    def test_new_title_on_incremental_rescan_updates(self):
        _write(self._path(), [
            {"type": "ai-title", "sessionId": "s1", "aiTitle": "Old"},
            _user("u1", "s1", "2026-04-10T00:00:00Z", "hello"),
        ])
        scan_dir(self.proj_root, self.db)

        with open(self._path(), "a", encoding="utf-8") as f:
            f.write(json.dumps({"type": "ai-title", "sessionId": "s1", "aiTitle": "New"}) + "\n")
        future = time.time() + 10
        os.utime(self._path(), (future, future))

        scan_dir(self.proj_root, self.db)
        with sqlite3.connect(self.db) as c:
            title = c.execute(
                "SELECT title FROM session_titles WHERE session_id='s1'"
            ).fetchone()[0]
        self.assertEqual(title, "New")


if __name__ == "__main__":
    unittest.main()
