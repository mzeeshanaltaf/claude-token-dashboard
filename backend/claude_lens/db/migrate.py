"""Apply `migrations/NNN_*.sql` to the Claude Lens schema, in order, exactly once.

Each migration runs in its own transaction together with its
`schema_migrations` row, so a failed migration leaves no trace. A transaction-
level advisory lock (keyed on the schema name) serialises concurrent runners:
the API container and the local collector may both call `migrate()` at startup.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_NAME_RE = re.compile(r"^(\d{3})_[A-Za-z0-9_]+\.sql$")


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path

    def read(self) -> str:
        return self.path.read_text(encoding="utf-8")


def discover(directory: Path = MIGRATIONS_DIR) -> List[Migration]:
    """Return the migrations in `directory`, sorted by version. Duplicates are an error."""
    found: dict[int, Migration] = {}
    for p in sorted(directory.glob("*.sql")):
        m = _NAME_RE.match(p.name)
        if not m:
            raise ValueError(f"bad migration file name: {p.name} (want NNN_name.sql)")
        version = int(m.group(1))
        if version in found:
            raise ValueError(f"duplicate migration version {version}: {found[version].name}, {p.name}")
        found[version] = Migration(version, p.stem, p)
    return [found[v] for v in sorted(found)]


def _lock(conn: psycopg.Connection, schema: str) -> None:
    conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"claude_lens.migrate.{schema}",))


def migrate(
    conn: psycopg.Connection, schema: str, directory: Optional[Path] = None
) -> List[int]:
    """Create `schema` if needed and apply pending migrations. Returns the versions applied.

    Leaves the connection's `search_path` set to `schema`. The connection must be
    idle (no open transaction) so each migration commits on its own.
    """
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise RuntimeError("migrate() needs an idle connection (commit or roll back first)")
    ident = sql.Identifier(schema)
    migrations = discover(directory or MIGRATIONS_DIR)

    with conn.transaction():
        _lock(conn, schema)
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(ident))
        conn.execute(sql.SQL("SET search_path TO {}").format(ident))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY,"
            " name TEXT NOT NULL,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        known = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}

    applied: List[int] = []
    for mig in migrations:
        if mig.version in known:
            continue  # skip the round trips; pending ones are re-checked under the lock
        with conn.transaction():
            _lock(conn, schema)
            done = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE version = %s", (mig.version,)
            ).fetchone()
            if done:
                continue
            conn.execute(mig.read())
            conn.execute(
                "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)",
                (mig.version, mig.name),
            )
            applied.append(mig.version)
    return applied


def applied_versions(conn: psycopg.Connection) -> List[int]:
    """Versions recorded in `schema_migrations` (empty if the table doesn't exist)."""
    if conn.execute("SELECT to_regclass('schema_migrations')").fetchone()[0] is None:
        return []
    return [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
