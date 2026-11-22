"""Password hashing (argon2 via pwdlib) and session-token helpers."""
from __future__ import annotations

import hashlib
import secrets

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

MIN_PASSWORD_LENGTH = 8
TOKEN_BYTES = 32

_hasher = PasswordHash((Argon2Hasher(),))
# Verified against when the username doesn't exist, so a miss costs as much as a hit.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    try:
        return _hasher.verify(password, password_hash)
    except Exception:  # noqa: BLE001 - a malformed stored hash is just a failed login
        return False


def check_new_password(password: str) -> None:
    """Raise ValueError when `password` is too weak to store."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"password must be at least {MIN_PASSWORD_LENGTH} characters")


def new_token() -> str:
    """32 random bytes, URL-safe base64 (the cookie value)."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_hash(token: str) -> str:
    """What `auth_sessions.token_hash` stores: hex sha256 of the cookie value."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
