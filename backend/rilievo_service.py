"""Primo rilievo Campo: schede e ambienti modificabili con autosalvataggio."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import asyncpg
from fastapi import HTTPException

RILIEVO_ROLES = frozenset({"owner", "admin", "staff", "operations"})


def _value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _d(row: asyncpg.Record | dict | None) -> dict | None:
    if row is None:
        return None
    out = {key: _value(value) for key, value in dict(row).items()}
    if isinstance(out.get("misure_extra"), str):
        out["misure_extra"] = json.loads(out["misure_extra"])
    return out


def _clean(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip()
    return normalized or None


def _extra_json(misure_extra: list[dict]) -> str:
    return json.dumps(misure_extra, ensure_ascii=False, default=str)


def _validate_photo_paths(
    tenant_id: str, rilievo_id: str, ambiente_client_uuid: str, paths: list[str]
) -> None:
    prefix = (
        f"{tenant_id}/rilievo-{rilievo_id}/"
        f"ambiente-{ambiente_client_uuid}/"
    )
    if any(not path.startswith(prefix) for path in paths):
        raise HTTPException(
            status_code=400,
            detail="Una o piu foto non appartengono all'ambiente selezionato",
        )


async def _require_rilievo(
    conn: asyncpg.Connection, tenant_id: str, rilievo_id: str
) -> dict:
    row = await conn.fetchrow(
        """
        select * from public.rilievi
        where tenant_id = $1::uuid and id = $2::uuid and archived_at is null
        """,
        tenant_id,
        rilievo_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Rilievo non trovato")
    return _d(row)


async def lista_rilievi(conn: asyncpg.Connection, tenant_id: str) -> list[dict]:
    rows = await conn.fetch(
        """
        select r.*,
               count(a.id)::int as n_ambienti,
               coalesce(sum(cardinality(a.foto_paths)), 0)::int as n_foto
        from public.rilievi r
        left join public.rilievo_ambienti a
          on a.tenant_id = r.tenant_id
         and a.rilievo_id = r.id
         and a.archived_at is null
        where r.tenant_id = $1::uuid and r.archived_at is null
        group by r.id
        order by r.data_rilievo desc, r.updated_at desc, r.id desc
        """,
        tenant_id,
    )
    return [_d(row) for row in rows]


async def crea_rilievo(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    client_uuid: str,
    cliente: str,
    data_rilievo: date,
    lead_id: Optional[str] = None,
    sopralluogo_legacy_id: Optional[str] = None,
    indirizzo: Optional[str] = None,
    tecnico: Optional[str] = None,
    note: Optional[str] = None,
) -> dict:
    row = await conn.fetchrow(
        """
        insert into public.rilievi (
          tenant_id, lead_id, sopralluogo_legacy_id, client_uuid, cliente,
          indirizzo, data_rilievo, tecnico, note, created_by
        ) values (
          $1::uuid, $2::uuid, $3, $4::uuid, $5,
          $6, $7::date, $8, $9, auth.uid()
        )
        on conflict (tenant_id, client_uuid) do update
          set cliente = excluded.cliente,
              lead_id = coalesce(public.rilievi.lead_id, excluded.lead_id),
              sopralluogo_legacy_id = coalesce(
                public.rilievi.sopralluogo_legacy_id,
                excluded.sopralluogo_legacy_id
              ),
              indirizzo = excluded.indirizzo,
              data_rilievo = excluded.data_rilievo,
              tecnico = excluded.tecnico,
              note = excluded.note,
              archived_at = null
        returning *
        """,
        tenant_id,
        lead_id,
        _clean(sopralluogo_legacy_id),
        client_uuid,
        cliente.strip(),
        _clean(indirizzo),
        data_rilievo,
        _clean(tecnico),
        _clean(note),
    )
    return _d(row)


async def get_rilievo(
    conn: asyncpg.Connection, tenant_id: str, rilievo_id: str
) -> dict:
    rilievo = await _require_rilievo(conn, tenant_id, rilievo_id)
    ambienti = await conn.fetch(
        """
        select * from public.rilievo_ambienti
        where tenant_id = $1::uuid and rilievo_id = $2::uuid
          and archived_at is null
        order by ordine, created_at, id
        """,
        tenant_id,
        rilievo_id,
    )
    rilievo["ambienti"] = [_d(row) for row in ambienti]
    rilievo["n_ambienti"] = len(rilievo["ambienti"])
    rilievo["n_foto"] = sum(
        len(ambiente.get("foto_paths") or []) for ambiente in rilievo["ambienti"]
    )
    return rilievo


async def aggiorna_rilievo(
    conn: asyncpg.Connection,
    tenant_id: str,
    rilievo_id: str,
    changes: dict,
) -> dict:
    await _require_rilievo(conn, tenant_id, rilievo_id)
    allowed = {
        "cliente",
        "indirizzo",
        "data_rilievo",
        "tecnico",
        "note",
        "stato",
    }
    updates = {key: value for key, value in changes.items() if key in allowed}
    if not updates:
        return await get_rilievo(conn, tenant_id, rilievo_id)
    if updates.get("stato") == "completato":
        count = await conn.fetchval(
            """
            select count(*) from public.rilievo_ambienti
            where tenant_id = $1::uuid and rilievo_id = $2::uuid
              and archived_at is null
            """,
            tenant_id,
            rilievo_id,
        )
        if not count:
            raise HTTPException(
                status_code=409,
                detail="Inserisci almeno un ambiente prima di completare il rilievo",
            )

    assignments = []
    args: list[Any] = [tenant_id, rilievo_id]
    for key, value in updates.items():
        args.append(value.strip() if isinstance(value, str) else value)
        cast = "::date" if key == "data_rilievo" else ""
        assignments.append(f"{key} = ${len(args)}{cast}")
    if "stato" in updates:
        assignments.append(
            "completed_at = now()"
            if updates["stato"] == "completato"
            else "completed_at = null"
        )
    row = await conn.fetchrow(
        f"""
        update public.rilievi set {', '.join(assignments)}
        where tenant_id = $1::uuid and id = $2::uuid and archived_at is null
        returning *
        """,
        *args,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Rilievo non trovato")
    return await get_rilievo(conn, tenant_id, rilievo_id)


async def salva_ambiente(
    conn: asyncpg.Connection,
    tenant_id: str,
    rilievo_id: str,
    ambiente_client_uuid: str,
    *,
    nome: str,
    tipologia: Optional[str] = None,
    piano: Optional[str] = None,
    ordine: int = 0,
    lunghezza: Optional[Decimal] = None,
    larghezza: Optional[Decimal] = None,
    altezza: Optional[Decimal] = None,
    superficie: Optional[Decimal] = None,
    misure_extra: Optional[list[dict]] = None,
    note: Optional[str] = None,
    foto_paths: Optional[list[str]] = None,
) -> dict:
    await _require_rilievo(conn, tenant_id, rilievo_id)
    paths = list(foto_paths or [])
    _validate_photo_paths(tenant_id, rilievo_id, ambiente_client_uuid, paths)
    if superficie is None and lunghezza is not None and larghezza is not None:
        superficie = (lunghezza * larghezza).quantize(Decimal("0.001"))
    row = await conn.fetchrow(
        """
        insert into public.rilievo_ambienti (
          tenant_id, rilievo_id, client_uuid, nome, tipologia, piano, ordine,
          lunghezza, larghezza, altezza, superficie, misure_extra, note,
          foto_paths
        ) values (
          $1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7,
          $8, $9, $10, $11, $12::jsonb, $13, $14::text[]
        )
        on conflict (tenant_id, rilievo_id, client_uuid) do update
          set nome = excluded.nome,
              tipologia = excluded.tipologia,
              piano = excluded.piano,
              ordine = excluded.ordine,
              lunghezza = excluded.lunghezza,
              larghezza = excluded.larghezza,
              altezza = excluded.altezza,
              superficie = excluded.superficie,
              misure_extra = excluded.misure_extra,
              note = excluded.note,
              foto_paths = excluded.foto_paths,
              archived_at = null
        returning *
        """,
        tenant_id,
        rilievo_id,
        ambiente_client_uuid,
        nome.strip(),
        _clean(tipologia),
        _clean(piano),
        ordine,
        lunghezza,
        larghezza,
        altezza,
        superficie,
        _extra_json(misure_extra or []),
        _clean(note),
        paths,
    )
    return _d(row)


async def archivia_ambiente(
    conn: asyncpg.Connection,
    tenant_id: str,
    rilievo_id: str,
    ambiente_client_uuid: str,
) -> dict:
    await _require_rilievo(conn, tenant_id, rilievo_id)
    row = await conn.fetchrow(
        """
        update public.rilievo_ambienti set archived_at = now()
        where tenant_id = $1::uuid and rilievo_id = $2::uuid
          and client_uuid = $3::uuid and archived_at is null
        returning id, client_uuid
        """,
        tenant_id,
        rilievo_id,
        ambiente_client_uuid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ambiente non trovato")
    return {"ok": True, "id": str(row["id"]), "client_uuid": str(row["client_uuid"])}
