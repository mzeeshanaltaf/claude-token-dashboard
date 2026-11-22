import json
import os
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from claude_lens.config import load_env_files
from claude_lens.db.migrate import migrate
from claude_lens.db.pool import set_search_path
from helpers import drop_test_schema, new_test_schema_name

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


@pytest.fixture(scope="session")
def pg_url():
    url = _test_database_url()
    if not url:
        pytest.skip("no TEST_DATABASE_URL / DATABASE_URL available")
    return url


@pytest.fixture(scope="session")
def pg_schema(pg_url):
    """A migrated throwaway schema for the whole test session, dropped at the end."""
    schema = new_test_schema_name()
    conn = psycopg.connect(pg_url, connect_timeout=15)
    try:
        migrate(conn, schema)
        yield schema
    finally:
        drop_test_schema(conn, schema)
        conn.close()


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


@pytest.fixture
def projects(tmp_path):
    """A projects root with one project folder; returns (root, project_dir)."""
    root = tmp_path / "projects"
    proj = root / "C--work-sample"
    proj.mkdir(parents=True)
    return root, proj
