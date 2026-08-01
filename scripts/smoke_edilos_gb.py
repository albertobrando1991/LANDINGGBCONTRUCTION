"""Smoke E2E GB: prezzario → computo da AI → valida → conferma → preventivo → PDF.

Uso (Supabase locale + SUPABASE_DB_URL):
  python scripts/smoke_edilos_gb.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
load_dotenv(BACKEND / ".env", override=True)

# default locale se non impostato
os.environ.setdefault(
    "SUPABASE_DB_URL", "postgresql://postgres:postgres@127.0.0.1:55432/postgres"
)

import db as db_pg
import boq_service
import mapping_engine
import prezzario_service
from engines.metriche import estrai_metriche
from legacy_tenant import GB_TENANT_ID, LEGACY_STAFF_MAP, claims_for_user
from preventivo_pdf import genera_pdf_preventivo


async def main() -> int:
    await db_pg.init_pool()
    if not db_pg.pool_ready():
        print("FAIL: SUPABASE_DB_URL non disponibile")
        return 2

    admin_email = "admin@gbconstruction.it"
    uid, role = LEGACY_STAFF_MAP[admin_email]
    user = {
        "email": admin_email,
        "role": "admin",
        "auth_provider": "legacy",
        "name": "Giuseppe Brancale",
    }
    claims = claims_for_user(user)
    print("claims.sub =", claims["sub"])

    async with db_pg.tenant_conn_claims(claims) as conn:
        # membership
        m = await conn.fetchrow(
            "select role from public.tenant_members where tenant_id = $1::uuid and user_id = $2::uuid",
            GB_TENANT_ID,
            uid,
        )
        if not m:
            print("FAIL: membership admin assente — esegui supabase db reset")
            return 1
        print("OK membership role =", m["role"])

        prezzari = await prezzario_service.lista_prezzari(conn, GB_TENANT_ID)
        print(f"OK prezzari = {len(prezzari)}")
        assert prezzari, "nessun prezzario"
        prezz_id = prezzari[0]["id"]
        wizard = await prezzario_service.voci_wizard(conn, GB_TENANT_ID, prezz_id)
        print(f"OK wizard voci = {len(wizard)}")
        assert len(wizard) == 28

        # sistema non modificabile
        try:
            await prezzario_service.applica_wizard(
                conn, GB_TENANT_ID, prezz_id, {wizard[0]["id"]: wizard[0]["prezzo_unitario"]}
            )
            print("FAIL: wizard su sistema doveva fallire")
            return 1
        except Exception as exc:
            print("OK blocco prezzario sistema:", str(exc.detail if hasattr(exc, "detail") else exc)[:80])

        # duplica
        custom = await prezzario_service.duplica_prezzario(
            conn, GB_TENANT_ID, prezz_id, "Listino GB operativo"
        )
        print("OK duplica prezzario", custom["id"])

        metriche = estrai_metriche(
            {
                "mq": 85,
                "bagni": 2,
                "camere": 3,
                "punti_luce": 40,
                "mq_intonaco": 200,
                "ml_tramezzi_demolire": 12,
            }
        )
        bozza = await mapping_engine.genera_computo_da_ai(
            conn,
            GB_TENANT_ID,
            metriche=metriche,
            config_lead={"livello": "premium"},
            prezzario_id=prezz_id,
        )
        print(
            f"OK computo AI id={bozza['id']} voci={bozza['n_voci']} totale={bozza['totale']}"
        )
        assert bozza["n_voci"] > 0

        n = await boq_service.valida_voci_ai(conn, GB_TENANT_ID, bozza["id"])
        print(f"OK validate AI = {n}")
        conf = await boq_service.conferma_computo(conn, GB_TENANT_ID, bozza["id"])
        print("OK conferma stato =", conf["stato"])
        prev = await boq_service.computo_to_preventivo(
            conn, GB_TENANT_ID, bozza["id"], sconto=0, iva=10
        )
        print("OK preventivo", prev["numero"], "totale", prev["totale_documento"])

        tenant_row = await conn.fetchrow(
            "select * from public.tenants where id = $1::uuid", GB_TENANT_ID
        )
        tenant = dict(tenant_row)
        pdf = genera_pdf_preventivo(prev, tenant)
        out = ROOT / "scripts" / "_smoke_preventivo_gb.pdf"
        out.write_bytes(pdf)
        print(f"OK PDF bytes={len(pdf)} → {out}")

    await db_pg.close_pool()
    print("SMOKE GB OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
