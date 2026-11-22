import socket
from pathlib import Path

import pytest

from claude_lens.config import Settings, find_repo_root, load_env_files, parse_env_text


def test_parse_env_text():
    text = "\n".join([
        "# comment",
        "",
        "A=1",
        "export B = two ",
        'C="quoted # not a comment"',
        "D='single'",
        "E=value # inline comment",
        "F=",
        "not a pair",
        "G=a=b",
    ])
    assert parse_env_text(text) == {
        "A": "1", "B": "two", "C": "quoted # not a comment", "D": "single",
        "E": "value", "F": "", "G": "a=b",
    }


def test_load_env_files_does_not_override_and_local_wins(tmp_path):
    (tmp_path / ".env.local").write_text("X=local\nY=local\n", encoding="utf-8")
    (tmp_path / ".env").write_text("Y=dotenv\nZ=dotenv\n", encoding="utf-8")
    env = {"X": "real"}
    loaded = load_env_files(tmp_path, env)
    assert [p.name for p in loaded] == [".env.local", ".env"]
    assert env == {"X": "real", "Y": "local", "Z": "dotenv"}


def test_load_env_files_without_files(tmp_path):
    env: dict = {}
    assert load_env_files(tmp_path, env) == []
    assert env == {}


def test_find_repo_root(tmp_path):
    (tmp_path / ".env.example").write_text("", encoding="utf-8")
    nested = tmp_path / "backend" / "claude_lens"
    nested.mkdir(parents=True)
    assert find_repo_root([nested]) == tmp_path


def test_find_repo_root_from_package_finds_this_repo():
    root = find_repo_root([Path(__file__).resolve().parent])
    assert root is not None
    assert (root / "backend" / "pyproject.toml").is_file()


def test_defaults():
    s = Settings.from_env({})
    assert s.database_url is None
    assert s.db_schema == "claude_dashboard"
    assert s.cookie_secure is True
    assert s.backend_url == "http://localhost:8000"
    assert s.claude_projects_dir == Path.home() / ".claude" / "projects"
    assert s.machine == socket.gethostname()


def test_empty_values_fall_back_to_defaults():
    s = Settings.from_env({"DB_SCHEMA": "", "CLAUDE_PROJECTS_DIR": " ", "CLAUDE_LENS_MACHINE": ""})
    assert s.db_schema == "claude_dashboard"
    assert s.claude_projects_dir == Path.home() / ".claude" / "projects"
    assert s.machine == socket.gethostname()


def test_values_from_env(tmp_path):
    s = Settings.from_env({
        "DATABASE_URL": "postgresql://u:p@h/db",
        "DB_SCHEMA": "claude_lens_test_abc123",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": "pw",
        "COOKIE_SECURE": "false",
        "BACKEND_URL": "http://backend:8000",
        "CLAUDE_PROJECTS_DIR": str(tmp_path),
        "CLAUDE_LENS_MACHINE": "box",
    })
    assert s.database_url == "postgresql://u:p@h/db"
    assert s.db_schema == "claude_lens_test_abc123"
    assert s.admin_username == "admin"
    assert s.cookie_secure is False
    assert s.backend_url == "http://backend:8000"
    assert s.claude_projects_dir == tmp_path
    assert s.machine == "box"


def test_repr_hides_secrets():
    s = Settings.from_env({"DATABASE_URL": "postgresql://u:SECRET@h/db", "ADMIN_PASSWORD": "SECRET"})
    assert "SECRET" not in repr(s)


@pytest.mark.parametrize("schema", ["bad-name", "a;drop", "1abc", 'x"y'])
def test_invalid_schema_rejected(schema):
    with pytest.raises(ValueError):
        Settings.from_env({"DB_SCHEMA": schema})


def test_invalid_bool_rejected():
    with pytest.raises(ValueError):
        Settings.from_env({"COOKIE_SECURE": "maybe"})
