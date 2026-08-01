"""Backfill MongoDB → Postgres (tenant gbconstruction).
Idempotente via legacy_mongo_id. Usa system_conn (service_role path).

Uso:
  python -m system_jobs.backfill_mongo --dry-run
  python -m system_jobs.backfill_mongo
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# allow `python -m system_jobs.backfill_mongo` from backend/
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT / ".env", override=True)

from motor.motor_asyncio import AsyncIOMotorClient

import db as db_pg


TENANT_SLUG = "gbconstruction"
ROLE_MAP = {
    "admin": "owner",
    "staff": "staff",
    "operations": "operations",
}


async def run(*, dry_run: bool = False) -> int:
    await db_pg.init_pool()
    if not db_pg.pool_ready():
        print("ERRORE: SUPABASE_DB_URL non configurato")
        return 2

    mongo_url = (
        os.environ.get("MONGO_URL")
        or os.environ.get("MONGO_PUBLIC_URL")
        or os.environ.get("MONGODB_URI")
        or "mongodb://localhost:27017"
    )
    mongo = AsyncIOMotorClient(mongo_url)
    mdb = mongo[
        os.environ.get("DB_NAME")
        or os.environ.get("PROD_DB_NAME")
        or "gb_construction"
    ]

    async with db_pg.system_conn() as conn:
        tenant_id = await conn.fetchval(
            "select id from public.tenants where slug = $1", TENANT_SLUG
        )
        if not tenant_id:
            print(f"ERRORE: tenant {TENANT_SLUG} assente — esegui seed.sql prima")
            return 2

        users = await mdb.users.find({}).to_list(None)
        leads = await mdb.leads.find({}).to_list(None)
        cantieri = await mdb.cantieri.find({}).to_list(None)

        print(f"Mongo: users={len(users)} leads={len(leads)} cantieri={len(cantieri)}")
        print(f"Tenant destinazione: {TENANT_SLUG} ({tenant_id})")

        if dry_run:
            print("Dry-run: nessuna scrittura")
            exit_code = 0
        else:
            # Note: utenti Supabase Auth non migrabili con password.
            invites = []
            for u in users:
                email = (u.get("email") or "").lower()
                role = ROLE_MAP.get(u.get("role") or "staff", "staff")
                invites.append({"email": email, "role": role, "name": u.get("name")})
                print(f"  user invite: {email} → role {role} (password non migrabile)")

            lead_ok = 0
            for lead in leads:
                mid = str(lead.get("_id"))
                tags = lead.get("tags") or []
                if not isinstance(tags, list):
                    tags = [str(tags)]
                tags = [str(t) for t in tags]
                try:
                    await conn.execute(
                        """
                        insert into public.leads (
                          tenant_id, nome, email, telefono, citta, indirizzo, privacy,
                          newsletter, status, owner, tags, score, config, stima, tracking,
                          timeline, note_cliente, prossima_azione, legacy_mongo_id
                        ) values (
                          $1::uuid, $2, $3, $4, $5, $6, coalesce($7, true),
                          coalesce($8, false), coalesce($9, 'nuovo'), $10, $11::text[],
                          $12, coalesce($13::jsonb, '{}'::jsonb), $14::jsonb,
                          coalesce($15::jsonb, '{}'::jsonb), coalesce($16::jsonb, '[]'::jsonb),
                          $17, $18, $19
                        )
                        on conflict (legacy_mongo_id) do nothing
                        """,
                        str(tenant_id),
                        lead.get("nome") or lead.get("name") or "Lead",
                        lead.get("email") or "unknown@example.com",
                        lead.get("telefono") or lead.get("phone") or "",
                        lead.get("citta"),
                        lead.get("indirizzo"),
                        lead.get("privacy"),
                        lead.get("newsletter"),
                        lead.get("status") or lead.get("stato"),
                        lead.get("owner"),
                        tags,
                        lead.get("score"),
                        __import__("json").dumps(lead.get("config") or {}, default=str),
                        __import__("json").dumps(lead.get("stima"), default=str)
                        if lead.get("stima")
                        else None,
                        __import__("json").dumps(lead.get("tracking") or {}, default=str),
                        __import__("json").dumps(lead.get("timeline") or [], default=str),
                        lead.get("note_cliente") or lead.get("note"),
                        lead.get("prossima_azione"),
                        mid,
                    )
                    lead_ok += 1
                except Exception as exc:
                    print(f"  lead fail {mid}: {type(exc).__name__}: {exc}")

            cant_ok = 0
            for c in cantieri:
                mid = str(c.get("_id"))
                try:
                    await conn.execute(
                        """
                        insert into public.cantieri (
                          tenant_id, cliente, indirizzo, stato, avanzamento, importo,
                          capocantiere, milestone, note, fasi, legacy_mongo_id
                        ) values (
                          $1::uuid, $2, $3, coalesce($4, 'attivo'), coalesce($5, 0), $6,
                          $7, $8, $9, coalesce($10::jsonb, '[]'::jsonb), $11
                        )
                        on conflict (legacy_mongo_id) do nothing
                        """,
                        str(tenant_id),
                        c.get("cliente") or c.get("nome") or "Cantiere",
                        c.get("indirizzo"),
                        c.get("stato"),
                        c.get("avanzamento") or 0,
                        c.get("importo"),
                        c.get("capocantiere"),
                        c.get("milestone"),
                        c.get("note"),
                        __import__("json").dumps(c.get("fasi") or [], default=str),
                        mid,
                    )
                    cant_ok += 1
                except Exception as exc:
                    print(f"  cantiere fail {mid}: {type(exc).__name__}: {exc}")

            pg_leads = await conn.fetchval(
                "select count(*) from public.leads where tenant_id = $1", tenant_id
            )
            pg_cant = await conn.fetchval(
                "select count(*) from public.cantieri where tenant_id = $1", tenant_id
            )

            print("--- Verifica conteggi ---")
            print(f"leads    Mongo={len(leads)}  Postgres={pg_leads}  (scritti_ok={lead_ok})")
            print(f"cantieri Mongo={len(cantieri)}  Postgres={pg_cant}  (scritti_ok={cant_ok})")
            print(f"inviti reset password: {len(invites)}")
            for inv in invites:
                print(f"  - {inv['email']} ({inv['role']})")

            exit_code = 0
            if pg_leads < len(leads) or pg_cant < len(cantieri):
                print("WARNING: conteggi Postgres inferiori a Mongo")
                exit_code = 1

    mongo.close()
    try:
        await asyncio.wait_for(db_pg.close_pool(), timeout=10)
    except Exception:
        pass
    if dry_run:
        print("Dry-run completato")
    else:
        print("Backfill completato")
    return exit_code


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    raise SystemExit(asyncio.run(run(dry_run=args.dry_run)))


if __name__ == "__main__":
    main()
