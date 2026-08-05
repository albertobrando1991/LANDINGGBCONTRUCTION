"""Test isolamento tenant — struttura estendibile.

Quando SUPABASE_DB_URL non è configurato, i test di isolation live sono skippati.
Il test catalogo RLS richiede Postgres; altrimenti si valida solo la lista tabelle attesa.
"""
from __future__ import annotations

import os
import json

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
    # SUPABASE_DB_URL viene impostata esplicitamente da CI e dagli smoke locali.
    # Deve prevalere sulla connessione remota eventualmente caricata dalla .env
    # quando altri moduli della suite importano l'applicazione.
    for key in ("SUPABASE_DB_URL", "CONNECTION_STRING_SUPABASE", "DATABASE_URL"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return None


def test_dsn_rls_preferisce_override_locale(monkeypatch):
    monkeypatch.setenv(
        "CONNECTION_STRING_SUPABASE",
        "postgresql://postgres:secret@remote.example.test/postgres",
    )
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:postgres@127.0.0.1:55432/postgres",
    )

    assert _pg_dsn() == "postgresql://postgres:postgres@127.0.0.1:55432/postgres"


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

    asyncio.run(_run())


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

    asyncio.run(_run())


@pytest.mark.skipif(
    os.environ.get("EDILOS_RLS_TESTS") != "1" or not _pg_dsn(),
    reason="Test RLS distruttivo-isolato abilitato solo sul database locale CI",
)
def test_rls_isola_dati_reali_e_vista_aggregata():
    """Popola entrambi i tenant in una transazione poi verifica letture/scritture A/B."""
    import asyncio
    import asyncpg
    import mapping_engine
    import prezzario_service

    tenant_a = "a0000000-0000-4000-8000-000000000001"
    tenant_b = "a0000000-0000-4000-8000-000000000002"
    user_a = "f1000000-0000-4000-8000-000000000001"
    staff_a = "f1000000-0000-4000-8000-000000000002"
    user_b = "f2000000-0000-4000-8000-000000000001"

    async def _claims(conn, user_id):
        await conn.execute("set local role authenticated")
        claims = json.dumps(
            {"sub": user_id, "role": "authenticated", "aud": "authenticated"}
        )
        await conn.execute(
            "select set_config('request.jwt.claims', $1, true)", claims
        )
        await conn.execute(
            "select set_config('request.jwt.claim.sub', $1, true)", user_id
        )
        await conn.execute(
            "select set_config('request.jwt.claim.role', 'authenticated', true)"
        )

    async def _insert_fixture(conn, tenant_id, suffix, prezzario_id, voce_id):
        cliente_id = await conn.fetchval(
            "insert into public.clienti (tenant_id, nome) values ($1::uuid, $2) returning id",
            tenant_id,
            f"Cliente {suffix}",
        )
        lead_id = await conn.fetchval(
            """
            insert into public.leads (
              tenant_id, cliente_id, nome, email, telefono, legacy_mongo_id
            ) values ($1::uuid, $2::uuid, $3, $4, $5, $6) returning id
            """,
            tenant_id,
            cliente_id,
            f"Lead {suffix}",
            f"lead-{suffix.lower()}@example.test",
            "+39000000000",
            f"rls-fixture-{suffix.lower()}",
        )
        cantiere_id = await conn.fetchval(
            """
            insert into public.cantieri (tenant_id, lead_id, cliente_id, cliente)
            values ($1::uuid, $2::uuid, $3::uuid, $4) returning id
            """,
            tenant_id,
            lead_id,
            cliente_id,
            f"Cantiere {suffix}",
        )
        computo_id = await conn.fetchval(
            """
            insert into public.computi (
              tenant_id, lead_id, cantiere_id, prezzario_id, stato
            ) values ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'bozza') returning id
            """,
            tenant_id,
            lead_id,
            cantiere_id,
            prezzario_id,
        )
        await conn.execute(
            """
            insert into public.computo_voci (
              tenant_id, computo_id, origine_voce_id, super_categoria,
              categoria, descrizione, um, qta, prezzo_unitario
            ) values ($1::uuid, $2::uuid, $3::uuid, 'Test', 'Test', $4, 'cad', 1, 10)
            """,
            tenant_id,
            computo_id,
            voce_id,
            f"Voce {suffix}",
        )
        await conn.execute(
            """
            insert into public.preventivi (
              tenant_id, computo_id, lead_id, numero, anno, progressivo
            ) values ($1::uuid, $2::uuid, $3::uuid, $4, 2099, 1)
            """,
            tenant_id,
            computo_id,
            lead_id,
            f"RLS-{suffix}",
        )

    async def _run():
        conn = await asyncpg.connect(_pg_dsn())
        tx = conn.transaction()
        await tx.start()
        try:
            await _insert_fixture(
                conn,
                tenant_a,
                "A",
                "b0000000-0000-4000-8000-000000000001",
                "c0000000-0000-4000-8000-000000000001",
            )
            await _insert_fixture(
                conn,
                tenant_b,
                "B",
                "b0000000-0000-4000-8000-000000000002",
                "d0000000-0000-4000-8000-000000000001",
            )

            for user_id, own_tenant, other_tenant in (
                (user_a, tenant_a, tenant_b),
                (user_b, tenant_b, tenant_a),
            ):
                await _claims(conn, user_id)
                for table in TABELLE_TENANT:
                    own = await conn.fetchval(
                        f"select count(*) from public.{table} where tenant_id = $1::uuid",
                        own_tenant,
                    )
                    other = await conn.fetchval(
                        f"select count(*) from public.{table} where tenant_id = $1::uuid",
                        other_tenant,
                    )
                    assert int(own) > 0, f"{table}: dati propri non leggibili"
                    assert int(other) == 0, f"{table}: leak cross-tenant"

                own_totals = await conn.fetchval(
                    "select count(*) from public.computi_totali where tenant_id = $1::uuid",
                    own_tenant,
                )
                other_totals = await conn.fetchval(
                    "select count(*) from public.computi_totali where tenant_id = $1::uuid",
                    other_tenant,
                )
                assert int(own_totals) > 0
                assert int(other_totals) == 0, "computi_totali ignora RLS"
                await conn.execute("reset role")

            await _claims(conn, user_a)
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute(
                        "insert into public.clienti (tenant_id, nome) values ($1::uuid, 'Leak')",
                        tenant_b,
                    )
            await conn.execute("reset role")

            await _claims(conn, user_a)
            custom = await prezzario_service.duplica_prezzario(
                conn,
                tenant_a,
                "b0000000-0000-4000-8000-000000000001",
                "Listino RLS test",
            )
            assert custom["is_default"] is True
            custom_voce = await conn.fetchrow(
                """
                update public.prezzario_voci set prezzo_unitario = 77
                where tenant_id = $1::uuid and prezzario_id = $2::uuid
                  and codice = 'VS-035'
                returning id
                """,
                tenant_a,
                custom["id"],
            )
            regole = await mapping_engine.carica_regole(
                conn, tenant_a, custom["id"]
            )
            pavimento = next(r for r in regole if r.metrica == "mq_pavimento")
            assert pavimento.prezzario_voce_id == str(custom_voce["id"])
            assert pavimento.prezzo_unitario == 77
            with pytest.raises(asyncpg.RaiseError):
                async with conn.transaction():
                    await conn.execute(
                        """
                        update public.prezzario_voci set prezzo_unitario = 999
                        where id = 'c0000000-0000-4000-8000-000000000001'
                        """
                    )
            await conn.execute("reset role")

            # Il lock applicativo non deve dipendere dalla policy UPDATE di
            # tenants: anche un membro staff autorizzato sui prezzari deve
            # poter serializzare il cambio del listino predefinito.
            await _claims(conn, staff_a)
            selected = await prezzario_service.imposta_default(
                conn, tenant_a, custom["id"]
            )
            assert selected["id"] == custom["id"]
            await conn.execute("reset role")

            await conn.execute("set local role anon")
            public_rows = await conn.fetch(
                "select slug, ragione_sociale, theme, contatti from public.tenants"
            )
            assert {row["slug"] for row in public_rows} >= {"gbconstruction", "demo"}
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.fetch("select piva from public.tenants")
            await conn.execute("reset role")
        finally:
            await tx.rollback()
            await conn.close()

    asyncio.run(_run())
