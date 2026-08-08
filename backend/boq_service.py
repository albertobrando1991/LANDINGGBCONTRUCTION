"""Computo metrico (BOQ): CRUD voci con snapshot prezzi e conferma con validazione AI."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import asyncpg
from fastapi import HTTPException


LOCKED_COMPUTO_STATES = {"confermato", "archiviato"}
PREVENTIVO_TRANSITIONS = {
    "inviato": {"accettato", "rifiutato", "scaduto"},
}
LEAD_STATUS_BY_PREVENTIVO = {
    "inviato": "preventivo_inviato",
    "accettato": "chiuso_vinto",
    "rifiutato": "chiuso_perso",
    "scaduto": "chiuso_perso",
}
LEAD_NEXT_ACTION_BY_PREVENTIVO = {
    "inviato": "Effettuare il follow-up del preventivo entro 5 giorni",
    "accettato": "Pianificare avvio lavori e documentazione contrattuale",
    "rifiutato": "Registrare il motivo del rifiuto e valutare un follow-up",
    "scaduto": "Contattare il cliente e valutare il rinnovo del preventivo",
}


def _d(row: asyncpg.Record | None) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for k, v in list(out.items()):
        if isinstance(v, UUID):
            out[k] = str(v)
        elif isinstance(v, Decimal):
            out[k] = float(v)
    return out


def _normalizza_codice(value: Any) -> str:
    """Normalizza i codici tariffa senza introdurre matching descrittivi incerti."""
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def _abbina_voce_acca(item: dict, candidates_by_code: dict[str, list[dict]]) -> dict | None:
    """Accetta soltanto un match univoco per codice e unita di misura."""
    raw_code = str(item.get("codice") or "").strip()
    if not raw_code or raw_code.upper().startswith("ACCA-") or not item.get("coerente"):
        return None
    matches = [
        candidate
        for candidate in candidates_by_code.get(_normalizza_codice(raw_code), [])
        if str(candidate.get("um") or "").lower() == str(item.get("um") or "").lower()
    ]
    return matches[0] if len(matches) == 1 else None


async def _ensure_cliente_for_lead(
    conn: asyncpg.Connection, tenant_id: str, lead: asyncpg.Record | dict
) -> str:
    """Crea o riusa l'anagrafica cliente collegata al lead, nella transazione corrente."""
    if lead.get("cliente_id"):
        return str(lead["cliente_id"])

    email = str(lead.get("email") or "").strip().lower()
    lock_identity = email or str(lead["id"])
    await conn.execute(
        "select pg_advisory_xact_lock(hashtextextended($1, 0))",
        f"cliente:{tenant_id}:{lock_identity}",
    )
    refreshed = await conn.fetchrow(
        """
        select id, cliente_id, nome, email, telefono, citta, indirizzo
        from public.leads
        where id = $1::uuid and tenant_id = $2::uuid
        """,
        lead["id"],
        tenant_id,
    )
    if not refreshed:
        raise HTTPException(status_code=404, detail="Cliente/lead non trovato")
    if refreshed["cliente_id"]:
        return str(refreshed["cliente_id"])

    cliente_id = None
    if email and not email.endswith("@invalid.local"):
        cliente_id = await conn.fetchval(
            """
            select id from public.clienti
            where tenant_id = $1::uuid and lower(email) = $2
            order by created_at, id
            limit 1
            """,
            tenant_id,
            email,
        )
    if not cliente_id:
        cliente_id = await conn.fetchval(
            """
            insert into public.clienti (
              tenant_id, nome, email, telefono, citta, indirizzo
            ) values ($1::uuid, $2, $3, $4, $5, $6)
            returning id
            """,
            tenant_id,
            refreshed["nome"],
            refreshed["email"],
            refreshed["telefono"],
            refreshed["citta"],
            refreshed["indirizzo"],
        )
    await conn.execute(
        """
        update public.leads set cliente_id = $1::uuid
        where id = $2::uuid and tenant_id = $3::uuid and cliente_id is null
        """,
        cliente_id,
        refreshed["id"],
        tenant_id,
    )
    return str(cliente_id)


async def _resolve_import_context(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    lead_id: Optional[str],
    cantiere_id: Optional[str],
    prezzario_id: Optional[str],
) -> dict:
    lead = None
    if lead_id:
        lead = await conn.fetchrow(
            """
            select id, cliente_id, nome, email, telefono, citta, indirizzo
            from public.leads
            where id = $1::uuid and tenant_id = $2::uuid
            """,
            lead_id,
            tenant_id,
        )
        if not lead:
            raise HTTPException(status_code=404, detail="Cliente/lead non trovato")

    cantiere = None
    if cantiere_id:
        cantiere = await conn.fetchrow(
            """
            select id, lead_id, cliente_id from public.cantieri
            where id = $1::uuid and tenant_id = $2::uuid
            """,
            cantiere_id,
            tenant_id,
        )
        if not cantiere:
            raise HTTPException(status_code=404, detail="Cantiere non trovato")
        if lead and cantiere["lead_id"] and str(cantiere["lead_id"]) != str(lead["id"]):
            raise HTTPException(
                status_code=409,
                detail="Il cantiere selezionato appartiene a un altro cliente",
            )
        if not lead_id and cantiere["lead_id"]:
            lead_id = str(cantiere["lead_id"])

    if lead_id and not lead:
        lead = await conn.fetchrow(
            """
            select id, cliente_id, nome, email, telefono, citta, indirizzo
            from public.leads
            where id = $1::uuid and tenant_id = $2::uuid
            """,
            lead_id,
            tenant_id,
        )
        if not lead:
            raise HTTPException(status_code=404, detail="Cliente/lead non trovato")

    if prezzario_id:
        exists = await conn.fetchval(
            """
            select exists(
              select 1 from public.prezzari
              where id = $1::uuid and tenant_id = $2::uuid
            )
            """,
            prezzario_id,
            tenant_id,
        )
        if not exists:
            raise HTTPException(status_code=404, detail="Prezzario non trovato")

    cliente_id = None
    if cantiere and cantiere["cliente_id"]:
        cliente_id = str(cantiere["cliente_id"])
        if lead and lead["cliente_id"] and str(lead["cliente_id"]) != cliente_id:
            raise HTTPException(
                status_code=409,
                detail="Lead e cantiere risultano associati a clienti diversi",
            )
        if lead and not lead["cliente_id"]:
            await conn.execute(
                """
                update public.leads set cliente_id = $1::uuid
                where id = $2::uuid and tenant_id = $3::uuid
                  and cliente_id is null
                """,
                cliente_id,
                lead["id"],
                tenant_id,
            )
    elif lead:
        cliente_id = await _ensure_cliente_for_lead(conn, tenant_id, lead)
    return {
        "lead_id": lead_id,
        "cantiere_id": cantiere_id,
        "prezzario_id": prezzario_id,
        "cliente_id": cliente_id,
    }


async def _assert_computo_editabile(
    conn: asyncpg.Connection, tenant_id: str, computo_id: str
) -> None:
    stato = await conn.fetchval(
        """
        select stato from public.computi
        where id = $1::uuid and tenant_id = $2::uuid
        for update
        """,
        computo_id,
        tenant_id,
    )
    if stato is None:
        raise HTTPException(status_code=404, detail="Computo non trovato")
    if stato in LOCKED_COMPUTO_STATES:
        raise HTTPException(
            status_code=409,
            detail="Computo confermato: crea una variante per modificarlo",
        )


async def _voce_computo_editabile(
    conn: asyncpg.Connection, tenant_id: str, voce_id: str
) -> str:
    row = await conn.fetchrow(
        """
        select v.computo_id, c.stato
        from public.computo_voci v
        join public.computi c
          on c.id = v.computo_id and c.tenant_id = v.tenant_id
        where v.id = $1::uuid and v.tenant_id = $2::uuid
        for update of c
        """,
        voce_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Voce di computo non trovata")
    if row["stato"] in LOCKED_COMPUTO_STATES:
        raise HTTPException(
            status_code=409,
            detail="Computo confermato: crea una variante per modificarlo",
        )
    return str(row["computo_id"])


async def crea_computo(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    lead_id: Optional[str] = None,
    cantiere_id: Optional[str] = None,
    prezzario_id: Optional[str] = None,
    tipo: str = "estimativo",
) -> dict:
    if not prezzario_id:
        prezzario_id = await conn.fetchval(
            "select id from public.prezzari where tenant_id = $1::uuid and is_default limit 1",
            tenant_id,
        )
    row = await conn.fetchrow(
        """
        insert into public.computi (tenant_id, lead_id, cantiere_id, prezzario_id, tipo, stato)
        values ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, 'bozza')
        returning *
        """,
        tenant_id,
        lead_id,
        cantiere_id,
        prezzario_id,
        tipo,
    )
    return _d(row)


async def aggiungi_voce(
    conn: asyncpg.Connection,
    tenant_id: str,
    computo_id: str,
    prezzario_voce_id: str,
    qta: float,
) -> dict:
    """SNAPSHOT: copia descrizione, um, categorie e prezzo dalla voce di prezzario."""
    await _assert_computo_editabile(conn, tenant_id, computo_id)

    voce = await conn.fetchrow(
        """
        select * from public.prezzario_voci
        where id = $1::uuid and tenant_id = $2::uuid and attiva = true
        """,
        prezzario_voce_id,
        tenant_id,
    )
    if not voce:
        raise HTTPException(status_code=404, detail="Voce di prezzario non trovata")

    ordine = await conn.fetchval(
        "select coalesce(max(ordine), 0) + 10 from public.computo_voci where computo_id = $1::uuid",
        computo_id,
    )
    row = await conn.fetchrow(
        """
        insert into public.computo_voci (
          tenant_id, computo_id, origine_voce_id, ordine,
          super_categoria, categoria, sub_categoria, descrizione, um, tipo,
          qta, prezzo_unitario, generata_da_ai, validata_umano
        ) values (
          $1::uuid, $2::uuid, $3::uuid, $4,
          $5, $6, $7, $8, $9, $10,
          $11, $12, false, true
        ) returning *
        """,
        tenant_id,
        computo_id,
        prezzario_voce_id,
        ordine,
        voce["super_categoria"],
        voce["categoria"],
        voce["sub_categoria"],
        voce["descrizione"],
        voce["um"],
        voce["tipo"],
        qta,
        float(voce["prezzo_unitario"]),
    )
    result = _d(row)
    await sincronizza_preventivo_bozza(conn, tenant_id, computo_id)
    return result


async def aggiorna_voce(
    conn: asyncpg.Connection, tenant_id: str, voce_id: str, **campi
) -> dict:
    computo_id = await _voce_computo_editabile(conn, tenant_id, voce_id)
    allowed = {"qta", "prezzo_unitario", "descrizione", "ordine", "validata_umano"}
    sets = []
    args: list[Any] = []
    for k, v in campi.items():
        if k not in allowed or v is None:
            continue
        args.append(v)
        sets.append(f"{k} = ${len(args)}")
    if not sets:
        raise HTTPException(status_code=400, detail="Nessun campo da aggiornare")
    args.extend([voce_id, tenant_id, computo_id])
    row = await conn.fetchrow(
        f"""
        update public.computo_voci
        set {', '.join(sets)}
        where id = ${len(args)-2}::uuid
          and tenant_id = ${len(args)-1}::uuid
          and computo_id = ${len(args)}::uuid
        returning *
        """,
        *args,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Voce di computo non trovata")
    result = _d(row)
    await sincronizza_preventivo_bozza(conn, tenant_id, computo_id)
    return result


async def rimuovi_voce(
    conn: asyncpg.Connection, tenant_id: str, voce_id: str
) -> dict:
    computo_id = await _voce_computo_editabile(conn, tenant_id, voce_id)
    row = await conn.fetchrow(
        """
        delete from public.computo_voci
        where id = $1::uuid and tenant_id = $2::uuid and computo_id = $3::uuid
        returning id, computo_id
        """,
        voce_id,
        tenant_id,
        computo_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Voce di computo non trovata")
    result = _d(row)
    await sincronizza_preventivo_bozza(conn, tenant_id, computo_id)
    return result


async def riordina_voci(
    conn: asyncpg.Connection, tenant_id: str, computo_id: str, ordine: list[str]
) -> None:
    await _assert_computo_editabile(conn, tenant_id, computo_id)
    rows = await conn.fetch(
        """
        select id from public.computo_voci
        where computo_id = $1::uuid and tenant_id = $2::uuid
        """,
        computo_id,
        tenant_id,
    )
    esistenti = {str(row["id"]) for row in rows}
    richiesti = set(ordine)
    if len(richiesti) != len(ordine) or richiesti != esistenti:
        raise HTTPException(
            status_code=400,
            detail="L'ordine deve contenere tutte le voci del computo una sola volta",
        )
    for i, vid in enumerate(ordine):
        await conn.execute(
            """
            update public.computo_voci set ordine = $1
            where id = $2::uuid and computo_id = $3::uuid and tenant_id = $4::uuid
            """,
            i * 10,
            vid,
            computo_id,
            tenant_id,
        )
    await sincronizza_preventivo_bozza(conn, tenant_id, computo_id)


async def duplica_computo(
    conn: asyncpg.Connection,
    tenant_id: str,
    computo_id: str,
    *,
    tipo: Optional[str] = None,
) -> dict:
    src = await conn.fetchrow(
        "select * from public.computi where id = $1::uuid and tenant_id = $2::uuid",
        computo_id,
        tenant_id,
    )
    if not src:
        raise HTTPException(status_code=404, detail="Computo non trovato")
    target_tipo = tipo or src["tipo"]
    is_variante = target_tipo == "variante"
    if is_variante and src["stato"] != "confermato":
        raise HTTPException(
            status_code=409,
            detail="La variante può essere creata solo da un computo confermato",
        )
    if is_variante and src["tipo"] == "variante":
        raise HTTPException(
            status_code=409,
            detail="Crea la nuova variante dal computo contrattuale originale",
        )
    new_id = await conn.fetchval(
        """
        insert into public.computi (
          tenant_id, lead_id, cantiere_id, parent_computo_id, prezzario_id, tipo, stato, note
        ) values ($1::uuid, $2, $3, $4, $5, $6, 'bozza', $7)
        returning id
        """,
        tenant_id,
        src["lead_id"],
        src["cantiere_id"],
        src["id"] if is_variante else None,
        src["prezzario_id"],
        target_tipo,
        (
            f"Variante di {src.get('numero') or src['id']}"
            if is_variante
            else f"Copia di {src.get('numero') or src['id']}"
        ),
    )
    await conn.execute(
        """
        insert into public.computo_voci (
          tenant_id, computo_id, origine_voce_id, parent_voce_id, ordine,
          super_categoria, categoria, sub_categoria, descrizione, um, tipo,
          qta, prezzo_unitario, generata_da_ai, validata_umano
        )
        select tenant_id, $1::uuid, origine_voce_id,
               case when $4::boolean then id else null end, ordine,
               super_categoria, categoria, sub_categoria, descrizione, um, tipo,
               qta, prezzo_unitario, generata_da_ai, validata_umano
        from public.computo_voci
        where computo_id = $2::uuid and tenant_id = $3::uuid
        """,
        new_id,
        computo_id,
        tenant_id,
        is_variante,
    )
    row = await conn.fetchrow(
        "select * from public.computi where id = $1 and tenant_id = $2::uuid",
        new_id,
        tenant_id,
    )
    return _d(row)


async def importa_computo_acca(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    filename: str,
    parsed: dict,
    lead_id: Optional[str] = None,
    cantiere_id: Optional[str] = None,
    prezzario_id: Optional[str] = None,
) -> dict:
    """Importa ACCA e applica prezzi GB solo con match deterministici univoci."""
    context = await _resolve_import_context(
        conn,
        tenant_id,
        lead_id=lead_id,
        cantiere_id=cantiere_id,
        prezzario_id=prezzario_id,
    )
    computo = await crea_computo(
        conn,
        tenant_id,
        lead_id=context["lead_id"],
        cantiere_id=context["cantiere_id"],
        prezzario_id=context["prezzario_id"],
        tipo="estimativo",
    )
    computo_id = computo["id"]
    selected_prezzario_id = computo.get("prezzario_id")
    price_rows = []
    if selected_prezzario_id:
        price_rows = await conn.fetch(
            """
            select id, codice, super_categoria, categoria, sub_categoria,
                   descrizione, um, tipo, prezzo_unitario
            from public.prezzario_voci
            where tenant_id = $1::uuid and prezzario_id = $2::uuid
              and attiva = true and codice is not null
            order by created_at desc, id
            """,
            tenant_id,
            selected_prezzario_id,
        )
    candidates_by_code: dict[str, list[dict]] = {}
    for row in price_rows:
        candidate = _d(row)
        candidates_by_code.setdefault(
            _normalizza_codice(candidate.get("codice")), []
        ).append(candidate)

    matched_count = 0
    total_gb = Decimal("0")
    for item in parsed["voci"]:
        code = str(item.get("codice") or f"ACCA-{item['numero']:03d}")
        match = _abbina_voce_acca(item, candidates_by_code)
        if match:
            matched_count += 1
        price = Decimal(str(match["prezzo_unitario"] if match else item["prezzo_unitario"]))
        quantity = Decimal(str(item["qta"]))
        total_gb += (quantity * price).quantize(Decimal("0.01"))
        await conn.execute(
            """
            insert into public.computo_voci (
              tenant_id, computo_id, origine_voce_id, ordine,
              super_categoria, categoria, sub_categoria, descrizione, um, tipo,
              qta, prezzo_unitario,
              generata_da_ai, validata_umano
            ) values (
              $1::uuid, $2::uuid, $3::uuid, $4, $5, $6,
              $7, $8, $9, $10, $11, $12, $13, $14
            )
            """,
            tenant_id,
            computo_id,
            match["id"] if match else None,
            int(item["numero"]) * 10,
            match["super_categoria"] if match else "Importazione ACCA",
            match["categoria"] if match else "Computo PriMus",
            code,
            item["descrizione"],
            item["um"],
            match["tipo"] if match else (
                "a_corpo" if item["um"] == "corpo" else "a_misura"
            ),
            item["qta"],
            price,
            not bool(match),
            bool(match),
        )
    pending_count = len(parsed["voci"]) - matched_count
    await conn.execute(
        """
        update public.computi
        set note = $1, stato = $2
        where id = $3::uuid and tenant_id = $4::uuid
        """,
        (
            f"Importato da PDF ACCA: {filename} | "
            f"Prezzi GB abbinati: {matched_count}/{parsed['n_voci']} | "
            f"Da verificare: {pending_count}"
        ),
        "bozza" if pending_count == 0 else "ai_da_revisionare",
        computo_id,
        tenant_id,
    )
    result = await get_computo(conn, tenant_id, computo_id)
    result["importazione"] = {
        "file": filename,
        "n_voci": parsed["n_voci"],
        "totale_pdf": float(parsed["totale_pdf"]),
        "totale_gb": float(total_gb),
        "n_prezzi_gb": matched_count,
        "n_da_verificare": pending_count,
        "criterio": "codice tariffa + unita di misura, match univoco",
    }
    result["automazione"] = {
        "pronto_preventivo": pending_count == 0 and bool(context["lead_id"]),
        "cliente_associato": bool(context["lead_id"] or context["cliente_id"]),
        "cantiere_associato": bool(context["cantiere_id"]),
        "prezzario_associato": bool(selected_prezzario_id),
        "richiede_revisione": pending_count > 0,
    }
    return result


async def crea_variante(
    conn: asyncpg.Connection, tenant_id: str, computo_id: str
) -> dict:
    return await duplica_computo(
        conn, tenant_id, computo_id, tipo="variante"
    )


async def get_confronto_variante(
    conn: asyncpg.Connection, tenant_id: str, variante_id: str
) -> dict:
    variante = await conn.fetchrow(
        """
        select v.*, b.numero as numero_base, b.stato as stato_base
        from public.computi v
        join public.computi b
          on b.id = v.parent_computo_id and b.tenant_id = v.tenant_id
        where v.id = $1::uuid and v.tenant_id = $2::uuid
          and v.tipo = 'variante'
        """,
        variante_id,
        tenant_id,
    )
    if not variante:
        raise HTTPException(status_code=404, detail="Variante non trovata")

    rows = await conn.fetch(
        """
        select *
        from public.computo_varianti_confronto
        where tenant_id = $1::uuid and variante_id = $2::uuid
        order by ordine, coalesce(descrizione_variante, descrizione_base)
        """,
        tenant_id,
        variante_id,
    )
    totals = await conn.fetchrow(
        """
        select
          coalesce(sum(v.totale) filter (where v.computo_id = $2::uuid), 0)
            ::numeric(14,2) as totale_variante,
          coalesce(sum(v.totale) filter (where v.computo_id = $3::uuid), 0)
            ::numeric(14,2) as totale_base
        from public.computo_voci v
        where v.tenant_id = $1::uuid
          and v.computo_id in ($2::uuid, $3::uuid)
        """,
        tenant_id,
        variante_id,
        variante["parent_computo_id"],
    )
    totale_base = Decimal(totals["totale_base"] or 0)
    totale_variante = Decimal(totals["totale_variante"] or 0)
    delta = totale_variante - totale_base
    counts = {name: 0 for name in ("invariata", "modificata", "nuova", "soppressa")}
    for row in rows:
        counts[row["classificazione"]] += 1

    return {
        "base": {
            "id": str(variante["parent_computo_id"]),
            "numero": variante["numero_base"],
            "stato": variante["stato_base"],
        },
        "variante": {
            "id": str(variante["id"]),
            "numero": variante["numero"],
            "stato": variante["stato"],
        },
        "riepilogo": {
            "totale_base": float(totale_base),
            "totale_variante": float(totale_variante),
            "delta_importo": float(delta),
            "delta_percentuale": (
                round(float(delta / totale_base * 100), 2)
                if totale_base
                else None
            ),
            "conteggi": counts,
        },
        "righe": [_d(row) for row in rows],
    }


async def conferma_computo(conn: asyncpg.Connection, tenant_id: str, computo_id: str) -> dict:
    """409 se restano voci generata_da_ai and not validata_umano."""
    current = await conn.fetchrow(
        """
        select * from public.computi
        where id = $1::uuid and tenant_id = $2::uuid
        for update
        """,
        computo_id,
        tenant_id,
    )
    if not current:
        raise HTTPException(status_code=404, detail="Computo non trovato")
    if current["stato"] in LOCKED_COMPUTO_STATES:
        return _d(current)
    pending = await conn.fetchval(
        """
        select count(*) from public.computo_voci
        where computo_id = $1::uuid and tenant_id = $2::uuid
          and generata_da_ai = true and validata_umano = false
        """,
        computo_id,
        tenant_id,
    )
    if pending and int(pending) > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Restano {pending} voci automatiche non validate: validale prima di confermare",
        )
    await sincronizza_preventivo_bozza(conn, tenant_id, computo_id)
    row = await conn.fetchrow(
        """
        update public.computi set stato = 'confermato'
        where id = $1::uuid and tenant_id = $2::uuid
        returning *
        """,
        computo_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Computo non trovato")
    return _d(row)


async def valida_voci_ai(
    conn: asyncpg.Connection,
    tenant_id: str,
    computo_id: str,
    *,
    voce_ids: Optional[list[str]] = None,
) -> int:
    await _assert_computo_editabile(conn, tenant_id, computo_id)
    if voce_ids:
        result = await conn.execute(
            """
            update public.computo_voci set validata_umano = true
            where computo_id = $1::uuid and tenant_id = $2::uuid
              and id = any($3::uuid[]) and generata_da_ai = true
            """,
            computo_id,
            tenant_id,
            voce_ids,
        )
    else:
        result = await conn.execute(
            """
            update public.computo_voci set validata_umano = true
            where computo_id = $1::uuid and tenant_id = $2::uuid and generata_da_ai = true
            """,
            computo_id,
            tenant_id,
        )
    try:
        count = int(result.split()[-1])
    except Exception:
        count = 0
    await sincronizza_preventivo_bozza(conn, tenant_id, computo_id)
    return count


async def get_computo(conn: asyncpg.Connection, tenant_id: str, computo_id: str) -> dict:
    c = await conn.fetchrow(
        """
        select c.*, coalesce(l.nome, cl.nome, ca.cliente) as cliente,
               p.nome as prezzario_nome,
               pb.id as preventivo_bozza_id,
               pb.numero as preventivo_bozza_numero,
               pb.totale_documento as preventivo_bozza_totale
        from public.computi c
        left join public.leads l
          on l.id = c.lead_id and l.tenant_id = c.tenant_id
        left join public.cantieri ca
          on ca.id = c.cantiere_id and ca.tenant_id = c.tenant_id
        left join public.clienti cl
          on cl.id = coalesce(ca.cliente_id, l.cliente_id)
         and cl.tenant_id = c.tenant_id
        left join public.prezzari p
          on p.id = c.prezzario_id and p.tenant_id = c.tenant_id
        left join lateral (
          select pr.id, pr.numero, pr.totale_documento
          from public.preventivi pr
          where pr.computo_id = c.id
            and pr.tenant_id = c.tenant_id
            and pr.stato = 'bozza'
          order by pr.created_at desc, pr.id desc
          limit 1
        ) pb on true
        where c.id = $1::uuid and c.tenant_id = $2::uuid
        """,
        computo_id,
        tenant_id,
    )
    if not c:
        raise HTTPException(status_code=404, detail="Computo non trovato")
    voci = await conn.fetch(
        """
        select * from public.computo_voci
        where computo_id = $1::uuid and tenant_id = $2::uuid
        order by ordine, descrizione
        """,
        computo_id,
        tenant_id,
    )
    totali = await conn.fetchrow(
        """
        select * from public.computi_totali
        where computo_id = $1::uuid and tenant_id = $2::uuid
        """,
        computo_id,
        tenant_id,
    )
    out = _d(c)
    out["voci"] = [_d(v) for v in voci]
    out["totali"] = _d(totali) if totali else {"totale": 0, "n_voci": 0, "n_da_validare": 0}
    return out


def _importi_preventivo(computo: dict, sconto: float, iva: float) -> dict:
    imponibile = round(float(computo["totali"].get("totale") or 0), 2)
    sconto = max(0.0, min(100.0, float(sconto)))
    iva = max(0.0, float(iva))
    netto = imponibile * (1 - sconto / 100)
    iva_importo = round(netto * iva / 100, 2)
    return {
        "imponibile": imponibile,
        "sconto": sconto,
        "iva": iva,
        "iva_importo": iva_importo,
        "totale": round(netto + iva_importo, 2),
    }


async def _cliente_id_per_computo(
    conn: asyncpg.Connection, tenant_id: str, computo_id: str
) -> Any:
    return await conn.fetchval(
        """
        select coalesce(ca.cliente_id, l.cliente_id)
        from public.computi co
        left join public.cantieri ca
          on ca.id = co.cantiere_id and ca.tenant_id = co.tenant_id
        left join public.leads l
          on l.id = co.lead_id and l.tenant_id = co.tenant_id
        where co.id = $1::uuid and co.tenant_id = $2::uuid
        """,
        computo_id,
        tenant_id,
    )


async def sincronizza_preventivo_bozza(
    conn: asyncpg.Connection,
    tenant_id: str,
    computo_id: str,
    *,
    computo: Optional[dict] = None,
    preventivo: Optional[asyncpg.Record | dict] = None,
    sconto: Optional[float] = None,
    iva: Optional[float] = None,
) -> dict | None:
    """Aggiorna la stessa bozza dopo ogni modifica del computo, senza duplicarla."""
    if preventivo is None:
        preventivo = await conn.fetchrow(
            """
            select * from public.preventivi
            where tenant_id = $1::uuid and computo_id = $2::uuid
              and stato = 'bozza'
            order by created_at desc, id desc
            limit 1
            for update
            """,
            tenant_id,
            computo_id,
        )
    if not preventivo:
        return None

    computo = computo or await get_computo(conn, tenant_id, computo_id)
    terms = _importi_preventivo(
        computo,
        preventivo["sconto_percentuale"] if sconto is None else sconto,
        preventivo["iva_percentuale"] if iva is None else iva,
    )
    cliente_id = await _cliente_id_per_computo(conn, tenant_id, computo_id)
    row = await conn.fetchrow(
        """
        update public.preventivi
        set lead_id = $1::uuid,
            cliente_id = $2::uuid,
            totale_imponibile = $3,
            sconto_percentuale = $4,
            iva_percentuale = $5,
            totale_iva = $6,
            totale_documento = $7,
            snapshot_voci = $8::jsonb,
            pdf_path = null
        where id = $9::uuid and tenant_id = $10::uuid and stato = 'bozza'
        returning *
        """,
        computo.get("lead_id"),
        cliente_id,
        terms["imponibile"],
        terms["sconto"],
        terms["iva"],
        terms["iva_importo"],
        terms["totale"],
        json.dumps(computo["voci"], default=str),
        preventivo["id"],
        tenant_id,
    )
    return _d(row) if row else None


async def lista_computi(conn: asyncpg.Connection, tenant_id: str) -> list[dict]:
    rows = await conn.fetch(
        """
        select c.*, t.totale, t.n_voci, t.n_da_validare,
               coalesce(l.nome, cl.nome, ca.cliente) as cliente,
               p.nome as prezzario_nome
        from public.computi c
        left join public.computi_totali t
          on t.computo_id = c.id and t.tenant_id = c.tenant_id
        left join public.leads l
          on l.id = c.lead_id and l.tenant_id = c.tenant_id
        left join public.cantieri ca
          on ca.id = c.cantiere_id and ca.tenant_id = c.tenant_id
        left join public.clienti cl
          on cl.id = coalesce(ca.cliente_id, l.cliente_id)
         and cl.tenant_id = c.tenant_id
        left join public.prezzari p
          on p.id = c.prezzario_id and p.tenant_id = c.tenant_id
        where c.tenant_id = $1::uuid
        order by c.created_at desc
        """,
        tenant_id,
    )
    return [_d(r) for r in rows]


async def lista_preventivi(conn: asyncpg.Connection, tenant_id: str) -> list[dict]:
    """Lista documenti EdilOS nel formato condiviso con la dashboard legacy."""
    rows = await conn.fetch(
        """
        select p.id, p.computo_id, p.numero,
               coalesce(l.nome, cl.nome, 'Cliente non associato') as cliente,
               coalesce(l.citta, cl.citta) as citta,
               coalesce(l.telefono, cl.telefono) as telefono,
               coalesce(l.email, cl.email) as email,
               coalesce(l.config ->> 'livello', 'computo') as livello,
               p.totale_documento as range_basso,
               p.totale_documento as range_alto,
               p.totale_documento,
               case p.stato
                 when 'bozza' then 'preventivo_preparazione'
                 when 'inviato' then 'preventivo_inviato'
                 when 'accettato' then 'chiuso_vinto'
                 when 'rifiutato' then 'chiuso_perso'
                 when 'scaduto' then 'chiuso_perso'
               end as status,
               p.stato as stato_documento,
               p.validita_giorni,
               p.inviato_at,
               p.accettato_at,
               p.rifiutato_at,
               p.scaduto_at,
               p.ultimo_destinatario,
               p.ultimo_email_provider,
               p.ultimo_email_id,
               co.stato as computo_stato,
               greatest(
                 0,
                 floor(
                   extract(epoch from (now() - coalesce(p.inviato_at, p.created_at)))
                   / 86400
                 )
               )::int as giorni_silenzio,
               'edilos'::text as source,
               p.created_at
        from public.preventivi p
        left join public.leads l
          on l.id = p.lead_id and l.tenant_id = p.tenant_id
        left join public.clienti cl
          on cl.id = p.cliente_id and cl.tenant_id = p.tenant_id
        join public.computi co
          on co.id = p.computo_id and co.tenant_id = p.tenant_id
        where p.tenant_id = $1::uuid
        order by p.created_at desc
        """,
        tenant_id,
    )
    return [_d(r) for r in rows]


async def get_preventivo(
    conn: asyncpg.Connection,
    tenant_id: str,
    preventivo_id: str,
    *,
    for_update: bool = False,
) -> dict:
    suffix = " for update" if for_update else ""
    row = await conn.fetchrow(
        f"""
        select * from public.preventivi
        where id = $1::uuid and tenant_id = $2::uuid{suffix}
        """,
        preventivo_id,
        tenant_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")
    return _d(row)


async def lista_eventi_preventivo(
    conn: asyncpg.Connection, tenant_id: str, preventivo_id: str
) -> list[dict]:
    await get_preventivo(conn, tenant_id, preventivo_id)
    rows = await conn.fetch(
        """
        select * from public.preventivo_eventi
        where preventivo_id = $1::uuid and tenant_id = $2::uuid
        order by created_at desc, id desc
        """,
        preventivo_id,
        tenant_id,
    )
    return [_d(row) for row in rows]


async def _aggiorna_lead_da_preventivo(
    conn: asyncpg.Connection,
    tenant_id: str,
    preventivo: dict,
    nuovo_stato: str,
    *,
    autore: str,
    dettaglio: str,
) -> None:
    lead_id = preventivo.get("lead_id")
    lead_status = LEAD_STATUS_BY_PREVENTIVO.get(nuovo_stato)
    if not lead_id or not lead_status:
        return
    event = {
        "id": f"prev-{preventivo['id']}-{nuovo_stato}",
        "tipo": "preventivo",
        "testo": dettaglio,
        "ts": datetime.now(timezone.utc).isoformat(),
        "autore": autore,
    }
    await conn.execute(
        """
        update public.leads
        set status = $1,
            prossima_azione = $2,
            timeline = jsonb_build_array($3::jsonb) || coalesce(timeline, '[]'::jsonb)
        where id = $4::uuid and tenant_id = $5::uuid
        """,
        lead_status,
        LEAD_NEXT_ACTION_BY_PREVENTIVO[nuovo_stato],
        json.dumps(event, ensure_ascii=False),
        lead_id,
        tenant_id,
    )


async def registra_invio_preventivo(
    conn: asyncpg.Connection,
    tenant_id: str,
    preventivo: dict,
    *,
    destinatario: str,
    oggetto: str,
    provider: str,
    provider_message_id: str,
    idempotency_key: str,
    autore: str,
) -> dict:
    row = await conn.fetchrow(
        """
        update public.preventivi
        set stato = 'inviato',
            inviato_at = coalesce(inviato_at, now()),
            ultimo_destinatario = $1,
            ultimo_email_provider = $2,
            ultimo_email_id = nullif($3, '')
        where id = $4::uuid and tenant_id = $5::uuid and stato = 'bozza'
        returning *
        """,
        destinatario,
        provider,
        provider_message_id,
        preventivo["id"],
        tenant_id,
    )
    if not row:
        raise HTTPException(
            status_code=409,
            detail="Il preventivo non è più in bozza e non può essere inviato",
        )
    await conn.execute(
        """
        insert into public.preventivo_eventi (
          tenant_id, preventivo_id, tipo, stato_precedente, stato_successivo,
          destinatario, oggetto, provider, provider_message_id,
          idempotency_key, dettaglio, autore
        ) values (
          $1::uuid, $2::uuid, 'email_inviata', 'bozza', 'inviato',
          $3, $4, $5, nullif($6, ''), $7, $8, $9
        )
        """,
        tenant_id,
        preventivo["id"],
        destinatario,
        oggetto,
        provider,
        provider_message_id,
        idempotency_key,
        f"Preventivo {preventivo['numero']} inviato a {destinatario}",
        autore,
    )
    updated = _d(row)
    await _aggiorna_lead_da_preventivo(
        conn,
        tenant_id,
        updated,
        "inviato",
        autore=autore,
        dettaglio=f"Preventivo {preventivo['numero']} inviato via email",
    )
    return updated


async def aggiorna_stato_preventivo(
    conn: asyncpg.Connection,
    tenant_id: str,
    preventivo_id: str,
    nuovo_stato: str,
    *,
    autore: str,
) -> dict:
    preventivo = await get_preventivo(
        conn, tenant_id, preventivo_id, for_update=True
    )
    stato_corrente = preventivo["stato"]
    if nuovo_stato == "inviato":
        raise HTTPException(
            status_code=400,
            detail="Per impostare lo stato inviato usa l'azione Invia preventivo",
        )
    if nuovo_stato not in PREVENTIVO_TRANSITIONS.get(stato_corrente, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Transizione non consentita: {stato_corrente} → {nuovo_stato}",
        )
    row = await conn.fetchrow(
        """
        update public.preventivi
        set stato = $1,
            accettato_at = case when $1 = 'accettato' then now() else accettato_at end,
            rifiutato_at = case when $1 = 'rifiutato' then now() else rifiutato_at end,
            scaduto_at = case when $1 = 'scaduto' then now() else scaduto_at end
        where id = $2::uuid and tenant_id = $3::uuid and stato = $4
        returning *
        """,
        nuovo_stato,
        preventivo_id,
        tenant_id,
        stato_corrente,
    )
    if not row:
        raise HTTPException(
            status_code=409,
            detail="Il preventivo è stato modificato da un altro operatore",
        )
    dettaglio = f"Preventivo {preventivo['numero']}: {stato_corrente} → {nuovo_stato}"
    await conn.execute(
        """
        insert into public.preventivo_eventi (
          tenant_id, preventivo_id, tipo, stato_precedente, stato_successivo,
          dettaglio, autore
        ) values ($1::uuid, $2::uuid, 'stato', $3, $4, $5, $6)
        """,
        tenant_id,
        preventivo_id,
        stato_corrente,
        nuovo_stato,
        dettaglio,
        autore,
    )
    updated = _d(row)
    await _aggiorna_lead_da_preventivo(
        conn,
        tenant_id,
        updated,
        nuovo_stato,
        autore=autore,
        dettaglio=dettaglio,
    )
    return updated


async def computo_to_preventivo(
    conn: asyncpg.Connection,
    tenant_id: str,
    computo_id: str,
    *,
    sconto: float = 0,
    iva: float = 10,
    autore: Optional[str] = None,
    consenti_computo_editabile: bool = False,
) -> dict:
    c = await get_computo(conn, tenant_id, computo_id)
    pending = int(c["totali"].get("n_da_validare") or 0)
    editable_ready = (
        consenti_computo_editabile
        and c["stato"] not in LOCKED_COMPUTO_STATES
        and pending == 0
    )
    if c["stato"] != "confermato" and not editable_ready:
        raise HTTPException(
            status_code=409,
            detail="Conferma il computo e valida tutte le voci automatiche prima di creare il preventivo",
        )
    if not c["voci"]:
        raise HTTPException(
            status_code=409,
            detail="Inserisci almeno una voce prima di creare il preventivo",
        )

    # Una sola bozza modificabile per computo nel percorso applicativo, anche
    # con richieste concorrenti. La numerazione resta separatamente serializzata.
    await conn.fetchval(
        "select pg_advisory_xact_lock(hashtextextended($1, 0))",
        f"edilos:preventivo-bozza:{tenant_id}:{computo_id}",
    )
    existing = await conn.fetchrow(
        """
        select * from public.preventivi
        where tenant_id = $1::uuid and computo_id = $2::uuid
          and stato = 'bozza'
        order by created_at desc, id desc
        limit 1
        for update
        """,
        tenant_id,
        computo_id,
    )
    if existing:
        return await sincronizza_preventivo_bozza(
            conn,
            tenant_id,
            computo_id,
            computo=c,
            preventivo=existing,
            sconto=sconto,
            iva=iva,
        )

    terms = _importi_preventivo(c, sconto, iva)
    cliente_id = await _cliente_id_per_computo(conn, tenant_id, computo_id)

    anno = datetime.now(timezone.utc).year
    # Serializza la numerazione per tenant senza dipendere dalla policy UPDATE
    # di tenants: anche staff/operations possono creare preventivi mantenendo
    # un solo progressivo per transazione concorrente.
    await conn.fetchval(
        "select pg_advisory_xact_lock(hashtextextended($1, 0))",
        f"edilos:preventivo-progressivo:{tenant_id}",
    )
    progressivo = await conn.fetchval(
        """
        select coalesce(max(progressivo), 0) + 1 from public.preventivi
        where tenant_id = $1::uuid and anno = $2
        """,
        tenant_id,
        anno,
    )
    numero = f"PREV-{anno}-{int(progressivo):04d}"
    row = await conn.fetchrow(
        """
        insert into public.preventivi (
          tenant_id, computo_id, lead_id, cliente_id,
          numero, anno, progressivo, stato,
          totale_imponibile, sconto_percentuale, iva_percentuale, totale_iva,
          totale_documento, snapshot_voci
        ) values (
          $1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7, 'bozza',
          $8, $9, $10, $11, $12, $13::jsonb
        ) returning *
        """,
        tenant_id,
        computo_id,
        c.get("lead_id"),
        cliente_id,
        numero,
        anno,
        progressivo,
        terms["imponibile"],
        terms["sconto"],
        terms["iva"],
        terms["iva_importo"],
        terms["totale"],
        json.dumps(c["voci"], default=str),
    )
    await conn.execute(
        """
        insert into public.preventivo_eventi (
          tenant_id, preventivo_id, tipo, stato_successivo, dettaglio, autore
        ) values ($1::uuid, $2::uuid, 'creato', 'bozza', $3, $4)
        """,
        tenant_id,
        row["id"],
        f"Preventivo {numero} creato dal computo {computo_id}",
        autore or "sistema",
    )
    return _d(row)
