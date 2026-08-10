import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from document_id import ObjectId
from document_store import _apply_update, _matches, _projection


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
    assert original == {"_id": ObjectId("64b64c8f2f9b2d7a1c000001"), "count": 1, "tags": ["a"]}


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
