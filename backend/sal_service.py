"""SAL derivati dal libretto misure con snapshot economico transazionale."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

import asyncpg
from fastapi import HTTPException

SAL_ROLES = frozenset({"owner", "admin", "staff", "operations"})
SAL_TRANSITIONS = {
    "bozza": {"emesso"},
    "emesso": {"approvato"},
    "approvato": set(),
}


def _d(row: asyncpg.Record | dict | None) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for key, value in list(out.items()):
        if isinstance(value, UUID):
            out[key] = str(value)
        elif isinstance(value, Decimal):
            out[key] = float(value)
    return out


def _linea(row: asyncpg.Record | dict) -> dict:
    item = _d(row)
    progressiva = Decimal(str(item.get("qta_progressiva") or 0))
    contrattuale = Decimal(str(item.get("qta_contrattuale") or 0))
    eccedenza = max(Decimal("0"), progressiva - contrattuale)
    item["eccedenza_qta"] = float(eccedenza)
    item["in_eccedenza"] = eccedenza > 0
    item["proponi_variante"] = eccedenza > 0
    return item


async def _require_cantiere(
    conn: asyncpg.Connection, tenant_id: str, cantiere_id: str
) -> None:
    exists = await conn.fetchval(
        """
        select exists(
          select 1 from public.cantieri
          where id = $1::uuid and tenant_id = $2::uuid
        )
        """,
        cantiere_id,
        tenant_id,
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Cantiere non trovato")


async def genera_sal(
    conn: asyncpg.Connection,
    tenant_id: str,
    cantiere_id: str,
    *,
    periodo_da: date,
    periodo_a: date,
) -> dict:
    """Crea un SAL usando soltanto misure associate a computi confermati."""
    if periodo_da > periodo_a:
        raise HTTPException(
            status_code=400,
            detail="La data iniziale non puo essere successiva alla data finale",
        )
    await _require_cantiere(conn, tenant_id, cantiere_id)

    # Serializza numero e controllo sovrapposizioni per lo stesso cantiere.
    await conn.fetchval(
        "select pg_advisory_xact_lock(hashtextextended($1, 0))",
        f"edilos:sal-progressivo:{tenant_id}:{cantiere_id}",
    )
    overlapping = await conn.fetchrow(
        """
        select id, numero, periodo_da, periodo_a
        from public.sal
        where tenant_id = $1::uuid
          and cantiere_id = $2::uuid
          and periodo_da <= $4::date
          and periodo_a >= $3::date
        order by numero
        limit 1
        """,
        tenant_id,
        cantiere_id,
        periodo_da,
        periodo_a,
    )
    if overlapping:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Il periodo si sovrappone al SAL {overlapping['numero']} "
                f"({overlapping['periodo_da']} - {overlapping['periodo_a']})"
            ),
        )

    righe = await conn.fetch(
        """
        select v.id as computo_voce_id,
               v.descrizione,
               v.um,
               v.qta as qta_contrattuale,
               v.prezzo_unitario,
               coalesce(
                 sum(m.qta) filter (
                   where m.data_misura between $3::date and $4::date
                 ),
                 0
               )::numeric(12,3) as qta_periodo,
               coalesce(
                 sum(m.qta) filter (where m.data_misura <= $4::date),
                 0
               )::numeric(12,3) as qta_progressiva
        from public.computo_voci v
        join public.computi c
          on c.id = v.computo_id and c.tenant_id = v.tenant_id
        left join public.libretto_misure m
          on m.computo_voce_id = v.id
         and m.tenant_id = v.tenant_id
         and m.cantiere_id = c.cantiere_id
         and m.data_misura <= $4::date
        where v.tenant_id = $1::uuid
          and c.cantiere_id = $2::uuid
          and c.stato = 'confermato'
        group by v.id, v.descrizione, v.um, v.qta, v.prezzo_unitario, v.ordine
        having coalesce(
          sum(m.qta) filter (
            where m.data_misura between $3::date and $4::date
          ),
          0
        ) <> 0
        order by v.ordine, v.descrizione, v.id
        """,
        tenant_id,
        cantiere_id,
        periodo_da,
        periodo_a,
    )
    if not righe:
        diagnostica = await conn.fetchrow(
            """
            select
              count(*) filter (
                where m.computo_voce_id is null
              )::integer as misure_libere,
              count(*) filter (
                where m.computo_voce_id is not null
                  and co.stato is distinct from 'confermato'
              )::integer as misure_computo_non_confermato,
              count(*)::integer as misure_periodo
            from public.libretto_misure m
            left join public.computo_voci v
              on v.id = m.computo_voce_id and v.tenant_id = m.tenant_id
            left join public.computi co
              on co.id = v.computo_id and co.tenant_id = v.tenant_id
            where m.tenant_id = $1::uuid
              and m.cantiere_id = $2::uuid
              and m.data_misura between $3::date and $4::date
            """,
            tenant_id,
            cantiere_id,
            periodo_da,
            periodo_a,
        )
        diagnostica = _d(diagnostica) or {}
        misure_libere = int(diagnostica.get("misure_libere") or 0)
        misure_non_confermate = int(
            diagnostica.get("misure_computo_non_confermato") or 0
        )
        if misure_libere:
            detail = (
                f"Sono presenti {misure_libere} misure libere nel periodo, ma "
                "non possono entrare nel SAL perché non sono collegate a una "
                "voce di computo con unità di misura e prezzo. Collega e "
                "conferma un computo, quindi registra le misure sulla relativa voce."
            )
        elif misure_non_confermate:
            detail = (
                f"Sono presenti {misure_non_confermate} misure collegate a un "
                "computo non confermato. Conferma il computo prima di generare il SAL."
            )
        else:
            detail = (
                "Nessuna misura valorizzata nel periodo per voci di computi "
                "confermati. Controlla cantiere e intervallo date."
            )
        raise HTTPException(
            status_code=409,
            detail=detail,
        )

    numero = await conn.fetchval(
        """
        select coalesce(max(numero), 0) + 1
        from public.sal
        where tenant_id = $1::uuid and cantiere_id = $2::uuid
        """,
        tenant_id,
        cantiere_id,
    )
    sal = await conn.fetchrow(
        """
        insert into public.sal (
          tenant_id, cantiere_id, numero, periodo_da, periodo_a, created_by
        ) values ($1::uuid, $2::uuid, $3, $4::date, $5::date, auth.uid())
        returning *
        """,
        tenant_id,
        cantiere_id,
        int(numero),
        periodo_da,
        periodo_a,
    )
    await conn.executemany(
        """
        insert into public.sal_righe (
          tenant_id, sal_id, computo_voce_id, descrizione, um,
          qta_periodo, qta_progressiva, prezzo_unitario
        ) values ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8)
        """,
        [
            (
                tenant_id,
                str(sal["id"]),
                str(riga["computo_voce_id"]),
                riga["descrizione"],
                riga["um"],
                riga["qta_periodo"],
                riga["qta_progressiva"],
                riga["prezzo_unitario"],
            )
            for riga in righe
        ],
    )
    return await get_sal(conn, tenant_id, str(sal["id"]))


async def lista_sal(
    conn: asyncpg.Connection, tenant_id: str, cantiere_id: str
) -> list[dict]:
    await _require_cantiere(conn, tenant_id, cantiere_id)
    rows = await conn.fetch(
        """
        select s.*,
               coalesce(sum(r.importo_periodo), 0)::numeric(14,2) as totale_periodo,
               count(r.id)::integer as numero_righe,
               coalesce(
                 bool_or(r.qta_progressiva > v.qta),
                 false
               ) as contiene_eccedenze
        from public.sal s
        left join public.sal_righe r
          on r.sal_id = s.id and r.tenant_id = s.tenant_id
        left join public.computo_voci v
          on v.id = r.computo_voce_id and v.tenant_id = r.tenant_id
        where s.tenant_id = $1::uuid and s.cantiere_id = $2::uuid
        group by s.id
        order by s.numero desc
        """,
        tenant_id,
        cantiere_id,
    )
    return [_d(row) for row in rows]


async def get_sal(
    conn: asyncpg.Connection,
    tenant_id: str,
    sal_id: str,
    *,
    for_update: bool = False,
) -> dict:
    suffix = " for update" if for_update else ""
    row = await conn.fetchrow(
        f"""
        select * from public.sal
        where id = $1::uuid and tenant_id = $2::uuid{suffix}
        """,
        sal_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="SAL non trovato")
    righe = await conn.fetch(
        """
        select r.*, v.qta as qta_contrattuale
        from public.sal_righe r
        join public.computo_voci v
          on v.id = r.computo_voce_id and v.tenant_id = r.tenant_id
        where r.sal_id = $1::uuid and r.tenant_id = $2::uuid
        order by r.descrizione, r.id
        """,
        sal_id,
        tenant_id,
    )
    item = _d(row)
    item["righe"] = [_linea(riga) for riga in righe]
    item["totale_periodo"] = round(
        sum(float(riga.get("importo_periodo") or 0) for riga in item["righe"]), 2
    )
    item["contiene_eccedenze"] = any(riga["in_eccedenza"] for riga in item["righe"])
    return item


async def get_sal_documento(
    conn: asyncpg.Connection, tenant_id: str, sal_id: str
) -> dict:
    """Compone i dati tenant-safe necessari al PDF SAL e al suo libretto."""
    sal = await get_sal(conn, tenant_id, sal_id)
    cantiere = await conn.fetchrow(
        """
        select id, cliente, indirizzo, capocantiere, stato
        from public.cantieri
        where id = $1::uuid and tenant_id = $2::uuid
        """,
        sal["cantiere_id"],
        tenant_id,
    )
    tenant = await conn.fetchrow(
        """
        select id, slug, ragione_sociale, piva, theme, contatti
        from public.tenants
        where id = $1::uuid
        """,
        tenant_id,
    )
    if not cantiere or not tenant:
        raise HTTPException(status_code=404, detail="Dati documento SAL non trovati")
    misure = await conn.fetch(
        """
        select m.id, m.data_misura, m.descrizione, m.parti,
               m.lunghezza, m.larghezza, m.altezza, m.qta,
               m.foto_paths, v.descrizione as computo_voce_descrizione,
               v.um as computo_voce_um
        from public.libretto_misure m
        join public.sal_righe r
          on r.computo_voce_id = m.computo_voce_id
         and r.sal_id = $1::uuid
         and r.tenant_id = m.tenant_id
        join public.computo_voci v
          on v.id = m.computo_voce_id and v.tenant_id = m.tenant_id
        where m.tenant_id = $2::uuid
          and m.cantiere_id = $3::uuid
          and m.data_misura between $4::date and $5::date
        order by m.data_misura, v.descrizione, m.created_at, m.id
        """,
        sal_id,
        tenant_id,
        sal["cantiere_id"],
        sal["periodo_da"],
        sal["periodo_a"],
    )
    return {
        "sal": sal,
        "cantiere": _d(cantiere),
        "tenant": _d(tenant),
        "misure": [_d(row) for row in misure],
    }


async def aggiorna_stato(
    conn: asyncpg.Connection,
    tenant_id: str,
    sal_id: str,
    nuovo_stato: Literal["emesso", "approvato"],
) -> dict:
    sal = await get_sal(conn, tenant_id, sal_id, for_update=True)
    stato_corrente = sal["stato"]
    if nuovo_stato not in SAL_TRANSITIONS.get(stato_corrente, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Transizione SAL non consentita: {stato_corrente} -> {nuovo_stato}",
        )
    row = await conn.fetchrow(
        """
        update public.sal set stato = $1
        where id = $2::uuid and tenant_id = $3::uuid and stato = $4
        returning id
        """,
        nuovo_stato,
        sal_id,
        tenant_id,
        stato_corrente,
    )
    if not row:
        raise HTTPException(
            status_code=409,
            detail="Il SAL e stato modificato da un altro operatore",
        )
    result = await get_sal(conn, tenant_id, sal_id)
    if nuovo_stato == "approvato":
        import financial_service

        await financial_service.genera_documento_economico(
            conn,
            tenant_id,
            result["cantiere_id"],
            tipo="riepilogo_sal",
            riferimento_id=sal_id,
        )
    return result
