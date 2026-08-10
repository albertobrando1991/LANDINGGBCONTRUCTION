import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from migrate_backup_to_supabase import decode_extended_json, load_backup


def test_decode_extended_json_preserves_runtime_values():
    decoded = decode_extended_json(
        {
            "_id": {"$oid": "64b64c8f2f9b2d7a1c000001"},
            "count": {"$numberInt": "3"},
            "large": {"$numberLong": "9007199254740991"},
            "score": {"$numberDouble": "0.95"},
            "created_at": {"$date": {"$numberLong": "0"}},
        }
    )
    assert decoded == {
        "_id": "64b64c8f2f9b2d7a1c000001",
        "count": 3,
        "large": 9007199254740991,
        "score": 0.95,
        "created_at": "1970-01-01T00:00:00+00:00",
    }


def test_load_backup_verifies_manifest_file_hash_and_counts(tmp_path):
    row = {
        "_id": {"$oid": "64b64c8f2f9b2d7a1c000001"},
        "name": "Antonio",
        "count": {"$numberInt": "1"},
    }
    collection = tmp_path / "leads.jsonl.gz"
    with gzip.open(collection, "wt", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(row) + "\n")
    collection_sha = hashlib.sha256(collection.read_bytes()).hexdigest()
    manifest = {
        "format": "mongodb_extended_json_v2_jsonl_gzip",
        "database": "gb_construction",
        "exported_at": "2026-08-10T09:43:30+00:00",
        "collections": {
            "leads": {
                "count": 1,
                "file": collection.name,
                "sha256": collection_sha,
                "indexes": [],
            }
        },
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    metadata, collections = load_backup(tmp_path, manifest_sha)

    assert metadata["manifest_sha256"] == manifest_sha
    assert metadata["source_count"] == 1
    assert collections["leads"]["documents"] == [
        ("64b64c8f2f9b2d7a1c000001", {"name": "Antonio", "count": 1})
    ]
