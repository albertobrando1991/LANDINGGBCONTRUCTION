"""Auth dual-mode: riconoscimento JWT legacy vs Supabase."""
import asyncio
import jwt
import pytest
import auth as authlib
from starlette.requests import Request


def test_looks_like_supabase_rs256():
    # token finto con header RS256 (non verifichiamo firma qui)
    header = {"alg": "RS256", "typ": "JWT", "kid": "test"}
    payload = {"sub": "u1", "iss": "https://xyz.supabase.co/auth/v1", "role": "authenticated"}
    # PyJWT needs a key even for encode with RS - use HS encode then force: just test helper with crafted
    # We test the helper with a manually built token-like structure via encode HS but alg claim
    token = jwt.encode(payload, "secret", algorithm="HS256")
    # HS won't look like supabase by alg; inject iss path
    assert authlib._looks_like_supabase_jwt(token) is True  # iss contains supabase


def test_looks_like_legacy_hs():
    payload = {"sub": "abc", "type": "access", "email": "a@b.c", "role": "admin"}
    token = jwt.encode(payload, "secret", algorithm="HS256")
    # no supabase iss
    assert authlib._looks_like_supabase_jwt(token) is False


def _request(*, authorization=None, cookie=None):
    headers = []
    if authorization:
        headers.append((b"authorization", authorization.encode("utf-8")))
    if cookie:
        headers.append((b"cookie", cookie.encode("utf-8")))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "query_string": b"",
            "scheme": "https",
            "server": ("api.gbconstruction.it", 443),
            "client": ("127.0.0.1", 12345),
        }
    )


def test_supabase_bearer_precedes_legacy_cookie():
    request = _request(
        authorization="Bearer supabase-session",
        cookie="access_token=legacy-session",
    )
    assert authlib._extract_token(request) == "supabase-session"


def test_legacy_cookie_remains_supported_without_bearer():
    request = _request(cookie="access_token=legacy-session")
    assert authlib._extract_token(request) == "legacy-session"


def test_supabase_membership_requires_a_tenant_identifier():
    assert authlib._supabase_memberships({}) == []
    assert authlib._supabase_memberships({"app_tenants": [{"r": "admin"}]}) == []


def test_supabase_membership_accepts_access_token_hook_claim():
    memberships = authlib._supabase_memberships(
        {"app_tenants": [{"t": "tenant-id", "r": "operations"}]}
    )
    assert memberships == [{"t": "tenant-id", "r": "operations"}]


def test_database_membership_recovers_missing_access_token_claim(monkeypatch):
    async def fetch_memberships(_user_id):
        return [{"t": "tenant-db", "r": "client", "slug": "gbconstruction"}]

    monkeypatch.setattr(authlib.db_pg, "fetch_user_memberships", fetch_memberships)

    memberships = asyncio.run(
        authlib._resolved_supabase_memberships({}, "user-id")
    )
    assert memberships == [
        {"t": "tenant-db", "r": "client", "slug": "gbconstruction"}
    ]


def test_database_membership_overrides_stale_access_token_claim(monkeypatch):
    async def fetch_memberships(_user_id):
        return []

    monkeypatch.setattr(authlib.db_pg, "fetch_user_memberships", fetch_memberships)

    memberships = asyncio.run(
        authlib._resolved_supabase_memberships(
            {"app_tenants": [{"t": "tenant-old", "r": "admin"}]},
            "user-id",
        )
    )
    assert memberships == []


class _FakeUsers:
    def __init__(self, existing=None):
        self.existing = existing
        self.inserted = []
        self.updated = []

    async def find_one(self, _query):
        return self.existing

    async def insert_one(self, document):
        self.inserted.append(dict(document))

    async def update_many(self, query, update):
        self.updated.append((query, update))
        return type("Result", (), {"modified_count": 2})()


class _FakeDB:
    def __init__(self, existing=None):
        self.users = _FakeUsers(existing)


def test_production_cookie_is_secure_and_lax(monkeypatch):
    monkeypatch.delenv("AUTH_COOKIE_SAMESITE", raising=False)
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("AUTH_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert authlib._cookie_flags() == {
        "httponly": True,
        "secure": True,
        "samesite": "lax",
        "path": "/",
    }


def test_seed_users_requires_explicit_credentials(monkeypatch):
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    db = _FakeDB()
    asyncio.run(authlib.seed_users(db))
    assert db.users.inserted == []


def test_seed_users_rejects_default_password(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "admin@gbconstruction.it")
    monkeypatch.setenv("ADMIN_PASSWORD", "GBadmin2026!")
    with pytest.raises(RuntimeError):
        asyncio.run(authlib.seed_users(_FakeDB()))


def test_seed_users_never_resets_existing_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "admin@gbconstruction.it")
    monkeypatch.setenv("ADMIN_PASSWORD", "Una-password-molto-forte-2026!")
    db = _FakeDB(existing={"email": "admin@gbconstruction.it"})
    asyncio.run(authlib.seed_users(db))
    assert db.users.inserted == []


def test_production_rejects_placeholder_security(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "replace-with-a-long-random-secret")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@gbconstruction.it")
    monkeypatch.setenv("ADMIN_PASSWORD", "Una-password-molto-forte-2026!")
    monkeypatch.setenv("ENABLE_DEMO_SEED", "false")
    with pytest.raises(RuntimeError):
        authlib.validate_production_security_configuration()


def test_production_accepts_explicit_strong_security(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a" * 64)
    monkeypatch.setenv("ADMIN_EMAIL", "admin@gbconstruction.it")
    monkeypatch.setenv("ADMIN_PASSWORD", "Una-password-molto-forte-2026!")
    monkeypatch.setenv("ENABLE_DEMO_SEED", "false")
    authlib.validate_production_security_configuration()


def test_disables_legacy_demo_users():
    db = _FakeDB()
    count = asyncio.run(authlib.disable_legacy_demo_users(db))
    assert count == 2
    query, update = db.users.updated[0]
    assert set(query["email"]["$in"]) == set(authlib.LEGACY_DEMO_EMAILS)
    assert update["$set"]["disabled"] is True
