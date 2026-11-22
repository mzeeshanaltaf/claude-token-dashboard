"""Settings loaded from the environment, with a tiny `.env.local` / `.env` loader.

Precedence (highest first): real environment variables, then `.env.local`,
then `.env`, both at the repo root. The loader never overrides a variable that
is already set, so the real environment always wins.
"""
from __future__ import annotations

import os
import re
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Optional

ENV_FILES = (".env.local", ".env")
DEFAULT_SCHEMA = "claude_dashboard"
DEFAULT_BACKEND_URL = "http://localhost:8000"

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def parse_env_text(text: str) -> dict[str, str]:
    """Parse dotenv-style text: `KEY=VALUE` lines, `#` comments, optional `export `.

    Surrounding single/double quotes are stripped. For unquoted values, a ` #`
    starts an inline comment.
    """
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        else:
            hash_at = value.find(" #")
            if hash_at != -1:
                value = value[:hash_at].rstrip()
        out[key] = value
    return out


def find_repo_root(starts: Optional[Iterable[Path]] = None) -> Optional[Path]:
    """Return the first ancestor of the start dirs that looks like the repo root.

    The repo root is a directory holding `.git` or `.env.example`. By default the
    search starts at the current directory, then at this package's location.
    """
    if starts is None:
        starts = (Path.cwd(), Path(__file__).resolve().parent)
    for start in starts:
        for d in (start, *start.parents):
            if (d / ".git").exists() or (d / ".env.example").is_file():
                return d
    return None


def load_env_files(
    root: Optional[Path] = None,
    environ: Optional[MutableMapping[str, str]] = None,
) -> list[Path]:
    """Load `.env.local` then `.env` from the repo root into `environ`.

    Existing keys are never overridden. Returns the files that were read.
    """
    environ = os.environ if environ is None else environ
    root = root if root is not None else find_repo_root()
    if root is None:
        return []
    loaded = []
    for name in ENV_FILES:
        path = root / name
        if not path.is_file():
            continue
        for key, value in parse_env_text(path.read_text(encoding="utf-8")).items():
            environ.setdefault(key, value)
        loaded.append(path)
    return loaded


def _get(env: Mapping[str, str], key: str) -> Optional[str]:
    """Return the value, treating empty strings as unset."""
    value = env.get(key)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    value = _get(env, key)
    if value is None:
        return default
    v = value.lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    raise ValueError(f"{key} must be a boolean (true/false), got {value!r}")


def default_sync_log(env: Optional[Mapping[str, str]] = None) -> Path:
    """`CLAUDE_LENS_SYNC_LOG` if set, else ~/.claude/claude-lens-sync.log."""
    custom = _get(os.environ if env is None else env, "CLAUDE_LENS_SYNC_LOG")
    return Path(custom).expanduser() if custom else Path.home() / ".claude" / "claude-lens-sync.log"


@dataclass(frozen=True)
class Settings:
    # Secrets are excluded from repr so they never leak into logs or tracebacks.
    database_url: Optional[str] = field(default=None, repr=False)
    db_schema: str = DEFAULT_SCHEMA
    admin_username: Optional[str] = None
    admin_password: Optional[str] = field(default=None, repr=False)
    cookie_secure: bool = True
    # Read the client IP from X-Forwarded-For (only behind a trusted proxy).
    trust_proxy: bool = False
    backend_url: str = DEFAULT_BACKEND_URL
    claude_projects_dir: Path = field(default_factory=lambda: Path.home() / ".claude" / "projects")
    machine: str = field(default_factory=socket.gethostname)
    sync_log: Path = field(default_factory=default_sync_log)

    def __post_init__(self) -> None:
        if not _IDENT_RE.match(self.db_schema):
            raise ValueError(f"DB_SCHEMA must be a plain SQL identifier, got {self.db_schema!r}")

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Settings":
        """Build settings from a mapping (default: `os.environ`). Does not read files."""
        env = os.environ if env is None else env
        kwargs: dict = {
            "database_url":   _get(env, "DATABASE_URL"),
            "db_schema":      _get(env, "DB_SCHEMA") or DEFAULT_SCHEMA,
            "admin_username": _get(env, "ADMIN_USERNAME"),
            "admin_password": _get(env, "ADMIN_PASSWORD"),
            "cookie_secure":  _bool(env, "COOKIE_SECURE", True),
            "trust_proxy":    _bool(env, "TRUST_PROXY", False),
            "backend_url":    _get(env, "BACKEND_URL") or DEFAULT_BACKEND_URL,
        }
        projects = _get(env, "CLAUDE_PROJECTS_DIR")
        if projects:
            kwargs["claude_projects_dir"] = Path(projects).expanduser()
        machine = _get(env, "CLAUDE_LENS_MACHINE")
        if machine:
            kwargs["machine"] = machine
        kwargs["sync_log"] = default_sync_log(env)
        return cls(**kwargs)


def load_settings() -> Settings:
    """Load the repo-root env files into `os.environ`, then build `Settings`."""
    load_env_files()
    return Settings.from_env()
