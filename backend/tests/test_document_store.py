import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from document_id import ObjectId
from document_store import (
    DocumentCollection,
    ReturnDocument,
    _apply_update,
    _matches,
    _projection,
)


class _AsyncContext:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False


class _FakeConnection:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.fetchrow = AsyncMock(side_effect=self._fetchrow)
        self.execute = AsyncMock(return_value="OK")
        self.executemany = AsyncMock(return_value=None)

    async def _fetchrow(self, *_args):
        return self.rows.pop(0) if self.rows else None

    def transaction(self):
        return _AsyncContext()


class _FakeDatabase:
    def __init__(self, conn):
        self.conn = conn
        self.pool = self

    async def tenant_id(self):
        return "00000000-0000-4000-8000-000000000001"

    def acquire(self):
        return _AsyncContext(self.conn)


def test_object_id_legacy_compatibility_without_bson():
    value = ObjectId("64B64C8F2F9B2D7A1C000001")
    assert str(value) == "64b64c8f2f9b2d7a1c000001"
    assert ObjectId.is_valid(value)
    assert not ObjectId.is_valid("not-an-id")
    assert len(str(ObjectId())) == 24


def test_filters_cover_runtime_operator_set():
    document = {
        "status": "completed",
        "count": 3,
        "tags": ["Meta", "caldo"],
        "external_ids": {"meta_leadgen_id": "lead-1"},
        "email": "Antonio@Example.it",
    }
    assert _matches(document, {"count": {"$gte": 3, "$lt": 4}})
    assert _matches(document, {"status": {"$in": ["completed", "failed"]}})
    assert _matches(document, {"status": {"$nin": ["failed"]}})
    assert _matches(document, {"tags": "Meta"})
    assert _matches(document, {"external_ids.meta_leadgen_id": {"$exists": True}})
    assert _matches(document, {"email": {"$regex": "^antonio", "$options": "i"}})
    assert _matches(document, {"$or": [{"count": {"$gt": 8}}, {"status": "completed"}]})
    assert not _matches(document, {"status": {"$ne": "completed"}})


def test_updates_preserve_document_semantics_used_by_services():
    original = {"_id": ObjectId("64b64c8f2f9b2d7a1c000001"), "count": 1, "tags": ["a"]}
    updated = _apply_update(
        original,
        {
            "$inc": {"count": 2},
            "$set": {"profile.city": "Napoli"},
            "$addToSet": {"tags": {"$each": ["a", "b"]}},
            "$push": {"timeline": {"$each": [{"id": "e1"}], "$position": 0}},
            "$unset": {"obsolete": ""},
        },
    )
    assert updated["count"] == 3
    assert updated["profile"]["city"] == "Napoli"
    assert updated["tags"] == ["a", "b"]
    assert updated["timeline"] == [{"id": "e1"}]
    assert original == {
        "_id": ObjectId("64b64c8f2f9b2d7a1c000001"),
        "count": 1,
        "tags": ["a"],
    }


def test_set_on_insert_and_projection():
    inserted = _apply_update(
        {"email": "a@example.it"},
        {"$set": {"active": True}, "$setOnInsert": {"created_at": "now"}},
        inserting=True,
    )
    assert inserted == {
        "email": "a@example.it",
        "active": True,
        "created_at": "now",
    }
    assert _projection(inserted, {"email": 1, "_id": 0}) == {"email": "a@example.it"}


def test_find_one_by_id_uses_primary_key_lookup_without_collection_scan():
    raw_id = "64b64c8f2f9b2d7a1c000001"
    conn = _FakeConnection([{"id": raw_id, "data": {"status": "active"}}])
    collection = DocumentCollection(_FakeDatabase(conn), "cantieri")

    result = asyncio.run(collection.find_one({"_id": ObjectId(raw_id)}))

    assert str(result["_id"]) == raw_id
    sql, _tenant_id, name, requested_id = conn.fetchrow.await_args.args
    assert "and id = $3" in sql.lower()
    assert name == "cantieri"
    assert requested_id == raw_id


def test_update_one_by_id_locks_only_the_target_row():
    raw_id = "64b64c8f2f9b2d7a1c000001"
    conn = _FakeConnection([{"id": raw_id, "data": json.dumps({"status": "active"})}])
    collection = DocumentCollection(_FakeDatabase(conn), "cantieri")

    result = asyncio.run(
        collection.update_one(
            {"_id": ObjectId(raw_id)},
            {"$set": {"status": "completed"}},
        )
    )

    assert result.matched_count == 1
    assert result.modified_count == 1
    assert "for update" in conn.fetchrow.await_args.args[0].lower()
    assert all(
        "pg_advisory" not in call.args[0] for call in conn.execute.await_args_list
    )
    assert any(
        "update private.runtime_documents" in call.args[0]
        for call in conn.execute.await_args_list
    )


def test_atomic_upsert_by_id_uses_row_scoped_advisory_key():
    raw_id = "rate:user:window"
    conn = _FakeConnection([None])
    collection = DocumentCollection(_FakeDatabase(conn), "api_rate_limits")

    result = asyncio.run(
        collection.find_one_and_update(
            {"_id": raw_id},
            {"$inc": {"count": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    )

    assert result["count"] == 1
    lock_call = conn.execute.await_args_list[0]
    assert "pg_advisory_xact_lock" in lock_call.args[0]
    assert lock_call.args[1].endswith(f":api_rate_limits:{raw_id}")


def test_find_one_and_delete_by_id_is_one_atomic_statement():
    raw_id = "64b64c8f2f9b2d7a1c000001"
    conn = _FakeConnection([{"id": raw_id, "data": {"cliente": "Demo"}}])
    collection = DocumentCollection(_FakeDatabase(conn), "cantieri")

    deleted = asyncio.run(collection.find_one_and_delete({"_id": ObjectId(raw_id)}))

    assert deleted["cliente"] == "Demo"
    assert "delete from private.runtime_documents" in conn.fetchrow.await_args.args[0]
    assert "returning id, data" in conn.fetchrow.await_args.args[0]
    conn.execute.assert_not_awaited()
