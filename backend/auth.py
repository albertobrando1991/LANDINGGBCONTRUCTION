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


def set_auth_cookies(response, access_token: str, refresh_token: str):
    response.set_cookie(key="access_token", value=access_token, httponly=True,
                        secure=False, samesite="lax", max_age=43200, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True,
                        secure=False, samesite="lax", max_age=604800, path="/")


def clear_auth_cookies(response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


async def get_current_user(request: Request, db) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Non autenticato")
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
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token non valido")


async def seed_users(db):
    """Crea admin + utenti staff/operations demo (idempotente)."""
    defaults = [
        (os.environ.get("ADMIN_EMAIL", "admin@gbconstruction.it"),
         os.environ.get("ADMIN_PASSWORD", "GBadmin2026!"), "Giuseppe Brancale", "admin",
         "https://customer-assets.emergentagent.com/job_cantiere-smart-1/artifacts/ycum27ay_RITRATTO%20GIUSEPPE.png"),
        ("staff@gbconstruction.it", "GBstaff2026!", "Vincenzo Brancale", "staff",
         "https://customer-assets.emergentagent.com/job_cantiere-smart-1/artifacts/f2u1glj0_RITRATTO%20VINCENZO.png"),
        ("operations@gbconstruction.it", "GBops2026!", "Giovanni Brancale", "operations",
         "https://customer-assets.emergentagent.com/job_cantiere-smart-1/artifacts/jmpctbmn_RITRATTO%20PADRE.png"),
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
        elif role == "admin" and not verify_password(password, existing["password_hash"]):
            await db.users.update_one({"email": email},
                                      {"$set": {"password_hash": hash_password(password)}})
