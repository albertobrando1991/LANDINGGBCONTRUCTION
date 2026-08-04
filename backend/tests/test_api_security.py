import asyncio

import pytest
from fastapi import HTTPException

import api_security


class _FakeRateLimits:
    def __init__(self):
        self.docs = {}
        self.indexes = []

    async def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))

    async def find_one_and_update(self, query, update, **_kwargs):
        key = query["_id"]
        doc = self.docs.setdefault(key, {"_id": key, "count": 0})
        doc["count"] += update["$inc"]["count"]
        for field, value in update["$setOnInsert"].items():
            doc.setdefault(field, value)
        return dict(doc)


class _FakeDB:
    def __init__(self):
        self.api_rate_limits = _FakeRateLimits()


def test_rate_limit_is_shared_and_returns_retry_after():
    db = _FakeDB()
    kwargs = {
        "scope": "login",
        "identity": "203.0.113.5",
        "limit": 2,
        "window_seconds": 900,
        "detail": "Troppi tentativi",
    }

    asyncio.run(api_security.enforce_rate_limit(db, **kwargs))
    asyncio.run(api_security.enforce_rate_limit(db, **kwargs))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(api_security.enforce_rate_limit(db, **kwargs))

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"].isdigit()
    assert "203.0.113.5" not in next(iter(db.api_rate_limits.docs))


def test_rate_limit_skips_missing_identity():
    db = _FakeDB()
    asyncio.run(
        api_security.enforce_rate_limit(
            db,
            scope="lead",
            identity=None,
            limit=1,
            window_seconds=60,
            detail="Limite",
        )
    )
    assert db.api_rate_limits.docs == {}


def test_rate_limit_ttl_index():
    db = _FakeDB()
    asyncio.run(api_security.ensure_rate_limit_indexes(db))
    assert ("expires_at", {"expireAfterSeconds": 0}) in db.api_rate_limits.indexes
