"""Libretto di misura append-only con sincronizzazione idempotente."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

import asyncpg
from fastapi import HTTPException

LIBRETTO_ROLES = frozenset({"owner", "admin", "staff", "operations"})


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


async def lista_cantieri_campo(conn: asyncpg.Connection, tenant_id: str) -> list[dict]:
    """Restituisce i cantieri operativi e le voci confermate per il rilievo.

    Il filtro tenant resta esplicito oltre alle policy RLS e la query aggregata
    evita una lettura separata delle voci per ogni cantiere.
    """
    rows = await conn.fetch(
        """
        select c.id, c.cliente, c.indirizzo, c.stato, c.capocantiere,
               coalesce(
                 jsonb_agg(
                   jsonb_build_object(
                     'id', v.id,
                     'computo_id', co.id,
                     'computo_numero', co.numero,
                     'computo_tipo', co.tipo,
                     'descrizione', v.descrizione,
                     'um', v.um,
                     'qta_contrattuale', v.qta,
                     'ordine', v.ordine
                   )
                   order by co.created_at desc, v.ordine, v.descrizione
                 ) filter (where v.id is not null),
                 '[]'::jsonb
               ) as voci
        from public.cantieri c
        left join public.computi co
          on co.cantiere_id = c.id
         and co.tenant_id = c.tenant_id
         and co.stato = 'confermato'
        left join public.computo_voci v
          on v.computo_id = co.id
         and v.tenant_id = co.tenant_id
        where c.tenant_id = $1::uuid
          and c.stato in ('attivo', 'in_pausa')
        group by c.id
        order by case c.stato when 'attivo' then 0 else 1 end,
                 c.cliente,
                 c.id
        """,
        tenant_id,
    )
    result = []
    for row in rows:
        item = _d(row)
        raw_voci = item.get("voci")
        if isinstance(raw_voci, str):
            raw_voci = json.loads(raw_voci)
        item["voci"] = raw_voci or []
        result.append(item)
    return result


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


async def _require_computo_voce(
    conn: asyncpg.Connection,
    tenant_id: str,
    cantiere_id: str,
    computo_voce_id: str,
) -> None:
    exists = await conn.fetchval(
        """
        select exists(
          select 1
          from public.computo_voci v
          join public.computi c
            on c.id = v.computo_id and c.tenant_id = v.tenant_id
          where v.id = $1::uuid
            and v.tenant_id = $2::uuid
            and c.cantiere_id = $3::uuid
        )
        """,
        computo_voce_id,
        tenant_id,
        cantiere_id,
    )
    if not exists:
        raise HTTPException(
            status_code=404,
            detail="Voce di computo non trovata per questo cantiere",
        )


def _validate_photo_paths(
    tenant_id: str, cantiere_id: str, foto_paths: list[str]
) -> None:
    prefix = f"{tenant_id}/cantiere-{cantiere_id}/"
    if any(not path.startswith(prefix) for path in foto_paths):
        raise HTTPException(
            status_code=400,
            detail="Una o piu foto non appartengono al cantiere selezionato",
        )


async def lista_misure(
    conn: asyncpg.Connection,
    tenant_id: str,
    cantiere_id: str,
    *,
    data_da: Optional[date] = None,
    data_a: Optional[date] = None,
    computo_voce_id: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    await _require_cantiere(conn, tenant_id, cantiere_id)
    if computo_voce_id:
        await _require_computo_voce(conn, tenant_id, cantiere_id, computo_voce_id)

    clauses = ["m.tenant_id = $1::uuid", "m.cantiere_id = $2::uuid"]
    args: list[object] = [tenant_id, cantiere_id]
    if data_da is not None:
        args.append(data_da)
        clauses.append(f"m.data_misura >= ${len(args)}::date")
    if data_a is not None:
        args.append(data_a)
        clauses.append(f"m.data_misura <= ${len(args)}::date")
    if computo_voce_id is not None:
        args.append(computo_voce_id)
        clauses.append(f"m.computo_voce_id = ${len(args)}::uuid")
    args.append(limit)

    rows = await conn.fetch(
        f"""
        select m.*,
               v.descrizione as computo_voce_descrizione,
               v.um as computo_voce_um,
               v.qta as computo_voce_qta
        from public.libretto_misure m
        left join public.computo_voci v
          on v.id = m.computo_voce_id and v.tenant_id = m.tenant_id
        where {' and '.join(clauses)}
        order by m.data_misura desc, m.created_at desc, m.id desc
        limit ${len(args)}
        """,
        *args,
    )
    return [_d(row) for row in rows]


def _same_decimal(stored: object, requested: Optional[Decimal]) -> bool:
    if stored is None or requested is None:
        return stored is None and requested is None
    return Decimal(str(stored)) == requested


def _same_payload(
    row: asyncpg.Record | dict,
    *,
    cantiere_id: str,
    computo_voce_id: Optional[str],
    data_misura: date,
    descrizione: Optional[str],
    parti: int,
    lunghezza: Optional[Decimal],
    larghezza: Optional[Decimal],
    altezza: Optional[Decimal],
    qta: Decimal,
    foto_paths: list[str],
) -> bool:
    stored = dict(row)
    stored_voce = stored.get("computo_voce_id")
    return (
        str(stored.get("cantiere_id")) == cantiere_id
        and (str(stored_voce) if stored_voce else None) == computo_voce_id
        and stored.get("data_misura") == data_misura
        and stored.get("descrizione") == descrizione
        and int(stored.get("parti") or 0) == parti
        and _same_decimal(stored.get("lunghezza"), lunghezza)
        and _same_decimal(stored.get("larghezza"), larghezza)
        and _same_decimal(stored.get("altezza"), altezza)
        and _same_decimal(stored.get("qta"), qta)
        and list(stored.get("foto_paths") or []) == foto_paths
    )


async def registra_misura(
    conn: asyncpg.Connection,
    tenant_id: str,
    cantiere_id: str,
    *,
    client_uuid: str,
    data_misura: date,
    qta: Decimal,
    computo_voce_id: Optional[str] = None,
    descrizione: Optional[str] = None,
    parti: int = 1,
    lunghezza: Optional[Decimal] = None,
    larghezza: Optional[Decimal] = None,
    altezza: Optional[Decimal] = None,
    foto_paths: Optional[list[str]] = None,
) -> tuple[dict, bool]:
    """Inserisce una misura oppure restituisce il retry gia registrato.

    Il conflitto non esegue UPDATE: il libretto resta append-only. Se la stessa
    chiave arriva con un payload diverso, la collisione viene resa esplicita.
    """
    paths = list(foto_paths or [])
    await _require_cantiere(conn, tenant_id, cantiere_id)
    if computo_voce_id:
        await _require_computo_voce(conn, tenant_id, cantiere_id, computo_voce_id)
    _validate_photo_paths(tenant_id, cantiere_id, paths)

    row = await conn.fetchrow(
        """
        insert into public.libretto_misure (
          tenant_id, cantiere_id, computo_voce_id, data_misura,
          rilevata_da, descrizione, parti, lunghezza, larghezza, altezza,
          qta, foto_paths, client_uuid
        ) values (
          $1::uuid, $2::uuid, $3::uuid, $4::date,
          auth.uid(), $5, $6, $7, $8, $9,
          $10, $11::text[], $12::uuid
        )
        on conflict (tenant_id, client_uuid) do nothing
        returning *
        """,
        tenant_id,
        cantiere_id,
        computo_voce_id,
        data_misura,
        descrizione,
        parti,
        lunghezza,
        larghezza,
        altezza,
        qta,
        paths,
        client_uuid,
    )
    if row:
        return _d(row), True

    existing = await conn.fetchrow(
        """
        select * from public.libretto_misure
        where tenant_id = $1::uuid and client_uuid = $2::uuid
        """,
        tenant_id,
        client_uuid,
    )
    if not existing:
        raise HTTPException(
            status_code=409,
            detail="Sincronizzazione concorrente non completata: riprova",
        )
    if not _same_payload(
        existing,
        cantiere_id=cantiere_id,
        computo_voce_id=computo_voce_id,
        data_misura=data_misura,
        descrizione=descrizione,
        parti=parti,
        lunghezza=lunghezza,
        larghezza=larghezza,
        altezza=altezza,
        qta=qta,
        foto_paths=paths,
    ):
        raise HTTPException(
            status_code=409,
            detail="client_uuid gia usato per una misura diversa",
        )
    return _d(existing), False
