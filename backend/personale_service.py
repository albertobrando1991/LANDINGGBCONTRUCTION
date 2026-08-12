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
    client_id = data.get("client_id")
    row = await conn.fetchrow(
        """
        insert into public.cantiere_personale (
          id, tenant_id, cantiere_id, personale_id, ruolo_in_cantiere,
          data_da, data_a, stato, note
        ) values (coalesce($1::uuid, gen_random_uuid()), $2::uuid, $3::uuid, $4::uuid, $5, $6, $7, $8, $9)
        on conflict (id) do update set
          ruolo_in_cantiere = excluded.ruolo_in_cantiere,
          data_da = excluded.data_da,
          data_a = excluded.data_a,
          stato = excluded.stato,
          note = excluded.note
        where cantiere_personale.tenant_id = excluded.tenant_id
        returning *
        """,
        client_id,
        tenant_id,
        data["cantiere_id"],
        data["personale_id"],
        _clean(data.get("ruolo_in_cantiere")),
        data["data_da"],
        data.get("data_a"),
        data.get("stato", "assegnato"),
        _clean(data.get("note")),
    )
    if not row:
        raise HTTPException(
            status_code=409, detail="Identificativo assegnazione gia in uso"
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


def _normalize_presenza(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    tipo = normalized.get("tipo_giornata", "intera")
    ore = normalized.get("ore_lavorate")
    if ore is None and tipo == "intera":
        normalized["ore_lavorate"] = 8
    elif ore is None and tipo == "mezza":
        normalized["ore_lavorate"] = 4
    elif tipo == "ore" and (ore is None or float(ore) <= 0):
        raise HTTPException(
            status_code=400,
            detail="Indica le ore lavorate per una presenza a ore",
        )
    ingresso = normalized.get("ora_ingresso")
    uscita = normalized.get("ora_uscita")
    if ingresso is not None and uscita is not None and uscita <= ingresso:
        raise HTTPException(
            status_code=400,
            detail="L'ora di uscita deve essere successiva all'ingresso",
        )
    if "note" in normalized:
        normalized["note"] = _clean(normalized.get("note"))
    return normalized


async def get_presenze(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    data: date,
    cantiere_id: str | None = None,
) -> dict:
    if cantiere_id:
        await economics_service._require_cantiere(conn, tenant_id, cantiere_id)
    rows = await conn.fetch(
        """
        select
          pr.*,
          p.nome as personale_nome,
          p.tipo as personale_tipo,
          p.ruolo as personale_ruolo,
          p.telefono,
          c.cliente as cantiere_cliente,
          c.legacy_mongo_id as cantiere_legacy_id
        from public.presenze_cantiere pr
        join public.personale p
          on p.tenant_id = pr.tenant_id and p.id = pr.personale_id
        join public.cantieri c
          on c.tenant_id = pr.tenant_id and c.id = pr.cantiere_id
        where pr.tenant_id = $1::uuid
          and pr.data = $2::date
          and ($3::uuid is null or pr.cantiere_id = $3::uuid)
        order by c.cliente, p.tipo, p.nome
        """,
        tenant_id,
        data,
        cantiere_id,
    )
    items = [economics_service._dict(row) for row in rows]
    return {
        "data": data.isoformat(),
        "righe": items,
        "totale_unita": sum(int(item.get("unita_presenti") or 0) for item in items),
        "totale_interni": sum(
            int(item.get("unita_presenti") or 0)
            for item in items
            if item.get("personale_tipo") == "interno"
        ),
        "totale_subappaltatori": sum(
            int(item.get("unita_presenti") or 0)
            for item in items
            if item.get("personale_tipo") == "subappaltatore"
        ),
        "cantieri_attivi": len({item.get("cantiere_id") for item in items}),
    }


async def crea_presenza(
    conn: asyncpg.Connection, tenant_id: str, data: dict[str, Any]
) -> dict:
    await economics_service._require_cantiere(conn, tenant_id, data["cantiere_id"])
    await economics_service._require_optional_reference(
        conn, tenant_id, "personale", data["personale_id"], "Persona"
    )
    normalized = _normalize_presenza(data)
    client_id = data.get("client_id")
    try:
        row = await conn.fetchrow(
            """
            insert into public.presenze_cantiere (
              id, tenant_id, cantiere_id, personale_id, data, unita_presenti,
              tipo_giornata, ore_lavorate, ora_ingresso, ora_uscita, note
            ) values (coalesce($1::uuid, gen_random_uuid()), $2::uuid, $3::uuid, $4::uuid, $5, $6, $7, $8, $9, $10, $11)
            on conflict (id) do update set
              unita_presenti = excluded.unita_presenti,
              tipo_giornata = excluded.tipo_giornata,
              ore_lavorate = excluded.ore_lavorate,
              ora_ingresso = excluded.ora_ingresso,
              ora_uscita = excluded.ora_uscita,
              note = excluded.note
            where presenze_cantiere.tenant_id = excluded.tenant_id
            returning *
            """,
            client_id,
            tenant_id,
            normalized["cantiere_id"],
            normalized["personale_id"],
            normalized.get("data", date.today()),
            normalized.get("unita_presenti", 1),
            normalized.get("tipo_giornata", "intera"),
            normalized.get("ore_lavorate"),
            normalized.get("ora_ingresso"),
            normalized.get("ora_uscita"),
            normalized.get("note"),
        )
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            status_code=409,
            detail="Presenza gia registrata per questa persona e giornata",
        ) from exc
    if not row:
        raise HTTPException(
            status_code=409, detail="Identificativo presenza gia in uso"
        )
    return economics_service._dict(row)


async def aggiorna_presenza(
    conn: asyncpg.Connection,
    tenant_id: str,
    presenza_id: str,
    data: dict[str, Any],
) -> dict:
    current = await conn.fetchrow(
        """
        select * from public.presenze_cantiere
        where tenant_id = $1::uuid and id = $2::uuid
        """,
        tenant_id,
        presenza_id,
    )
    if not current:
        raise HTTPException(status_code=404, detail="Presenza non trovata")
    merged = {
        "tipo_giornata": current["tipo_giornata"],
        "ore_lavorate": current["ore_lavorate"],
        "ora_ingresso": current["ora_ingresso"],
        "ora_uscita": current["ora_uscita"],
        **data,
    }
    if "tipo_giornata" in data and "ore_lavorate" not in data:
        merged["ore_lavorate"] = None
    normalized = _normalize_presenza(merged)
    changed = {key: value for key, value in normalized.items() if key in data}
    if "tipo_giornata" in data and "ore_lavorate" not in data:
        changed["ore_lavorate"] = normalized.get("ore_lavorate")
    return await economics_service._patch_row(
        conn,
        tenant_id,
        "presenze_cantiere",
        presenza_id,
        changed,
        {
            "data",
            "unita_presenti",
            "tipo_giornata",
            "ore_lavorate",
            "ora_ingresso",
            "ora_uscita",
            "note",
        },
        "Presenza",
    )


async def elimina_presenza(
    conn: asyncpg.Connection, tenant_id: str, presenza_id: str
) -> dict:
    row = await conn.fetchrow(
        """
        delete from public.presenze_cantiere
        where tenant_id = $1::uuid and id = $2::uuid
        returning id
        """,
        tenant_id,
        presenza_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Presenza non trovata")
    return {"ok": True, "deleted": str(row["id"])}
