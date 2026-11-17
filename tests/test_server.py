import http.server
import json
import os
import socket
import sqlite3
import tempfile
import threading
import unittest
import urllib.request

from token_dashboard.db import init_db
from pathlib import Path

from token_dashboard.server import build_handler, _make_pricing_loader


class PricingLoaderTests(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "pricing.json"

    def _write(self, models, bump):
        self.path.write_text(json.dumps({"models": models}), encoding="utf-8")
        # Force a distinct mtime so the test doesn't depend on FS timestamp resolution.
        st = self.path.stat()
        os.utime(self.path, ns=(st.st_atime_ns, st.st_mtime_ns + bump))

    def test_picks_up_edits_without_restart(self):
        self._write({"a": 1}, 1_000_000)
        get = _make_pricing_loader(self.path)
        self.assertEqual(get()["models"], {"a": 1})
        self._write({"a": 1, "b": 2}, 2_000_000)
        self.assertEqual(get()["models"], {"a": 1, "b": 2})

    def test_keeps_last_good_copy_when_file_is_invalid(self):
        self._write({"a": 1}, 1_000_000)
        get = _make_pricing_loader(self.path)
        get()
        self.path.write_text("{ not json", encoding="utf-8")
        st = self.path.stat()
        os.utime(self.path, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000))
        self.assertEqual(get()["models"], {"a": 1})

    def test_raises_if_never_loaded_and_invalid(self):
        self.path.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            _make_pricing_loader(self.path)()


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "t.db")
        init_db(self.db)
        with sqlite3.connect(self.db) as c:
            c.execute("INSERT INTO messages (uuid, parent_uuid, session_id, project_slug, type, timestamp, model, input_tokens, output_tokens, cache_read_tokens, cache_create_5m_tokens, cache_create_1h_tokens, prompt_text, prompt_chars) VALUES ('u',NULL,'s','p','user','2026-04-19T00:00:00Z',NULL,0,0,0,0,0,'hi',2)")
            c.execute("INSERT INTO messages (uuid, parent_uuid, session_id, project_slug, type, timestamp, model, input_tokens, output_tokens, cache_read_tokens, cache_create_5m_tokens, cache_create_1h_tokens) VALUES ('a','u','s','p','assistant','2026-04-19T00:00:01Z','claude-haiku-4-5',1,1,0,0,0)")
            c.commit()
        self.port = _free_port()
        H = build_handler(self.db, projects_dir="/nonexistent")
        self.httpd = http.server.HTTPServer(("127.0.0.1", self.port), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()

    def _get(self, path):
        return urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}").read()

    def test_index_html(self):
        body = self._get("/")
        self.assertIn(b"Token Dashboard", body)

    def test_overview_json(self):
        body = json.loads(self._get("/api/overview"))
        self.assertIn("sessions", body)
        self.assertEqual(body["sessions"], 1)

    def test_prompts_json(self):
        body = json.loads(self._get("/api/prompts?limit=10"))
        self.assertIsInstance(body, list)

    def test_projects_json(self):
        body = json.loads(self._get("/api/projects"))
        self.assertIsInstance(body, list)
        self.assertEqual(body[0]["project_slug"], "p")

    def test_plan_json(self):
        body = json.loads(self._get("/api/plan"))
        self.assertIn("plan", body)
        self.assertIn("pricing", body)

    def test_head_returns_200_not_501(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/", method="HEAD")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.read(), b"")

    def test_head_api_endpoint(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/overview", method="HEAD")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.read(), b"")


if __name__ == "__main__":
    unittest.main()
