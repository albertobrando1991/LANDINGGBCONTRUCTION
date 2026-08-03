import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_architect_service as svc  # noqa: E402


class _FakeUploadLog:
    def __init__(self):
        self.docs = []
        self.indexes = []

    async def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))
        return None

    async def count_documents(self, query):
        ip = query.get("ip")
        created_at = query.get("created_at") or {}
        threshold = created_at.get("$gte", datetime.min.replace(tzinfo=timezone.utc))
        return sum(
            1
            for doc in self.docs
            if doc.get("ip") == ip and doc.get("created_at") >= threshold
        )

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return None


class _FakeDB:
    def __init__(self):
        self.ai_architect_upload_log = _FakeUploadLog()


def test_rate_limit_allows_under_threshold(monkeypatch):
    monkeypatch.setattr(svc, "AI_ARCHITECT_UPLOAD_MAX_PER_IP", 2)
    db = _FakeDB()

    asyncio.run(svc.enforce_upload_rate_limit(db, "203.0.113.10"))
    asyncio.run(svc.enforce_upload_rate_limit(db, "203.0.113.10"))

    assert len(db.ai_architect_upload_log.docs) == 2


def test_rate_limit_blocks_over_threshold(monkeypatch):
    monkeypatch.setattr(svc, "AI_ARCHITECT_UPLOAD_MAX_PER_IP", 2)
    db = _FakeDB()

    asyncio.run(svc.enforce_upload_rate_limit(db, "203.0.113.10"))
    asyncio.run(svc.enforce_upload_rate_limit(db, "203.0.113.10"))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(svc.enforce_upload_rate_limit(db, "203.0.113.10"))

    assert exc.value.status_code == 429
    assert "numero massimo di analisi gratuite" in exc.value.detail
    assert len(db.ai_architect_upload_log.docs) == 2


def test_rate_limit_isolated_per_ip(monkeypatch):
    monkeypatch.setattr(svc, "AI_ARCHITECT_UPLOAD_MAX_PER_IP", 2)
    db = _FakeDB()

    asyncio.run(svc.enforce_upload_rate_limit(db, "203.0.113.10"))
    asyncio.run(svc.enforce_upload_rate_limit(db, "203.0.113.10"))
    asyncio.run(svc.enforce_upload_rate_limit(db, "203.0.113.11"))

    assert len(db.ai_architect_upload_log.docs) == 3


def test_rate_limit_skips_when_ip_unknown(monkeypatch):
    monkeypatch.setattr(svc, "AI_ARCHITECT_UPLOAD_MAX_PER_IP", 2)
    db = _FakeDB()

    asyncio.run(svc.enforce_upload_rate_limit(db, None))
    asyncio.run(svc.enforce_upload_rate_limit(db, ""))

    assert db.ai_architect_upload_log.docs == []


def test_rate_limit_configures_ttl_index(monkeypatch):
    monkeypatch.setattr(svc, "AI_ARCHITECT_UPLOAD_WINDOW_HOURS", 24)
    db = _FakeDB()

    asyncio.run(svc.ensure_upload_rate_limit_indexes(db))

    assert ("created_at", {"expireAfterSeconds": 24 * 3600}) in db.ai_architect_upload_log.indexes
