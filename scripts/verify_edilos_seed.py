"""Verifica seed EdilOS su Postgres locale."""
import asyncio
import os
import sys

import asyncpg


async def main():
    dsn = os.environ.get(
        "SUPABASE_DB_URL", "postgresql://postgres:postgres@127.0.0.1:55432/postgres"
    )
    c = await asyncpg.connect(dsn)
    tenants = await c.fetch(
        "select slug, ragione_sociale from public.tenants order by slug"
    )
    print("tenants:", [dict(t) for t in tenants])
    wiz = await c.fetchval(
        """
        select count(*) from public.prezzario_voci
        where chiave_wizard
          and tenant_id = (select id from public.tenants where slug = 'gbconstruction')
        """
    )
    total = await c.fetchval(
        """
        select count(*) from public.prezzario_voci
        where tenant_id = (select id from public.tenants where slug = 'gbconstruction')
        """
    )
    maps = await c.fetchval(
        """
        select count(*) from public.mapping_regole
        where tenant_id = (select id from public.tenants where slug = 'gbconstruction')
        """
    )
    print(f"voci totali={total} wizard={wiz} mapping={maps}")
    assert wiz == 28, wiz
    assert total >= 80, total

    rows = await c.fetch(
        """
        select c.relname, c.relrowsecurity as rls
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        join information_schema.columns col
          on col.table_schema = n.nspname and col.table_name = c.relname
        where n.nspname = 'public'
          and c.relkind = 'r'
          and col.column_name = 'tenant_id'
        """
    )
    missing = [r["relname"] for r in rows if not r["rls"]]
    print("tables with tenant_id:", len(rows), "missing RLS:", missing)
    assert not missing, missing
    await c.close()
    print("OK")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print("FAIL:", exc)
        sys.exit(1)
