import json
import os
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from claude_lens.config import load_env_files
from claude_lens.db.migrate import migrate
from claude_lens.db.pool import set_search_path
from helpers import ADMIN_PASS, ADMIN_USER, drop_test_schema, login, new_test_schema_name

FIXTURES = Path(__file__).parent / "fixtures"

# Every table 001_init.sql creates (schema_migrations is kept between tests).
DATA_TABLES = (
    "messages", "tool_calls", "files", "session_titles", "settings", "dismissed_tips",
    "skill_catalog", "sync_runs", "auth_sessions", "users",
)


def pytest_collection_modifyitems(items):
    """Tag every test that needs Postgres, so `pytest -m "not db"` runs offline."""
    for item in items:
        if "pg_url" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.db)


@pytest.fixture(autouse=True)
def _restore_environ():
    """`load_settings()` (called by the CLI) copies .env.local into os.environ; undo that."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture(autouse=True)
def _sync_log(tmp_path, monkeypatch):
    """Keep `claude-lens scan` from writing to the real ~/.claude/claude-lens-sync.log."""
    path = tmp_path / "logs" / "claude-lens-sync.log"
    monkeypatch.setenv("CLAUDE_LENS_SYNC_LOG", str(path))
    return path


@pytest.fixture
def load_fixture():
    def _load(name: str) -> dict:
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return _load


def _test_database_url():
    """TEST_DATABASE_URL, else DATABASE_URL, from the env or the repo-root env files.

    The env files are read into a copy, so os.environ (and test_config) stay untouched.
    """
    env = dict(os.environ)
    load_env_files(environ=env)
    return env.get("TEST_DATABASE_URL") or env.get("DATABASE_URL") or None


class _SecretURL(str):
    """A connection string whose repr hides it: pytest prints fixture values in tracebacks."""

    def __repr__(self) -> str:
        return "'<DATABASE_URL redacted>'"


@pytest.fixture(scope="session")
def pg_url():
    url = _test_database_url()
    if not url:
        pytest.skip("no TEST_DATABASE_URL / DATABASE_URL available")
    return _SecretURL(url)


@pytest.fixture(scope="session")
def pg_schema(pg_url):
    """A migrated throwaway schema for the whole test session, dropped at the end.

    The drop uses a fresh connection: one held open for the whole (~10 min) run
    may have been closed by the server by then, which used to leave the schema behind.
    """
    schema = new_test_schema_name()
    with psycopg.connect(pg_url, connect_timeout=15) as conn:
        migrate(conn, schema)
    try:
        yield schema
    finally:
        with psycopg.connect(pg_url, connect_timeout=15) as conn:
            drop_test_schema(conn, schema)


@pytest.fixture(scope="session")
def _pg_session_conn(pg_url, pg_schema):
    conn = psycopg.connect(pg_url, connect_timeout=15)
    set_search_path(conn, pg_schema)
    yield conn
    conn.close()


@pytest.fixture
def db(_pg_session_conn):
    """An idle connection to the test schema, with every data table emptied."""
    conn = _pg_session_conn
    conn.rollback()
    conn.execute(
        sql.SQL("TRUNCATE {} RESTART IDENTITY CASCADE").format(
            sql.SQL(", ").join(sql.Identifier(t) for t in DATA_TABLES)
        )
    )
    conn.commit()
    yield conn
    conn.rollback()


# --- API -------------------------------------------------------------------------

@pytest.fixture(scope="session")
def api_settings(pg_url, pg_schema):
    from claude_lens.config import Settings
    return Settings.from_env({
        "DATABASE_URL": pg_url, "DB_SCHEMA": pg_schema,
        "ADMIN_USERNAME": ADMIN_USER, "ADMIN_PASSWORD": ADMIN_PASS,
        "COOKIE_SECURE": "false",
    })


@pytest.fixture(scope="session")
def _api_client(api_settings):
    """One app (and pool) for the whole session: startup costs seconds over the network."""
    from fastapi.testclient import TestClient
    from claude_lens.api.main import create_app
    app = create_app(api_settings, pool_max=3)
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def _admin_hash():
    from claude_lens.core.passwords import hash_password
    return hash_password(ADMIN_PASS)


@pytest.fixture
def anon(db, _api_client, _admin_hash):
    """A logged-out TestClient over an emptied schema that holds just the admin user."""
    db.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)",
               (ADMIN_USER, _admin_hash))
    db.commit()
    _api_client.app.state.lockout.clear()
    _api_client.cookies.clear()
    yield _api_client
    _api_client.cookies.clear()


@pytest.fixture
def client(anon):
    """A TestClient logged in as the admin."""
    r = login(anon)
    assert r.status_code == 200, r.text
    return anon


@pytest.fixture
def projects(tmp_path):
    """A projects root with one project folder; returns (root, project_dir)."""
    root = tmp_path / "projects"
    proj = root / "C--work-sample"
    proj.mkdir(parents=True)
    return root, proj
