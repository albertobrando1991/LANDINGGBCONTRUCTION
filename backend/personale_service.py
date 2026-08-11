"""Anagrafica personale e assegnazioni tenant-scoped ai cantieri."""
from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg
from fastapi import HTTPException

import economics_service


PERSONALE_READ_ROLES = {"owner", "admin", "staff", "operations"}
PERSONALE_WRITE_ROLES = {"owner", "admin"}


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip() or None
    return value


def _validate_period(data_da: date, data_a: date | None) -> None:
    if data_a is not None and data_a < data_da:
        raise HTTPException(
            status_code=400,
            detail="La data finale non puo precedere la data iniziale",
        )


async def get_personale(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    tipo: str | None = None,
    attivo: bool | None = None,
) -> list[dict]:
    rows = await conn.fetch(
        """
        select p.*, f.ragione_sociale as fornitore
        from public.personale p
        left join public.fornitori f
          on f.tenant_id = p.tenant_id and f.id = p.fornitore_id
        where p.tenant_id = $1::uuid
          and ($2::text is null or p.tipo = $2::text)
          and ($3::boolean is null or p.attivo = $3::boolean)
        order by p.attivo desc, p.tipo, p.nome
        """,
        tenant_id,
        tipo,
        attivo,
    )
    return [economics_service._dict(row) for row in rows]


async def crea_personale(
    conn: asyncpg.Connection, tenant_id: str, data: dict[str, Any]
) -> dict:
    await economics_service._require_optional_reference(
        conn,
        tenant_id,
        "fornitori",
        data.get("fornitore_id"),
        "Fornitore",
    )
    row = await conn.fetchrow(
        """
        insert into public.personale (
          tenant_id, tipo, nome, ruolo, fornitore_id, telefono, email,
          costo_giornaliero, costo_orario, attivo, note
        ) values (
          $1::uuid, $2, $3, $4, $5::uuid, $6, $7, $8, $9, $10, $11
        ) returning *
        """,
        tenant_id,
        data["tipo"],
        data["nome"].strip(),
        _clean(data.get("ruolo")),
        data.get("fornitore_id"),
        _clean(data.get("telefono")),
        _clean(data.get("email")),
        data.get("costo_giornaliero"),
        data.get("costo_orario"),
        data.get("attivo", True),
        _clean(data.get("note")),
    )
    return economics_service._dict(row)


async def aggiorna_personale(
    conn: asyncpg.Connection,
    tenant_id: str,
    personale_id: str,
    data: dict[str, Any],
) -> dict:
    if "fornitore_id" in data:
        await economics_service._require_optional_reference(
            conn,
            tenant_id,
            "fornitori",
            data.get("fornitore_id"),
            "Fornitore",
        )
    normalized = {
        key: (_clean(value) if key in {"ruolo", "telefono", "email", "note"} else value)
        for key, value in data.items()
    }
    if normalized.get("nome"):
        normalized["nome"] = normalized["nome"].strip()
    return await economics_service._patch_row(
        conn,
        tenant_id,
        "personale",
        personale_id,
        normalized,
        {
            "tipo",
            "nome",
            "ruolo",
            "fornitore_id",
            "telefono",
            "email",
            "costo_giornaliero",
            "costo_orario",
            "attivo",
            "note",
        },
        "Persona",
    )


async def get_assegnazioni(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    cantiere_id: str | None = None,
    personale_id: str | None = None,
    stato: str | None = None,
) -> list[dict]:
    if cantiere_id:
        await economics_service._require_cantiere(conn, tenant_id, cantiere_id)
    rows = await conn.fetch(
        """
        select
          cp.*,
          p.tipo as personale_tipo,
          p.nome as personale_nome,
          p.ruolo as personale_ruolo,
          p.telefono,
          p.email,
          p.costo_giornaliero,
          p.costo_orario,
          p.fornitore_id,
          f.ragione_sociale as fornitore,
          c.cliente as cantiere_cliente,
          c.legacy_mongo_id as cantiere_legacy_id
        from public.cantiere_personale cp
        join public.personale p
          on p.tenant_id = cp.tenant_id and p.id = cp.personale_id
        join public.cantieri c
          on c.tenant_id = cp.tenant_id and c.id = cp.cantiere_id
        left join public.fornitori f
          on f.tenant_id = p.tenant_id and f.id = p.fornitore_id
        where cp.tenant_id = $1::uuid
          and ($2::uuid is null or cp.cantiere_id = $2::uuid)
          and ($3::uuid is null or cp.personale_id = $3::uuid)
          and ($4::text is null or cp.stato = $4::text)
        order by
          (cp.stato = 'in_corso') desc,
          (cp.stato = 'assegnato') desc,
          cp.data_da desc,
          p.nome
        """,
        tenant_id,
        cantiere_id,
        personale_id,
        stato,
    )
    return [economics_service._dict(row) for row in rows]


async def crea_assegnazione(
    conn: asyncpg.Connection, tenant_id: str, data: dict[str, Any]
) -> dict:
    await economics_service._require_cantiere(
        conn, tenant_id, data["cantiere_id"]
    )
    await economics_service._require_optional_reference(
        conn,
        tenant_id,
        "personale",
        data["personale_id"],
        "Persona",
    )
    _validate_period(data["data_da"], data.get("data_a"))
    row = await conn.fetchrow(
        """
        insert into public.cantiere_personale (
          tenant_id, cantiere_id, personale_id, ruolo_in_cantiere,
          data_da, data_a, stato, note
        ) values ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8)
        returning *
        """,
        tenant_id,
        data["cantiere_id"],
        data["personale_id"],
        _clean(data.get("ruolo_in_cantiere")),
        data["data_da"],
        data.get("data_a"),
        data.get("stato", "assegnato"),
        _clean(data.get("note")),
    )
    return economics_service._dict(row)


async def aggiorna_assegnazione(
    conn: asyncpg.Connection,
    tenant_id: str,
    assegnazione_id: str,
    data: dict[str, Any],
) -> dict:
    current = await conn.fetchrow(
        """
        select cantiere_id, personale_id, data_da, data_a
        from public.cantiere_personale
        where tenant_id = $1::uuid and id = $2::uuid
        """,
        tenant_id,
        assegnazione_id,
    )
    if not current:
        raise HTTPException(status_code=404, detail="Assegnazione non trovata")
    cantiere_id = data.get("cantiere_id", current["cantiere_id"])
    personale_id = data.get("personale_id", current["personale_id"])
    if "cantiere_id" in data:
        await economics_service._require_cantiere(conn, tenant_id, cantiere_id)
    if "personale_id" in data:
        await economics_service._require_optional_reference(
            conn,
            tenant_id,
            "personale",
            personale_id,
            "Persona",
        )
    _validate_period(
        data.get("data_da", current["data_da"]),
        data.get("data_a", current["data_a"]),
    )
    normalized = {
        key: (_clean(value) if key in {"ruolo_in_cantiere", "note"} else value)
        for key, value in data.items()
    }
    return await economics_service._patch_row(
        conn,
        tenant_id,
        "cantiere_personale",
        assegnazione_id,
        normalized,
        {
            "cantiere_id",
            "personale_id",
            "ruolo_in_cantiere",
            "data_da",
            "data_a",
            "stato",
            "note",
        },
        "Assegnazione",
    )
