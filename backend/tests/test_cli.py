import shutil
from pathlib import Path

import psycopg
import pytest

from claude_lens import cli
from claude_lens.cli import build_parser, main
from helpers import q, q1

COMMANDS = ["scan", "migrate-sqlite", "status", "set-password"]
FIXTURE = Path(__file__).parent / "fixtures" / "sample_session.jsonl"


def test_help_lists_all_subcommands(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for name in COMMANDS:
        assert name in out


def test_set_password_needs_a_username():
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["set-password"])
    assert exc.value.code == 2


def _answers(monkeypatch, *values):
    it = iter(values)
    monkeypatch.setattr(cli, "_getpass", lambda prompt="": next(it))


def test_set_password_rejects_mismatch_and_short(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    _answers(monkeypatch, "longenough1", "different22")
    assert main(["set-password", "admin"]) == 1
    assert "don't match" in capsys.readouterr().err
    _answers(monkeypatch, "short", "short")
    assert main(["set-password", "admin"]) == 1
    assert "at least 8" in capsys.readouterr().err


def test_command_is_required():
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args([])
    assert exc.value.code == 2


def test_scan_flags_parse():
    args = build_parser().parse_args(["scan", "--full", "--projects-dir", "x", "--batch-lines", "7"])
    assert args.full and args.projects_dir == "x" and args.batch_lines == 7


def test_scan_rejects_missing_projects_dir(tmp_path, capsys, monkeypatch, _sync_log):
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    assert main(["scan", "--projects-dir", str(tmp_path / "nope")]) == 2
    assert "projects dir not found" in capsys.readouterr().err
    assert "ERROR projects dir not found" in _sync_log.read_text(encoding="utf-8")


def test_scan_logs_to_file_without_console_streams(tmp_path, monkeypatch, _sync_log):
    """Under pythonw sys.stdout/sys.stderr are None: nothing may crash, the file still gets it."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")
    monkeypatch.setattr("sys.stdout", None)
    monkeypatch.setattr("sys.stderr", None)
    assert main(["scan", "--projects-dir", str(tmp_path / "nope")]) == 2
    assert "projects dir not found" in _sync_log.read_text(encoding="utf-8")


def test_scan_logs_unexpected_errors(tmp_path, monkeypatch, _sync_log, capsys):
    def boom(*a, **k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(cli, "_scan_with_retries", boom)
    assert main(["scan"]) == 1
    text = _sync_log.read_text(encoding="utf-8")
    assert "unexpected error" in text and "RuntimeError: kaboom" in text


def test_sync_log_rotates(monkeypatch, _sync_log):
    monkeypatch.setattr(cli, "SYNC_LOG_BYTES", 200)
    cli._open_sync_log(_sync_log)
    try:
        for i in range(20):
            cli.log.info("line %d %s", i, "x" * 40)
    finally:
        cli._close_sync_log()
    assert _sync_log.exists() and _sync_log.with_name(_sync_log.name + ".1").exists()
    assert not _sync_log.with_name(_sync_log.name + ".2").exists()  # 1 backup only


def test_migrate_sqlite_flags_parse():
    args = build_parser().parse_args(
        ["migrate-sqlite", "--sqlite", "x.db", "--machine", "pc", "--force", "--check-only",
         "--chunk", "5"])
    assert (args.sqlite, args.machine, args.force, args.check_only, args.chunk) == (
        "x.db", "pc", True, True, 5)
    defaults = build_parser().parse_args(["migrate-sqlite"])
    assert defaults.sqlite.endswith("token-dashboard.db") and defaults.machine is None
    assert not defaults.force and not defaults.check_only


# --- against the test schema ----------------------------------------------------

@pytest.fixture
def cli_env(db, pg_url, pg_schema, tmp_path, monkeypatch):
    """Point the CLI at the test schema, a temp projects dir and an empty skill root."""
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("DB_SCHEMA", pg_schema)
    monkeypatch.setenv("CLAUDE_LENS_MACHINE", "cli-test-pc")
    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("y" * 40)
    from claude_lens.collector import skills_catalog
    monkeypatch.setattr(skills_catalog, "_DEFAULT_ROOTS", [tmp_path / "skills"])
    root = tmp_path / "projects"
    (root / "C--work-sample").mkdir(parents=True)
    shutil.copy(FIXTURE, root / "C--work-sample" / "s1.jsonl")
    return root


def test_scan_command_records_a_sync_run(db, cli_env, capsys, _sync_log):
    assert main(["scan", "--projects-dir", str(cli_env)]) == 0
    out = capsys.readouterr().out
    assert "scanned 1 files: 3 messages, 2 tool calls, 0 titles" in out
    assert "INFO scanned 1 files: 3 messages" in _sync_log.read_text(encoding="utf-8")
    run = q(db, "SELECT machine, status, files, messages, tools, titles, error, finished_at IS NOT NULL"
                " FROM sync_runs")
    assert run == [("cli-test-pc", "ok", 1, 3, 2, 0, None, True)]
    # The catalog also registers "<ancestor>:demo" slugs for the temp path's folders.
    slugs = q(db, "SELECT machine, slug FROM skill_catalog")
    assert ("cli-test-pc", "demo") in slugs
    assert f"{len(slugs)} skills in catalog" in out

    assert main(["scan", "--projects-dir", str(cli_env)]) == 0
    assert "scanned 0 files" in capsys.readouterr().out
    assert q1(db, "SELECT count(*) FROM sync_runs WHERE status = 'ok'") == 2


def test_scan_records_errors_on_the_run_row(db, cli_env, capsys, monkeypatch):
    def boom(*a, **k):
        raise ValueError("disk on fire")
    monkeypatch.setattr(cli, "scan", boom)
    assert main(["scan", "--projects-dir", str(cli_env)]) == 1
    assert "disk on fire" in capsys.readouterr().err
    assert q(db, "SELECT status, error FROM sync_runs") == [("error", "ValueError: disk on fire")]


def test_scan_retries_operational_errors(db, cli_env, capsys, monkeypatch):
    sleeps = []
    monkeypatch.setattr(cli, "_sleep", sleeps.append)
    real_scan = cli.scan
    calls = {"n": 0}

    def flaky_scan(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise psycopg.OperationalError("server closed the connection unexpectedly")
        return real_scan(*a, **k)

    monkeypatch.setattr(cli, "scan", flaky_scan)
    assert main(["scan", "--projects-dir", str(cli_env)]) == 0
    assert sleeps == [cli.RETRY_DELAY, cli.RETRY_DELAY]
    assert "retry 2/3" in capsys.readouterr().err
    runs = q(db, "SELECT status, left(error, 16) FROM sync_runs ORDER BY id")
    assert runs == [("error", "connection lost:"), ("error", "connection lost:"), ("ok", None)]


def test_scan_gives_up_after_three_retries(db, cli_env, capsys, monkeypatch):
    sleeps = []
    monkeypatch.setattr(cli, "_sleep", sleeps.append)

    def dead_connect(settings):
        raise psycopg.OperationalError("connection timeout expired")

    monkeypatch.setattr(cli, "connect", dead_connect)
    assert main(["scan", "--projects-dir", str(cli_env)]) == 1
    assert len(sleeps) == cli.RETRIES
    assert "scan failed after 4 attempts" in capsys.readouterr().err


def test_status_prints_runs_and_counts(db, cli_env, capsys):
    main(["scan", "--projects-dir", str(cli_env)])
    capsys.readouterr()
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "migrations applied: 001" in out
    assert " ok " in out and "cli-test-pc" in out
    assert "messages" in out and "sessions" in out


def test_set_password_creates_then_updates_and_revokes(db, cli_env, monkeypatch, capsys):
    from claude_lens.core.passwords import verify_password

    _answers(monkeypatch, "first-pass-1", "first-pass-1")
    assert main(["set-password", "admin"]) == 0
    assert "created user 'admin'" in capsys.readouterr().out
    uid, h1 = q(db, "SELECT id, password_hash FROM users WHERE username = 'admin'")[0]
    assert verify_password("first-pass-1", h1)

    db.execute("INSERT INTO auth_sessions (token_hash, user_id, expires_at)"
               " VALUES ('t1', %s, now() + interval '1 day'), ('t2', %s, now() + interval '1 day')",
               (uid, uid))
    db.commit()
    _answers(monkeypatch, "second-pass-2", "second-pass-2")
    assert main(["set-password", "admin"]) == 0
    assert "2 session(s) revoked" in capsys.readouterr().out
    h2 = q1(db, "SELECT password_hash FROM users WHERE id = %s", (uid,))
    assert verify_password("second-pass-2", h2) and not verify_password("first-pass-1", h2)
    assert q1(db, "SELECT count(*) FROM auth_sessions") == 0


def test_status_on_uninitialised_schema(pg_url, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    monkeypatch.setenv("DB_SCHEMA", "claude_lens_test_never_created")
    assert main(["status"]) == 0
    assert "not initialised" in capsys.readouterr().out
