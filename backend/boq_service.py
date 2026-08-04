"""Computo metrico (BOQ): CRUD voci con snapshot prezzi e conferma con validazione AI."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import asyncpg
from fastapi import HTTPException


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
    stato = await conn.fetchval(
        "select stato from public.computi where id = $1::uuid and tenant_id = $2::uuid",
        computo_id,
        tenant_id,
    )
    if stato is None:
        raise HTTPException(status_code=404, detail="Computo non trovato")
    if stato in ("confermato", "archiviato"):
        raise HTTPException(
            status_code=409, detail="Computo confermato: crea una variante per modificarlo"
        )

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
    return _d(row)


async def aggiorna_voce(
    conn: asyncpg.Connection, tenant_id: str, voce_id: str, **campi
) -> dict:
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
    args.extend([voce_id, tenant_id])
    row = await conn.fetchrow(
        f"""
        update public.computo_voci
        set {', '.join(sets)}
        where id = ${len(args)-1}::uuid and tenant_id = ${len(args)}::uuid
        returning *
        """,
        *args,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Voce di computo non trovata")
    return _d(row)


async def riordina_voci(
    conn: asyncpg.Connection, tenant_id: str, computo_id: str, ordine: list[str]
) -> None:
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
        src["id"],
        src["prezzario_id"],
        tipo or src["tipo"],
        f"Copia di {src.get('numero') or src['id']}",
    )
    await conn.execute(
        """
        insert into public.computo_voci (
          tenant_id, computo_id, origine_voce_id, ordine,
          super_categoria, categoria, sub_categoria, descrizione, um, tipo,
          qta, prezzo_unitario, generata_da_ai, validata_umano
        )
        select tenant_id, $1::uuid, origine_voce_id, ordine,
               super_categoria, categoria, sub_categoria, descrizione, um, tipo,
               qta, prezzo_unitario, generata_da_ai, validata_umano
        from public.computo_voci where computo_id = $2::uuid
        """,
        new_id,
        computo_id,
    )
    row = await conn.fetchrow("select * from public.computi where id = $1", new_id)
    return _d(row)


async def conferma_computo(conn: asyncpg.Connection, tenant_id: str, computo_id: str) -> dict:
    """409 se restano voci generata_da_ai and not validata_umano."""
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
            detail=f"Restano {pending} voci AI non validate: validale prima di confermare",
        )
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
        return int(result.split()[-1])
    except Exception:
        return 0


async def get_computo(conn: asyncpg.Connection, tenant_id: str, computo_id: str) -> dict:
    c = await conn.fetchrow(
        "select * from public.computi where id = $1::uuid and tenant_id = $2::uuid",
        computo_id,
        tenant_id,
    )
    if not c:
        raise HTTPException(status_code=404, detail="Computo non trovato")
    voci = await conn.fetch(
        """
        select * from public.computo_voci
        where computo_id = $1::uuid order by ordine, descrizione
        """,
        computo_id,
    )
    totali = await conn.fetchrow(
        "select * from public.computi_totali where computo_id = $1",
        computo_id,
    )
    out = _d(c)
    out["voci"] = [_d(v) for v in voci]
    out["totali"] = _d(totali) if totali else {"totale": 0, "n_voci": 0, "n_da_validare": 0}
    return out


async def lista_computi(conn: asyncpg.Connection, tenant_id: str) -> list[dict]:
    rows = await conn.fetch(
        """
        select c.*, t.totale, t.n_voci, t.n_da_validare
        from public.computi c
        left join public.computi_totali t on t.computo_id = c.id
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
               coalesce(l.nome, 'Cliente non associato') as cliente,
               l.citta, l.telefono, l.email,
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
               0 as giorni_silenzio,
               'edilos'::text as source,
               p.created_at
        from public.preventivi p
        left join public.leads l
          on l.id = p.lead_id and l.tenant_id = p.tenant_id
        where p.tenant_id = $1::uuid
        order by p.created_at desc
        """,
        tenant_id,
    )
    return [_d(r) for r in rows]


async def computo_to_preventivo(
    conn: asyncpg.Connection,
    tenant_id: str,
    computo_id: str,
    *,
    sconto: float = 0,
    iva: float = 10,
) -> dict:
    c = await get_computo(conn, tenant_id, computo_id)
    if c["stato"] != "confermato":
        raise HTTPException(
            status_code=409,
            detail="Conferma il computo e valida tutte le voci AI prima di creare il preventivo",
        )

    imponibile = float(c["totali"].get("totale") or 0)
    sconto = max(0.0, min(100.0, float(sconto)))
    iva = max(0.0, float(iva))
    netto = imponibile * (1 - sconto / 100)
    iva_importo = round(netto * iva / 100, 2)
    totale = round(netto + iva_importo, 2)

    from datetime import datetime, timezone

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
    snapshot = c["voci"]
    row = await conn.fetchrow(
        """
        insert into public.preventivi (
          tenant_id, computo_id, lead_id, numero, anno, progressivo, stato,
          totale_imponibile, sconto_percentuale, iva_percentuale, totale_iva,
          totale_documento, snapshot_voci
        ) values (
          $1::uuid, $2::uuid, $3::uuid, $4, $5, $6, 'bozza',
          $7, $8, $9, $10, $11, $12::jsonb
        ) returning *
        """,
        tenant_id,
        computo_id,
        c.get("lead_id"),
        numero,
        anno,
        progressivo,
        round(imponibile, 2),
        sconto,
        iva,
        iva_importo,
        totale,
        __import__("json").dumps(snapshot, default=str),
    )
    return _d(row)
