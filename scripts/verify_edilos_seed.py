"""Verifica seed EdilOS su Postgres locale."""

import asyncio
import os
import sys

import asyncpg


async def main():
    dsn = (
        os.environ.get("CONNECTION_STRING_SUPABASE")
        or os.environ.get("SUPABASE_DB_URL")
        or os.environ.get("DATABASE_URL")
        or "postgresql://postgres:postgres@127.0.0.1:55432/postgres"
    )
    c = await asyncpg.connect(dsn)
    tenants = await c.fetch(
        "select slug, ragione_sociale from public.tenants order by slug"
    )
    print("tenants:", [dict(t) for t in tenants])
    default_prezzario = await c.fetchval("""
        select id from public.prezzari
        where tenant_id = (select id from public.tenants where slug = 'gbconstruction')
          and is_default = true
        """)
    assert default_prezzario, "Prezzario default GB assente"
    wiz = await c.fetchval(
        """
        select count(*) from public.prezzario_voci
        where chiave_wizard
          and prezzario_id = $1::uuid
        """,
        default_prezzario,
    )
    total = await c.fetchval(
        """
        select count(*) from public.prezzario_voci
        where prezzario_id = $1::uuid
        """,
        default_prezzario,
    )
    maps = await c.fetchval("""
        select count(*) from public.mapping_regole
        where tenant_id = (select id from public.tenants where slug = 'gbconstruction')
        """)
    print(f"voci totali={total} wizard={wiz} mapping={maps}")
    assert wiz == 28, wiz
    assert total >= 80, total
    assert maps >= 13, maps

    invalid_defaults = await c.fetch("""
        select tenant_id, count(*) filter (where is_default) as defaults
        from public.prezzari
        group by tenant_id
        having count(*) filter (where is_default) <> 1
        """)
    assert invalid_defaults == [], invalid_defaults

    rows = await c.fetch("""
        select c.relname, c.relrowsecurity as rls
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        join information_schema.columns col
          on col.table_schema = n.nspname and col.table_name = c.relname
        where n.nspname = 'public'
          and c.relkind = 'r'
          and col.column_name = 'tenant_id'
        """)
    missing = [r["relname"] for r in rows if not r["rls"]]
    print("tables with tenant_id:", len(rows), "missing RLS:", missing)
    assert not missing, missing
    view_options = await c.fetchval("""
        select reloptions from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relname = 'computi_totali'
        """)
    assert view_options and "security_invoker=true" in view_options, view_options

    buckets = await c.fetch(
        """
        select id, public, file_size_limit, allowed_mime_types
        from storage.buckets
        where id in ('planimetrie','render','foto-cantiere','documenti')
        """
    )
    assert len(buckets) == 4, buckets
    assert all(not row["public"] for row in buckets), buckets
    assert all(int(row["file_size_limit"] or 0) > 0 for row in buckets), buckets
    assert all(row["allowed_mime_types"] for row in buckets), buckets

    storage_policies = await c.fetch(
        """
        select policyname, cmd, roles, qual, with_check
        from pg_policies
        where schemaname = 'storage'
          and tablename = 'objects'
          and policyname in (
            'storage_tenant_read', 'storage_tenant_write',
            'storage_tenant_update', 'storage_tenant_delete'
          )
        """
    )
    assert len(storage_policies) == 4, storage_policies
    for policy in storage_policies:
        expression = f"{policy['qual'] or ''} {policy['with_check'] or ''}"
        assert "has_role" in expression, policy
        assert "client" not in expression, policy
        assert "authenticated" in policy["roles"], policy
    await c.close()
    print("OK")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print("FAIL:", exc)
        sys.exit(1)
