"""Bridge on-demand dai lead legacy Mongo ai record tenant-scoped Postgres."""

from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

import asyncpg
from bson import ObjectId
from fastapi import HTTPException

VALID_STATUSES = {
    "nuovo",
    "qualificato",
    "sopralluogo_fissato",
    "sopralluogo_fatto",
    "preventivo_preparazione",
    "preventivo_inviato",
    "follow_up",
    "in_trattativa",
    "chiuso_vinto",
    "chiuso_perso",
}


def _json(value: Any, fallback: Any) -> str:
    return json.dumps(value if value is not None else fallback, default=str)


def _score(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return None


async def resolve_lead_id(
    conn: asyncpg.Connection,
    mongo_db: Any,
    tenant_id: str,
    lead_id: Optional[str],
) -> Optional[str]:
    """Restituisce sempre un UUID Postgres valido per il tenant corrente.

    Gli UUID vengono verificati; gli ObjectId legacy sono sincronizzati in
    ``public.leads`` in modo idempotente prima di creare computi/preventivi.
    """
    if not lead_id:
        return None

    raw_id = str(lead_id).strip()
    try:
        pg_id = str(UUID(raw_id))
    except (TypeError, ValueError):
        pg_id = None

    if pg_id:
        exists = await conn.fetchval(
            "select id from public.leads where id = $1::uuid and tenant_id = $2::uuid",
            pg_id,
            tenant_id,
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Lead non trovato nel tenant")
        return str(exists)

    if not ObjectId.is_valid(raw_id):
        raise HTTPException(status_code=400, detail="ID lead non valido")

    existing = await conn.fetchval(
        "select id from public.leads where legacy_mongo_id = $1 and tenant_id = $2::uuid",
        raw_id,
        tenant_id,
    )
    if existing:
        return str(existing)

    legacy = await mongo_db.leads.find_one({"_id": ObjectId(raw_id)})
    if not legacy:
        raise HTTPException(status_code=404, detail="Lead legacy non trovato")

    status = str(legacy.get("status") or legacy.get("stato") or "nuovo")
    if status not in VALID_STATUSES:
        status = "nuovo"
    tags = legacy.get("tags") or []
    if not isinstance(tags, list):
        tags = [str(tags)]

    row = await conn.fetchrow(
        """
        insert into public.leads (
          tenant_id, nome, email, telefono, citta, indirizzo, privacy,
          newsletter, status, owner, tags, score, config, stima, tracking,
          timeline, note_cliente, prossima_azione, ai_architect_job_id,
          legacy_mongo_id
        ) values (
          $1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::text[],
          $12, $13::jsonb, $14::jsonb, $15::jsonb, $16::jsonb, $17, $18,
          $19, $20
        )
        on conflict (legacy_mongo_id) do update set
          nome = excluded.nome,
          email = excluded.email,
          telefono = excluded.telefono,
          citta = excluded.citta,
          indirizzo = excluded.indirizzo,
          privacy = excluded.privacy,
          newsletter = excluded.newsletter,
          status = excluded.status,
          owner = excluded.owner,
          tags = excluded.tags,
          score = excluded.score,
          config = excluded.config,
          stima = excluded.stima,
          tracking = excluded.tracking,
          timeline = excluded.timeline,
          note_cliente = excluded.note_cliente,
          prossima_azione = excluded.prossima_azione,
          ai_architect_job_id = excluded.ai_architect_job_id
        where public.leads.tenant_id = excluded.tenant_id
        returning id
        """,
        tenant_id,
        legacy.get("nome") or legacy.get("name") or "Lead",
        legacy.get("email") or f"legacy-{raw_id}@invalid.local",
        legacy.get("telefono") or legacy.get("phone") or "",
        legacy.get("citta"),
        legacy.get("indirizzo"),
        bool(legacy.get("privacy", True)),
        bool(legacy.get("newsletter", False)),
        status,
        legacy.get("owner"),
        [str(tag) for tag in tags],
        _score(legacy.get("score")),
        _json(legacy.get("config"), {}),
        _json(legacy.get("stima") or legacy.get("estimate"), None),
        _json(legacy.get("tracking"), {}),
        _json(legacy.get("timeline"), []),
        legacy.get("note_cliente") or legacy.get("note"),
        legacy.get("prossima_azione"),
        str(legacy.get("ai_architect_job_id") or "") or None,
        raw_id,
    )
    if not row:
        raise HTTPException(
            status_code=409,
            detail="Il lead legacy risulta associato a un altro tenant",
        )
    return str(row["id"])
