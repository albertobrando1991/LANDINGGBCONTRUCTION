"""GB Construction - Autenticazione JWT email+password con ruoli."""
import os
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request
from bson import ObjectId

JWT_ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id, "email": email, "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _cookie_flags() -> dict:
    """Flag cookie per auth.

    Dashboard su Vercel (gb-construction.vercel.app) chiama API su
    api.gbconstruction.it → cross-site: serve SameSite=None + Secure.
    In locale (HTTP) resta Lax + non-secure.
    Override: AUTH_COOKIE_SAMESITE=none|lax e COOKIE_SECURE=true|false.
    """
    explicit = (os.environ.get("AUTH_COOKIE_SAMESITE") or "").strip().lower()
    secure_env = (os.environ.get("COOKIE_SECURE") or os.environ.get("AUTH_COOKIE_SECURE") or "").strip().lower()
    railway_prod = (os.environ.get("RAILWAY_ENVIRONMENT") or "").strip().lower() == "production"

    if explicit in ("none", "lax", "strict"):
        samesite = explicit
    elif secure_env in ("1", "true", "yes") or railway_prod:
        samesite = "none"
    else:
        samesite = "lax"

    if secure_env in ("1", "true", "yes"):
        secure = True
    elif secure_env in ("0", "false", "no"):
        secure = False
    else:
        # SameSite=None richiede Secure nei browser moderni
        secure = samesite == "none" or railway_prod

    return {"httponly": True, "secure": secure, "samesite": samesite, "path": "/"}


def set_auth_cookies(response, access_token: str, refresh_token: str):
    flags = _cookie_flags()
    response.set_cookie(key="access_token", value=access_token, max_age=43200, **flags)
    response.set_cookie(key="refresh_token", value=refresh_token, max_age=604800, **flags)


def clear_auth_cookies(response):
    flags = _cookie_flags()
    # delete_cookie deve allineare path/secure/samesite per invalidare
    response.delete_cookie(
        "access_token",
        path=flags["path"],
        secure=flags["secure"],
        samesite=flags["samesite"],
    )
    response.delete_cookie(
        "refresh_token",
        path=flags["path"],
        secure=flags["secure"],
        samesite=flags["samesite"],
    )


def _extract_token(request: Request) -> str | None:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return token


def _looks_like_supabase_jwt(token: str) -> bool:
    """Supabase JWT: tipicamente RS256 e iss che punta a *.supabase.co/auth/v1."""
    try:
        header = jwt.get_unverified_header(token)
        payload = jwt.decode(token, options={"verify_signature": False, "verify_aud": False, "verify_exp": False})
    except Exception:
        return False
    alg = (header.get("alg") or "").upper()
    iss = str(payload.get("iss") or "")
    if alg.startswith("RS") or alg.startswith("ES"):
        return True
    if "supabase" in iss or "/auth/v1" in iss:
        return True
    return False


_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0


async def _fetch_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    import time
    import urllib.request

    now = time.time()
    if _jwks_cache and (now - _jwks_fetched_at) < 3600:
        return _jwks_cache
    jwks_url = os.environ.get("SUPABASE_JWKS_URL")
    if not jwks_url:
        base = os.environ.get("SUPABASE_URL", "").rstrip("/")
        if base:
            jwks_url = f"{base}/auth/v1/.well-known/jwks.json"
    if not jwks_url:
        raise HTTPException(status_code=500, detail="SUPABASE_JWKS_URL non configurato")
    with urllib.request.urlopen(jwks_url, timeout=10) as resp:
        import json
        _jwks_cache = json.loads(resp.read().decode("utf-8"))
        _jwks_fetched_at = now
        return _jwks_cache


async def _verify_supabase(token: str) -> dict:
    """Verifica JWT Supabase via JWKS e restituisce utente normalizzato."""
    try:
        from jwt import PyJWKClient
    except Exception:
        PyJWKClient = None

    jwks_url = os.environ.get("SUPABASE_JWKS_URL")
    if not jwks_url:
        base = os.environ.get("SUPABASE_URL", "").rstrip("/")
        jwks_url = f"{base}/auth/v1/.well-known/jwks.json" if base else None
    if not jwks_url:
        raise HTTPException(status_code=500, detail="SUPABASE_JWKS_URL non configurato")

    try:
        if PyJWKClient is not None:
            client = PyJWKClient(jwks_url, cache_keys=True)
            key = client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                key.key,
                algorithms=["RS256", "ES256"],
                audience="authenticated",
                options={"verify_aud": False},
            )
        else:
            # fallback: decode without full JWKS if crypto extra missing (dev only)
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_aud": False},
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except Exception:
        raise HTTPException(status_code=401, detail="Token non valido")

    user_id = payload.get("sub")
    email = payload.get("email") or (payload.get("user_metadata") or {}).get("email")
    app_tenants = payload.get("app_tenants") or []
    role = "staff"
    if app_tenants and isinstance(app_tenants, list) and isinstance(app_tenants[0], dict):
        role = app_tenants[0].get("r") or app_tenants[0].get("role") or "staff"
    return {
        "id": user_id,
        "sub": user_id,
        "email": email,
        "role": role,
        "name": (payload.get("user_metadata") or {}).get("name") or email,
        "app_tenants": app_tenants,
        "auth_provider": "supabase",
        "access_token": token,
    }


async def _verify_legacy(token: str, db) -> dict:
    """Percorso JWT proprietario attuale — INVARIATO."""
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token non valido")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="Utente non trovato")
        user["id"] = str(user["_id"])
        user.pop("_id", None)
        user.pop("password_hash", None)
        user["auth_provider"] = "legacy"
        user["access_token"] = token
        from legacy_tenant import map_legacy_user

        return map_legacy_user(user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token non valido")


async def get_current_user(request: Request, db) -> dict:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Non autenticato")
    if _looks_like_supabase_jwt(token):
        user = await _verify_supabase(token)
        user["access_token"] = token
        return user
    return await _verify_legacy(token, db)


async def seed_users(db):
    """Crea admin + utenti staff/operations demo (idempotente)."""
    defaults = [
        (os.environ.get("ADMIN_EMAIL", "admin@gbconstruction.it"),
         os.environ.get("ADMIN_PASSWORD", "GBadmin2026!"), "Giuseppe Brancale", "admin",
         "/brand/staff-giuseppe.png"),
        ("staff@gbconstruction.it", "GBstaff2026!", "Vincenzo Brancale", "staff",
         "/brand/staff-vincenzo.png"),
        ("operations@gbconstruction.it", "GBops2026!", "Giovanni Brancale", "operations",
         "/brand/staff-giovanni.png"),
    ]
    for email, password, name, role, photo in defaults:
        email = email.lower()
        existing = await db.users.find_one({"email": email})
        if existing is None:
            await db.users.insert_one({
                "email": email, "password_hash": hash_password(password),
                "name": name, "role": role, "photo": photo,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        else:
            updates = {}
            if role == "admin" and not verify_password(password, existing["password_hash"]):
                updates["password_hash"] = hash_password(password)
            if (existing.get("photo") or "").startswith("https://"):
                updates["photo"] = photo
            if updates:
                await db.users.update_one({"email": email}, {"$set": updates})
