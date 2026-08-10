"""Importa in Supabase un backup Extended JSON verificato, senza contattare Mongo.

La scrittura avviene in una singola transazione. Hash, conteggi e digest dei
payload vengono verificati prima del commit; qualsiasi divergenza fa rollback.
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import db as db_pg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backup", required=True, help="Directory contenente manifest.json")
    parser.add_argument("--tenant", default="gbconstruction")
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--apply", action="store_true", help="Esegue l'import atomico")
    parser.add_argument(
        "--verify-remote",
        action="store_true",
        help="Confronta lo snapshot con i dati gia presenti su Supabase",
    )
    return parser.parse_args()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def decode_extended_json(value: Any) -> Any:
    if isinstance(value, list):
        return [decode_extended_json(item) for item in value]
    if not isinstance(value, dict):
        return value

    if set(value) == {"$oid"}:
        return str(value["$oid"])
    if set(value) in ({"$numberInt"}, {"$numberLong"}):
        return int(next(iter(value.values())))
    if set(value) == {"$numberDouble"}:
        raw = str(value["$numberDouble"])
        parsed = float(raw)
        return parsed if math.isfinite(parsed) else raw
    if set(value) == {"$numberDecimal"}:
        return str(value["$numberDecimal"])
    if set(value) == {"$date"}:
        raw_date = decode_extended_json(value["$date"])
        if isinstance(raw_date, int):
            return datetime.fromtimestamp(raw_date / 1000, timezone.utc).isoformat()
        return str(raw_date)
    if set(value) == {"$binary"}:
        binary = value["$binary"]
        return {
            "$binary": {
                "base64": str(binary.get("base64") or ""),
                "subType": str(binary.get("subType") or ""),
            }
        }
    return {str(key): decode_extended_json(item) for key, item in value.items()}


def canonical_digest(documents: list[tuple[str, dict]]) -> str:
    canonical = json.dumps(
        sorted(documents, key=lambda item: item[0]),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(canonical)


def load_backup(backup_dir: Path, expected_manifest_sha256: str | None) -> tuple[dict, dict]:
    manifest_path = backup_dir / "manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest_sha256 = sha256_bytes(manifest_bytes)
    if expected_manifest_sha256 and manifest_sha256 != expected_manifest_sha256.lower():
        raise RuntimeError(
            f"Hash manifest inatteso: {manifest_sha256}; atteso {expected_manifest_sha256.lower()}"
        )

    manifest = json.loads(manifest_bytes)
    if manifest.get("format") != "mongodb_extended_json_v2_jsonl_gzip":
        raise RuntimeError(f"Formato backup non supportato: {manifest.get('format')!r}")

    collections: dict[str, dict] = {}
    for name, metadata in sorted(manifest.get("collections", {}).items()):
        source_path = backup_dir / metadata["file"]
        file_sha256 = sha256_bytes(source_path.read_bytes())
        if file_sha256 != metadata["sha256"]:
            raise RuntimeError(f"Hash file non valido per {name}: {file_sha256}")
        documents: list[tuple[str, dict]] = []
        with gzip.open(source_path, "rt", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                decoded = decode_extended_json(json.loads(line))
                raw_id = str(decoded.pop("_id", ""))
                if not raw_id:
                    raise RuntimeError(f"Documento senza _id: {name}:{line_number}")
                documents.append((raw_id, decoded))
        if len(documents) != int(metadata["count"]):
            raise RuntimeError(
                f"Conteggio backup non valido per {name}: {len(documents)} != {metadata['count']}"
            )
        collections[name] = {
            "documents": documents,
            "count": len(documents),
            "digest": canonical_digest(documents),
            "source_sha256": file_sha256,
        }

    return {
        "manifest": manifest,
        "manifest_sha256": manifest_sha256,
        "source_count": sum(item["count"] for item in collections.values()),
    }, collections


async def connect() -> asyncpg.Connection:
    dsn = db_pg.resolve_db_url()
    if not dsn:
        raise RuntimeError(
            "DSN Supabase assente: configura CONNECTION_STRING_SUPABASE o SUPABASE_DB_URL"
        )
    clean_dsn, kwargs = db_pg._prepare_asyncpg_dsn(dsn)
    return await asyncpg.connect(clean_dsn, command_timeout=120, **kwargs)


async def fetch_remote_collection(
    conn: asyncpg.Connection, tenant_id: str, collection: str
) -> list[tuple[str, dict]]:
    rows = await conn.fetch(
        """
        select id, data
        from private.runtime_documents
        where tenant_id = $1::uuid and collection = $2
        order by id
        """,
        tenant_id,
        collection,
    )
    result = []
    for row in rows:
        payload = row["data"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        result.append((str(row["id"]), dict(payload or {})))
    return result


async def verify_remote(
    conn: asyncpg.Connection,
    tenant_id: str,
    collections: dict[str, dict],
) -> dict[str, dict]:
    evidence: dict[str, dict] = {}
    for name, source in collections.items():
        remote = await fetch_remote_collection(conn, tenant_id, name)
        remote_digest = canonical_digest(remote)
        if len(remote) != source["count"] or remote_digest != source["digest"]:
            raise RuntimeError(
                f"Parita fallita per {name}: "
                f"righe {len(remote)}/{source['count']}, "
                f"digest {remote_digest}/{source['digest']}"
            )
        evidence[name] = {
            "count": source["count"],
            "decoded_digest": source["digest"],
            "source_sha256": source["source_sha256"],
        }
    return evidence


async def run(args: argparse.Namespace) -> None:
    backup_dir = Path(args.backup).resolve()
    metadata, collections = load_backup(backup_dir, args.expected_manifest_sha256)
    print(
        f"backup_verified: collections={len(collections)} rows={metadata['source_count']} "
        f"manifest_sha256={metadata['manifest_sha256']}"
    )
    if not args.apply and not args.verify_remote:
        return
    if args.apply and not args.expected_manifest_sha256:
        raise RuntimeError("--apply richiede --expected-manifest-sha256")

    conn = await connect()
    try:
        tenant_id = await conn.fetchval(
            "select id from public.tenants where slug = $1", args.tenant
        )
        if not tenant_id:
            raise RuntimeError(f"Tenant Supabase non trovato: {args.tenant}")
        tenant_id = str(tenant_id)

        if args.apply:
            async with conn.transaction():
                existing_audit = await conn.fetchval(
                    """
                    select 1 from private.runtime_migration_audits
                    where manifest_sha256 = $1
                    """,
                    metadata["manifest_sha256"],
                )
                existing_rows = await conn.fetchval(
                    "select count(*) from private.runtime_documents where tenant_id = $1::uuid",
                    tenant_id,
                )
                if existing_audit:
                    print("import_already_audited: verifying existing Supabase snapshot")
                elif existing_rows:
                    raise RuntimeError(
                        "Destinazione runtime non vuota e priva dell'audit di questo snapshot; "
                        "import interrotto per evitare sovrascritture"
                    )
                else:
                    for collection, source in collections.items():
                        rows = [
                            (
                                tenant_id,
                                collection,
                                raw_id,
                                json.dumps(payload, ensure_ascii=False),
                            )
                            for raw_id, payload in source["documents"]
                        ]
                        if rows:
                            await conn.executemany(
                                """
                                insert into private.runtime_documents
                                  (tenant_id, collection, id, data)
                                values ($1::uuid, $2, $3, $4::jsonb)
                                """,
                                rows,
                            )

                evidence = await verify_remote(conn, tenant_id, collections)
                if not existing_audit:
                    await conn.execute(
                        """
                        insert into private.runtime_migration_audits (
                          manifest_sha256, tenant_id, source_database,
                          source_exported_at, collections, source_count, imported_count
                        ) values ($1, $2::uuid, $3, $4::timestamptz, $5::jsonb, $6, $6)
                        """,
                        metadata["manifest_sha256"],
                        tenant_id,
                        metadata["manifest"].get("database") or "unknown",
                        datetime.fromisoformat(metadata["manifest"]["exported_at"]),
                        json.dumps(evidence, ensure_ascii=False),
                        metadata["source_count"],
                    )
            print(f"import_committed: tenant={args.tenant} rows={metadata['source_count']}")
        else:
            evidence = await verify_remote(conn, tenant_id, collections)
            print(
                f"remote_parity_verified: tenant={args.tenant} "
                f"collections={len(evidence)} rows={metadata['source_count']}"
            )
    finally:
        await conn.close()


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
