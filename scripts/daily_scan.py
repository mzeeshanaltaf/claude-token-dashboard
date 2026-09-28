"""Background scan that keeps the SQLite DB current between dashboard launches.

Why: the scanner is incremental, but after a week of not opening the dashboard
there are thousands of new JSONL lines to ingest and startup takes minutes.
Running this once a day spreads that work out so `cli.py dashboard` starts fast.

Run by the scheduled task that scripts/install_daily_scan.ps1 registers. Safe to
run by hand too: `python scripts/daily_scan.py`. Honours the same env vars as
cli.py (TOKEN_DASHBOARD_DB, CLAUDE_PROJECTS_DIR). Logs to
~/.claude/token-dashboard-scan.log (rotated at 1 MB).
"""
from __future__ import annotations

import logging
import os
import sqlite3
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from token_dashboard.db import init_db, default_db_path  # noqa: E402
from token_dashboard.scanner import scan_dir  # noqa: E402

# The dashboard server re-scans every 30s; if it happens to hold the write lock
# when we start, wait and retry rather than failing the day's run.
ATTEMPTS = 3
RETRY_DELAY_S = 60


def _log() -> logging.Logger:
    path = Path.home() / ".claude" / "token-dashboard-scan.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log = logging.getLogger("daily_scan")
    log.setLevel(logging.INFO)
    log.addHandler(handler)
    # Under pythonw there is no console; stderr is None.
    if sys.stderr is not None:
        log.addHandler(logging.StreamHandler())
    return log


def main() -> int:
    log = _log()
    db = os.environ.get("TOKEN_DASHBOARD_DB") or str(default_db_path())
    projects = os.environ.get("CLAUDE_PROJECTS_DIR") or str(Path.home() / ".claude" / "projects")

    for attempt in range(1, ATTEMPTS + 1):
        started = time.monotonic()
        try:
            init_db(db)
            n = scan_dir(projects, db)
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < ATTEMPTS:
                log.warning("database locked (attempt %d/%d), retrying in %ds", attempt, ATTEMPTS, RETRY_DELAY_S)
                time.sleep(RETRY_DELAY_S)
                continue
            log.exception("scan failed")
            return 1
        except Exception:
            log.exception("scan failed")
            return 1
        log.info(
            "scanned %d files, %d messages, %d tool calls in %.1fs",
            n["files"], n["messages"], n["tools"], time.monotonic() - started,
        )
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
