"""Controlli di sicurezza condivisi dagli endpoint HTTP pubblici."""

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from pymongo import ReturnDocument


def _rate_limit_key(scope: str, identity: str, bucket: int) -> str:
    digest = hashlib.sha256(identity.strip().lower().encode("utf-8")).hexdigest()
    return f"{scope}:{digest}:{bucket}"


async def ensure_rate_limit_indexes(db) -> None:
    """La TTL index rimuove automaticamente le finestre scadute."""

    await db.api_rate_limits.create_index("expires_at", expireAfterSeconds=0)


async def enforce_rate_limit(
    db,
    *,
    scope: str,
    identity: str | None,
    limit: int,
    window_seconds: int,
    detail: str,
) -> None:
    """Rate limit atomico a finestra fissa, condiviso tra processi via Mongo."""

    normalized_identity = (identity or "").strip()
    if not normalized_identity or limit <= 0:
        return

    now = datetime.now(timezone.utc)
    bucket = int(now.timestamp()) // window_seconds
    expires_at = now + timedelta(seconds=window_seconds * 2)
    document = await db.api_rate_limits.find_one_and_update(
        {"_id": _rate_limit_key(scope, normalized_identity, bucket)},
        {
            "$inc": {"count": 1},
            "$setOnInsert": {
                "scope": scope,
                "created_at": now,
                "expires_at": expires_at,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    if int((document or {}).get("count", 0)) > limit:
        retry_after = window_seconds - (int(now.timestamp()) % window_seconds)
        raise HTTPException(
            status_code=429,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
        )
