"""Smoke del repository documentale applicativo sul database Supabase scelto."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import db as db_pg
from document_store import PostgresDocumentDatabase, ReturnDocument


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="gbconstruction")
    parser.add_argument("--expected-total", type=int)
    parser.add_argument("--lead-name")
    parser.add_argument("--write-smoke", action="store_true")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    await db_pg.init_pool()
    if not db_pg.pool_ready():
        raise RuntimeError("DSN Supabase non configurato")
    runtime = PostgresDocumentDatabase(db_pg, args.tenant)
    try:
        await runtime.startup()
        async with runtime.pool.acquire() as conn:
            total = await conn.fetchval(
                """
                select count(*)
                from private.runtime_documents d
                join public.tenants t on t.id = d.tenant_id
                where t.slug = $1
                """,
                args.tenant,
            )
        if args.expected_total is not None and total != args.expected_total:
            raise RuntimeError(f"Totale runtime inatteso: {total} != {args.expected_total}")

        if args.lead_name:
            lead = await runtime.leads.find_one(
                {"nome": {"$regex": f"^{args.lead_name}$", "$options": "i"}}
            )
            if not lead:
                raise RuntimeError(f"Lead non trovato: {args.lead_name}")
            if not isinstance(lead.get("timeline"), list):
                raise RuntimeError(
                    f"Timeline non normalizzata per {args.lead_name}: "
                    f"{type(lead.get('timeline')).__name__}"
                )
            print(
                f"lead_verified: name={args.lead_name} id={lead['_id']} "
                f"timeline_events={len(lead['timeline'])}"
            )

        if args.write_smoke:
            smoke_id = "supabase-cutover-smoke"
            await runtime.migration_smoke.delete_one({"_id": smoke_id})
            await runtime.migration_smoke.insert_one({"_id": smoke_id, "count": 1})
            updated = await runtime.migration_smoke.find_one_and_update(
                {"_id": smoke_id},
                {"$inc": {"count": 1}},
                return_document=ReturnDocument.AFTER,
            )
            if not updated or updated.get("count") != 2:
                raise RuntimeError("Smoke write/update fallito")
            deleted = await runtime.migration_smoke.delete_one({"_id": smoke_id})
            if deleted.deleted_count != 1:
                raise RuntimeError("Cleanup smoke fallito")
            print("write_smoke_verified: insert/update/delete clean")

        print(f"runtime_verified: tenant={args.tenant} rows={total}")
    finally:
        await db_pg.close_pool()


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
