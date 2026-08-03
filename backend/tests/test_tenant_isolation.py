"""Test isolamento tenant — struttura estendibile.

Quando SUPABASE_DB_URL non è configurato, i test di isolation live sono skippati.
Il test catalogo RLS richiede Postgres; altrimenti si valida solo la lista tabelle attesa.
"""
from __future__ import annotations

import os

import pytest

# (tabella, note) — estendere qui a ogni nuova tabella tenant-scoped
TABELLE_TENANT = [
    "clienti",
    "leads",
    "cantieri",
    "prezzari",
    "prezzario_voci",
    "computi",
    "computo_voci",
    "mapping_regole",
    "preventivi",
]


def test_tabelle_tenant_elencate():
    """Garantisce che le tabelle di dominio multi-tenant siano documentate nel test."""
    assert "leads" in TABELLE_TENANT
    assert "prezzario_voci" in TABELLE_TENANT
    assert "computo_voci" in TABELLE_TENANT
    assert "preventivi" in TABELLE_TENANT


def _pg_dsn() -> str | None:
    for key in ("CONNECTION_STRING_SUPABASE", "SUPABASE_DB_URL", "DATABASE_URL"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return None


@pytest.mark.skipif(
    not (
        os.environ.get("CONNECTION_STRING_SUPABASE")
        or os.environ.get("SUPABASE_DB_URL")
        or os.environ.get("DATABASE_URL")
    ),
    reason="Nessuna DSN Postgres — isolation live richiede CONNECTION_STRING_SUPABASE",
)
def test_ogni_tabella_con_tenant_id_ha_rls():
    import asyncio
    import asyncpg

    async def _run():
        dsn = _pg_dsn()
        assert dsn
        # sslmode=require gestito da libpq-style URL: asyncpg vuole ssl= esplicito su cloud
        kwargs = {}
        if "supabase" in dsn or "sslmode=" in dsn:
            import ssl

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            kwargs["ssl"] = ctx
            dsn = dsn.split("?")[0]
        conn = await asyncpg.connect(dsn, **kwargs)
        try:
            rows = await conn.fetch(
                """
                select c.relname as table_name, c.relrowsecurity as rls
                from pg_class c
                join pg_namespace n on n.oid = c.relnamespace
                join information_schema.columns col
                  on col.table_schema = n.nspname and col.table_name = c.relname
                where n.nspname = 'public'
                  and c.relkind = 'r'
                  and col.column_name = 'tenant_id'
                """
            )
            missing = []
            for r in rows:
                if not r["rls"]:
                    missing.append(r["table_name"])
                    continue
                n_policies = await conn.fetchval(
                    """
                    select count(*) from pg_policies
                    where schemaname = 'public' and tablename = $1
                    """,
                    r["table_name"],
                )
                if int(n_policies or 0) < 2:
                    missing.append(f"{r['table_name']} (policies={n_policies})")
            assert missing == [], f"Tabelle con tenant_id senza RLS/policy: {missing}"
        finally:
            await conn.close()

    asyncio.get_event_loop().run_until_complete(_run())


@pytest.mark.skipif(
    not os.environ.get("SUPABASE_DB_URL"),
    reason="SUPABASE_DB_URL non configurato",
)
@pytest.mark.parametrize("tabella", TABELLE_TENANT)
def test_tabella_presente_nello_schema(tabella):
    import asyncio
    import asyncpg

    async def _run():
        conn = await asyncpg.connect(os.environ["SUPABASE_DB_URL"])
        try:
            exists = await conn.fetchval(
                """
                select exists(
                  select 1 from information_schema.tables
                  where table_schema = 'public' and table_name = $1
                )
                """,
                tabella,
            )
            assert exists, f"Tabella mancante: {tabella}"
        finally:
            await conn.close()

    asyncio.get_event_loop().run_until_complete(_run())
