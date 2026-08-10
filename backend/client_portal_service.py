"""Portale cliente EdilOS: onboarding, condivisioni e viste RLS dedicate."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from system_jobs.client_invites import find_or_invite_user

INTERNAL_ROLES = frozenset({"owner", "admin", "staff", "operations"})
PORTAL_ADMIN_ROLES = frozenset({"owner", "admin"})


def _json(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    return value


def _row(row: asyncpg.Record | dict | None) -> dict | None:
    return _json(dict(row)) if row is not None else None


def _rows(rows) -> list[dict]:
    return [_row(row) for row in rows]


async def _require_cantiere(
    conn: asyncpg.Connection, tenant_id: str, cantiere_id: str
) -> None:
    exists = await conn.fetchval(
        """
        select exists(
          select 1 from public.cantieri
          where tenant_id = $1::uuid and id = $2::uuid
        )
        """,
        tenant_id,
        cantiere_id,
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Cantiere non trovato")


async def get_portal_dashboard(conn: asyncpg.Connection, tenant_id: str) -> dict:
    cantieri = await conn.fetch(
        """
        select * from public.portale_cantieri
        where tenant_id = $1::uuid
        order by case stato when 'attivo' then 0 when 'in_pausa' then 1 else 2 end,
                 nome_cantiere
        """,
        tenant_id,
    )
    sal = await conn.fetch(
        """
        select * from public.portale_sal_approvati
        where tenant_id = $1::uuid
        order by periodo_a desc, numero desc
        """,
        tenant_id,
    )
    varianti = await conn.fetch(
        """
        select * from public.portale_varianti
        where tenant_id = $1::uuid
        order by updated_at desc, variante_id
        """,
        tenant_id,
    )
    righe = await conn.fetch(
        """
        select * from public.portale_variante_righe
        where tenant_id = $1::uuid
        order by variante_id, ordine,
                 coalesce(descrizione_variante, descrizione_base)
        """,
        tenant_id,
    )
    assets = await conn.fetch(
        """
        select id, tenant_id, cantiere_id, tipo, bucket, storage_path,
               titolo, descrizione, created_at
        from public.cantiere_condivisioni
        where tenant_id = $1::uuid
        order by created_at desc
        """,
        tenant_id,
    )
    pagamenti = await conn.fetch(
        """
        select * from public.portale_pagamenti_cliente
        where tenant_id = $1::uuid
        order by data_prevista, numero_rata, incasso_id
        """,
        tenant_id,
    )
    documenti_economici = await conn.fetch(
        """
        select * from public.portale_documenti_economici
        where tenant_id = $1::uuid
        order by created_at desc, documento_id
        """,
        tenant_id,
    )

    righe_by_variante: dict[str, list[dict]] = {}
    for item in _rows(righe):
        righe_by_variante.setdefault(item["variante_id"], []).append(item)
    variante_rows = _rows(varianti)
    for item in variante_rows:
        item["righe"] = righe_by_variante.get(item["variante_id"], [])

    return {
        "cantieri": _rows(cantieri),
        "sal": _rows(sal),
        "varianti": variante_rows,
        "assets": _rows(assets),
        "pagamenti": _rows(pagamenti),
        "documenti_economici": _rows(documenti_economici),
    }


async def approva_variante(
    conn: asyncpg.Connection,
    tenant_id: str,
    cantiere_id: str,
    variante_id: str,
    user_id: str,
    *,
    ip: str,
    user_agent: str | None,
) -> dict:
    row = await conn.fetchrow(
        """
        select *
        from private.approva_variante_cliente(
          $1::uuid, $2::uuid, $3::uuid, $4::inet, $5
        )
        """,
        tenant_id,
        cantiere_id,
        variante_id,
        ip,
        (user_agent or "")[:500] or None,
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Variante confermata non disponibile per questo cantiere",
        )
    result = _row(row)
    if result["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Identita cliente non coerente")
    return result


async def invita_cliente(
    conn: asyncpg.Connection,
    tenant_id: str,
    cantiere_id: str,
    *,
    email: str,
    nome: str | None,
) -> dict:
    await _require_cantiere(conn, tenant_id, cantiere_id)
    normalized = email.strip().lower()
    user, invited = await asyncio.to_thread(
        find_or_invite_user, normalized, nome, context="cantiere"
    )
    user_id = str(getattr(user, "id", "") or "")
    if not user_id:
        raise HTTPException(status_code=502, detail="Invito Supabase non completato")

    existing_role = await conn.fetchval(
        """
        select role from public.tenant_members
        where tenant_id = $1::uuid and user_id = $2::uuid
        """,
        tenant_id,
        user_id,
    )
    if existing_role and str(existing_role) != "client":
        raise HTTPException(
            status_code=409,
            detail="L'email appartiene gia a un membro interno del tenant",
        )

    await conn.execute(
        """
        insert into public.tenant_members (tenant_id, user_id, role, nome)
        values ($1::uuid, $2::uuid, 'client', $3)
        on conflict (tenant_id, user_id) do update
          set nome = coalesce(excluded.nome, public.tenant_members.nome)
        """,
        tenant_id,
        user_id,
        (nome or "").strip() or None,
    )
    row = await conn.fetchrow(
        """
        insert into public.cantiere_clienti (
          tenant_id, cantiere_id, user_id, email, nome, attivo
        ) values ($1::uuid, $2::uuid, $3::uuid, $4, $5, true)
        on conflict (tenant_id, cantiere_id, user_id) do update
          set email = excluded.email,
              nome = coalesce(excluded.nome, public.cantiere_clienti.nome),
              attivo = true
        returning *
        """,
        tenant_id,
        cantiere_id,
        user_id,
        normalized,
        (nome or "").strip() or None,
    )
    result = _row(row)
    result["invited"] = invited
    return result


async def get_cantiere_portal_admin(
    conn: asyncpg.Connection, tenant_id: str, cantiere_id: str
) -> dict:
    await _require_cantiere(conn, tenant_id, cantiere_id)
    clients = await conn.fetch(
        """
        select tenant_id, cantiere_id, user_id, email, nome, attivo,
               created_at, updated_at
        from public.cantiere_clienti
        where tenant_id = $1::uuid and cantiere_id = $2::uuid
        order by attivo desc, created_at desc
        """,
        tenant_id,
        cantiere_id,
    )
    shares = await conn.fetch(
        """
        select id, tipo, bucket, storage_path, titolo, descrizione, created_at
        from public.cantiere_condivisioni
        where tenant_id = $1::uuid and cantiere_id = $2::uuid
        order by created_at desc
        """,
        tenant_id,
        cantiere_id,
    )
    photos = await conn.fetch(
        """
        select distinct photo_path
        from public.libretto_misure lm,
             lateral unnest(lm.foto_paths) as photo_path
        where lm.tenant_id = $1::uuid and lm.cantiere_id = $2::uuid
        order by photo_path
        """,
        tenant_id,
        cantiere_id,
    )
    return {
        "clients": _rows(clients),
        "shares": _rows(shares),
        "photo_candidates": [row["photo_path"] for row in photos],
    }


async def disattiva_cliente(
    conn: asyncpg.Connection,
    tenant_id: str,
    cantiere_id: str,
    user_id: str,
) -> dict:
    row = await conn.fetchrow(
        """
        update public.cantiere_clienti
        set attivo = false
        where tenant_id = $1::uuid
          and cantiere_id = $2::uuid
          and user_id = $3::uuid
        returning *
        """,
        tenant_id,
        cantiere_id,
        user_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Accesso cliente non trovato")
    return _row(row)


async def condividi_asset(
    conn: asyncpg.Connection,
    tenant_id: str,
    cantiere_id: str,
    *,
    tipo: str,
    bucket: str,
    storage_path: str,
    titolo: str,
    descrizione: str | None,
) -> dict:
    await _require_cantiere(conn, tenant_id, cantiere_id)
    expected_bucket = "foto-cantiere" if tipo == "foto" else "documenti"
    if bucket != expected_bucket:
        raise HTTPException(status_code=400, detail="Bucket non coerente con il tipo")
    prefix = f"{tenant_id}/cantiere-{cantiere_id}/"
    if not storage_path.startswith(prefix):
        raise HTTPException(status_code=400, detail="Percorso asset non autorizzato")
    exists = await conn.fetchval(
        """
        select exists(
          select 1 from storage.objects
          where bucket_id = $1 and name = $2
        )
        """,
        bucket,
        storage_path,
    )
    if not exists:
        raise HTTPException(status_code=404, detail="File Storage non trovato")
    row = await conn.fetchrow(
        """
        insert into public.cantiere_condivisioni (
          tenant_id, cantiere_id, tipo, bucket, storage_path, titolo, descrizione
        ) values ($1::uuid, $2::uuid, $3, $4, $5, $6, $7)
        on conflict (tenant_id, cantiere_id, bucket, storage_path) do update
          set titolo = excluded.titolo,
              descrizione = excluded.descrizione
        returning *
        """,
        tenant_id,
        cantiere_id,
        tipo,
        bucket,
        storage_path,
        titolo.strip(),
        (descrizione or "").strip() or None,
    )
    return _row(row)


async def revoca_condivisione(
    conn: asyncpg.Connection, tenant_id: str, cantiere_id: str, share_id: str
) -> dict:
    row = await conn.fetchrow(
        """
        delete from public.cantiere_condivisioni
        where tenant_id = $1::uuid and cantiere_id = $2::uuid and id = $3::uuid
        returning *
        """,
        tenant_id,
        cantiere_id,
        share_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Condivisione non trovata")
    return _row(row)
