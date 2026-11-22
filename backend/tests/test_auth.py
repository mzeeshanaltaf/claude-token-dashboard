"""Login, sessions, lockout, password change, CSRF and the admin bootstrap."""
import pytest

from claude_lens.api.auth import bootstrap_admin
from claude_lens.api.deps import COOKIE_NAME
from claude_lens.config import Settings
from claude_lens.core.passwords import token_hash, verify_password
from helpers import ADMIN_PASS, ADMIN_USER, login, q, q1

PROTECTED = ["/api/overview", "/api/daily", "/api/by-model", "/api/tools", "/api/skills",
             "/api/projects", "/api/projects/x/sessions", "/api/sessions", "/api/sessions/x",
             "/api/prompts", "/api/tips", "/api/plan", "/api/settings", "/api/sync-status",
             "/api/auth/me"]


def test_401_without_a_cookie(anon):
    for path in PROTECTED:
        assert anon.get(path).status_code == 401, path
    assert anon.post("/api/plan", json={"plan": "pro"}).status_code == 401
    assert anon.post("/api/tips/dismiss", json={"key": "x"}).status_code == 401
    assert anon.post("/api/settings", json={}).status_code == 401


def test_401_with_a_bogus_cookie(anon):
    anon.cookies.set(COOKIE_NAME, "not-a-real-token")
    assert anon.get("/api/overview").status_code == 401


def test_login_then_access_works(anon, db):
    r = login(anon)
    assert r.status_code == 200
    assert r.json()["username"] == ADMIN_USER
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    low = cookie.lower()
    assert "httponly" in low and "samesite=lax" in low and "path=/" in low
    assert "max-age=604800" in low
    assert "secure" not in low  # COOKIE_SECURE=false in the test settings
    # only the sha256 of the token is stored
    token = anon.cookies.get(COOKIE_NAME)
    assert len(token) >= 43
    assert q(db, "SELECT token_hash FROM auth_sessions") == [(token_hash(token),)]
    assert q1(db, "SELECT expires_at - now() > interval '6 days 23 hours' FROM auth_sessions")
    assert anon.get("/api/overview").status_code == 200
    assert anon.get("/api/auth/me").json()["username"] == ADMIN_USER


def test_wrong_password_401_then_429_on_the_6th(anon):
    for _ in range(5):
        assert login(anon, password="wrong-password").status_code == 401
    r = login(anon)  # even the right password is refused while locked out
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
    assert login(anon, username="someone-else", password="x").status_code == 401  # per user


def test_unknown_user_is_401(anon):
    assert login(anon, username="nobody").status_code == 401


def test_success_resets_the_failure_count(anon):
    for _ in range(4):
        assert login(anon, password="wrong-password").status_code == 401
    assert login(anon).status_code == 200
    for _ in range(4):
        assert login(anon, password="wrong-password").status_code == 401
    assert login(anon).status_code == 200


def test_logout_revokes_the_session(client, db):
    token = client.cookies.get(COOKIE_NAME)
    r = client.post("/api/auth/logout", json={})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert f'{COOKIE_NAME}=""' in r.headers["set-cookie"] or "max-age=0" in r.headers["set-cookie"].lower()
    assert q1(db, "SELECT count(*) FROM auth_sessions") == 0
    client.cookies.set(COOKIE_NAME, token)  # replaying the old cookie no longer works
    assert client.get("/api/overview").status_code == 401


def test_logout_without_a_session_is_fine(anon):
    assert anon.post("/api/auth/logout", json={}).status_code == 200


def test_password_change_revokes_other_sessions(anon, db):
    assert login(anon).status_code == 200
    other = anon.cookies.get(COOKIE_NAME)
    anon.cookies.clear()
    assert login(anon).status_code == 200
    mine = anon.cookies.get(COOKIE_NAME)
    assert q1(db, "SELECT count(*) FROM auth_sessions") == 2

    bad = anon.post("/api/auth/password", json={"current": "nope", "new": "brand-new-pass"})
    assert bad.status_code == 400
    short = anon.post("/api/auth/password", json={"current": ADMIN_PASS, "new": "short"})
    assert short.status_code == 422

    r = anon.post("/api/auth/password", json={"current": ADMIN_PASS, "new": "brand-new-pass"})
    assert r.status_code == 200 and r.json() == {"ok": True, "revoked_sessions": 1}
    assert anon.get("/api/overview").status_code == 200  # this session survives
    anon.cookies.set(COOKIE_NAME, other)
    assert anon.get("/api/overview").status_code == 401  # the other one is gone
    anon.cookies.set(COOKIE_NAME, mine)
    assert verify_password("brand-new-pass", q1(db, "SELECT password_hash FROM users"))
    anon.cookies.clear()
    assert login(anon).status_code == 401
    assert login(anon, password="brand-new-pass").status_code == 200


def test_session_expiry_slides_forward(client, db):
    db.execute("UPDATE auth_sessions SET expires_at = now() + interval '3 days'")
    db.commit()
    r = client.get("/api/overview")
    assert r.status_code == 200
    assert COOKIE_NAME in r.headers.get("set-cookie", "")
    assert q1(db, "SELECT expires_at - now() > interval '6 days' FROM auth_sessions")
    r = client.get("/api/overview")  # plenty left now: no refresh
    assert "set-cookie" not in r.headers


def test_expired_session_is_401(client, db):
    db.execute("UPDATE auth_sessions SET expires_at = now() - interval '1 second'")
    db.commit()
    assert client.get("/api/overview").status_code == 401


# --- CSRF ---------------------------------------------------------------------------

def test_csrf_requires_json_content_type(client):
    r = client.post("/api/plan", content="plan=pro",
                    headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 415
    r = client.post("/api/auth/login", content=b"{}", headers={"Content-Type": "text/plain"})
    assert r.status_code == 415


def test_csrf_checks_origin(client):
    evil = client.post("/api/plan", json={"plan": "pro"}, headers={"Origin": "https://evil.example"})
    assert evil.status_code == 403
    null = client.post("/api/plan", json={"plan": "pro"}, headers={"Origin": "null"})
    assert null.status_code == 403
    same = client.post("/api/plan", json={"plan": "pro"}, headers={"Origin": "http://testserver"})
    assert same.status_code == 200
    proxied = client.post("/api/plan", json={"plan": "max"}, headers={
        "Origin": "https://lens.example.com", "X-Forwarded-Host": "lens.example.com"})
    assert proxied.status_code == 200
    # GETs are never blocked
    assert client.get("/api/plan", headers={"Origin": "https://evil.example"}).status_code == 200


# --- bootstrap ------------------------------------------------------------------------

def _settings(pg_schema, **env):
    return Settings.from_env({"DB_SCHEMA": pg_schema, **env})


def test_bootstrap_creates_admin_once(db, pg_schema):
    s = _settings(pg_schema, ADMIN_USERNAME="boss", ADMIN_PASSWORD="first-password")
    assert bootstrap_admin(db, s) is True
    assert q(db, "SELECT username FROM users") == [("boss",)]
    s2 = _settings(pg_schema, ADMIN_USERNAME="boss", ADMIN_PASSWORD="other-password")
    assert bootstrap_admin(db, s2) is False  # existing users are never touched
    assert verify_password("first-password", q1(db, "SELECT password_hash FROM users"))


def test_bootstrap_refuses_without_env_and_users(db, pg_schema):
    with pytest.raises(RuntimeError, match="refusing to start"):
        bootstrap_admin(db, _settings(pg_schema))
    with pytest.raises(RuntimeError):
        bootstrap_admin(db, _settings(pg_schema, ADMIN_USERNAME="boss"))
    assert q1(db, "SELECT count(*) FROM users") == 0


def test_app_refuses_to_start_without_admin(db, pg_url, pg_schema):
    from fastapi.testclient import TestClient
    from claude_lens.api.main import create_app
    app = create_app(Settings.from_env({"DATABASE_URL": pg_url, "DB_SCHEMA": pg_schema}),
                     pool_max=1)
    with pytest.raises(RuntimeError, match="ADMIN_USERNAME"):
        with TestClient(app):
            pass
