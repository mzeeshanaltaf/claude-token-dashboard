import psycopg
import pytest

from claude_lens.db.migrate import applied_versions, discover, migrate
from helpers import drop_test_schema, new_test_schema_name, q, q1

EXPECTED_TABLES = {
    "messages", "tool_calls", "files", "session_titles", "settings", "dismissed_tips",
    "skill_catalog", "sync_runs", "users", "auth_sessions", "schema_migrations",
}


def test_discover_finds_init_migration():
    migs = discover()
    assert migs[0].version == 1 and migs[0].name == "001_init"


def test_discover_rejects_bad_names(tmp_path):
    (tmp_path / "init.sql").write_text("SELECT 1")
    with pytest.raises(ValueError, match="bad migration file name"):
        discover(tmp_path)


def test_discover_rejects_duplicate_versions(tmp_path):
    (tmp_path / "001_a.sql").write_text("SELECT 1")
    (tmp_path / "001_b.sql").write_text("SELECT 1")
    with pytest.raises(ValueError, match="duplicate"):
        discover(tmp_path)


@pytest.fixture
def fresh_schema(pg_url):
    schema = new_test_schema_name()
    conn = psycopg.connect(pg_url, connect_timeout=15)
    yield conn, schema
    drop_test_schema(conn, schema)
    conn.close()


def test_migrate_creates_schema_once_and_records_versions(fresh_schema, tmp_path):
    conn, schema = fresh_schema
    assert migrate(conn, schema) == [1]
    assert migrate(conn, schema) == []  # idempotent
    assert applied_versions(conn) == [1]
    tables = {r[0] for r in q(conn, "SELECT table_name FROM information_schema.tables"
                                    " WHERE table_schema = %s", (schema,))}
    assert tables == EXPECTED_TABLES
    assert q1(conn, "SHOW search_path") == schema
    assert q1(conn, "SELECT applied_at IS NOT NULL FROM schema_migrations WHERE version = 1")


def test_failed_migration_rolls_back(fresh_schema, tmp_path):
    conn, schema = fresh_schema
    (tmp_path / "001_ok.sql").write_text("CREATE TABLE t1 (id int);")
    (tmp_path / "002_bad.sql").write_text("CREATE TABLE t2 (id int); SELECT * FROM no_such_table;")
    with pytest.raises(psycopg.errors.UndefinedTable):
        migrate(conn, schema, tmp_path)
    conn.rollback()
    assert applied_versions(conn) == [1]
    assert q1(conn, "SELECT to_regclass('t2')") is None
    conn.rollback()


def test_migrate_requires_idle_connection(fresh_schema):
    conn, schema = fresh_schema
    conn.execute("SELECT 1")  # opens a transaction
    with pytest.raises(RuntimeError, match="idle"):
        migrate(conn, schema)
    conn.rollback()
