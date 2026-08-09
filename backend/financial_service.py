"""Piano pagamenti, rate, extra e documenti economici per cantiere."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException

import preventivo_struttura


FINANCIAL_ROLES = frozenset({"owner", "admin"})


def _d(row: asyncpg.Record | dict | None) -> dict | None:
    if row is None:
        return None
    result = dict(row)
    for key, value in list(result.items()):
        if isinstance(value, UUID):
            result[key] = str(value)
        elif isinstance(value, Decimal):
            result[key] = float(value)
    return result


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


async def _require_cantiere(
    conn: asyncpg.Connection, tenant_id: str, cantiere_id: str
) -> dict:
    row = await conn.fetchrow(
        """
        select c.*, coalesce(cl.email, l.email) as cliente_email,
               coalesce(cl.telefono, l.telefono) as cliente_telefono,
               coalesce(cl.nome, l.nome, c.cliente) as cliente_nome
        from public.cantieri c
        left join public.clienti cl
          on cl.id = c.cliente_id and cl.tenant_id = c.tenant_id
        left join public.leads l
          on l.id = c.lead_id and l.tenant_id = c.tenant_id
        where c.tenant_id = $1::uuid and c.id = $2::uuid
        """,
        tenant_id,
        cantiere_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Cantiere non trovato")
    return _d(row)


async def crea_piano_pagamenti(
    conn: asyncpg.Connection,
    tenant_id: str,
    cantiere_id: str,
    *,
    preventivo_id: str,
    rate: list[dict],
    email_automatica: bool = True,
    whatsapp_automatico: bool = False,
    whatsapp_consenso: bool = False,
    giorni_preavviso: list[int] | None = None,
) -> dict:
    """Attiva il piano concordato e crea rate/scadenze in una transazione."""
    cantiere = await _require_cantiere(conn, tenant_id, cantiere_id)
    if email_automatica and not cantiere.get("cliente_email"):
        raise HTTPException(
            status_code=400,
            detail="Aggiungi l'email del cliente al cantiere oppure disattiva i promemoria email",
        )
    if whatsapp_automatico and not cantiere.get("cliente_telefono"):
        raise HTTPException(
            status_code=400,
            detail="Aggiungi il telefono del cliente prima di attivare WhatsApp",
        )
    if whatsapp_automatico and not whatsapp_consenso:
        raise HTTPException(
            status_code=400,
            detail="Conferma il consenso del cliente ai promemoria WhatsApp",
        )
    preavvisi = sorted(set(giorni_preavviso or [7, 1, 0]), reverse=True)
    if any(day < 0 or day > 365 for day in preavvisi):
        raise HTTPException(status_code=400, detail="Giorni di preavviso non validi")
    preventivo = await conn.fetchrow(
        """
        select p.*, co.cantiere_id, co.stato as computo_stato
        from public.preventivi p
        join public.computi co
          on co.id = p.computo_id and co.tenant_id = p.tenant_id
        where p.tenant_id = $1::uuid and p.id = $2::uuid
          and co.cantiere_id = $3::uuid
        for update
        """,
        tenant_id,
        preventivo_id,
        cantiere_id,
    )
    if not preventivo:
        raise HTTPException(
            status_code=404,
            detail="Contratto/preventivo non trovato per questo cantiere",
        )
    if preventivo["stato"] != "accettato" or preventivo["computo_stato"] != "confermato":
        raise HTTPException(
            status_code=409,
            detail="Conferma computo e contratto prima di attivare il piano pagamenti",
        )
    if not rate:
        raise HTTPException(status_code=400, detail="Inserisci almeno una rata")

    totale = _money(preventivo["totale_documento"])
    somma_rate = sum((_money(item.get("importo")) for item in rate), Decimal("0"))
    if somma_rate != totale:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Il totale delle rate ({somma_rate:.2f}) deve coincidere con "
                f"il contratto ({totale:.2f})"
            ),
        )
    numbers = [int(item.get("numero") or index) for index, item in enumerate(rate, 1)]
    if len(numbers) != len(set(numbers)) or min(numbers) < 1:
        raise HTTPException(status_code=400, detail="Numerazione rate non valida")
    sal_ids = [str(item["sal_id"]) for item in rate if item.get("sal_id")]
    if sal_ids:
        sal_count = await conn.fetchval(
            """
            select count(*) from public.sal
            where tenant_id = $1::uuid and cantiere_id = $2::uuid
              and id = any($3::uuid[]) and stato in ('emesso', 'approvato')
            """,
            tenant_id,
            cantiere_id,
            sal_ids,
        )
        if int(sal_count or 0) != len(set(sal_ids)):
            raise HTTPException(
                status_code=400,
                detail="Una o piu rate indicano un SAL non valido per il cantiere",
            )

    piano = await conn.fetchrow(
        """
        insert into public.piani_pagamento (
          tenant_id, cantiere_id, preventivo_id, totale_contratto,
          cliente_nome, cliente_email, cliente_telefono,
          email_automatica, whatsapp_automatico, whatsapp_consenso_at,
          giorni_preavviso
        ) values (
          $1::uuid, $2::uuid, $3::uuid, $4,
          $5, $6, $7, $8, $9,
          case when $10 then now() else null end, $11::integer[]
        ) returning *
        """,
        tenant_id,
        cantiere_id,
        preventivo_id,
        totale,
        cantiere["cliente_nome"],
        cantiere.get("cliente_email"),
        cantiere.get("cliente_telefono"),
        email_automatica,
        whatsapp_automatico,
        whatsapp_consenso,
        preavvisi,
    )

    for index, item in enumerate(rate, 1):
        numero = int(item.get("numero") or index)
        tipo = str(item.get("tipo") or "sal")
        data_scadenza = item["data_scadenza"]
        importo = _money(item["importo"])
        percentuale = (
            Decimal(str(item.get("percentuale"))).quantize(Decimal("0.001"))
            if item.get("percentuale") is not None
            else (importo / totale * 100).quantize(Decimal("0.001"))
        )
        incasso = await conn.fetchrow(
            """
            insert into public.incassi (
              tenant_id, cantiere_id, sal_id, descrizione, importo,
              data_prevista, stato, metodo, piano_pagamento_id,
              numero_rata, tipo_rata, percentuale, modalita_pagamento, note
            ) values (
              $1::uuid, $2::uuid, $3::uuid, $4, $5,
              $6, 'previsto', $7, $8::uuid,
              $9, $10, $11, $7, $12
            ) returning *
            """,
            tenant_id,
            cantiere_id,
            item.get("sal_id"),
            str(item.get("titolo") or f"Rata {numero}"),
            importo,
            data_scadenza,
            item.get("modalita_pagamento"),
            str(piano["id"]),
            numero,
            tipo,
            percentuale,
            item.get("note"),
        )
        await conn.execute(
            """
            insert into public.scadenze (
              tenant_id, cantiere_id, incasso_id, tipo,
              titolo, importo, data_scadenza, note
            ) values ($1::uuid, $2::uuid, $3::uuid, 'incasso', $4, $5, $6, $7)
            """,
            tenant_id,
            cantiere_id,
            str(incasso["id"]),
            str(item.get("titolo") or f"Rata {numero}"),
            importo,
            data_scadenza,
            item.get("note"),
        )

    await pianifica_promemoria(conn, tenant_id, str(piano["id"]))
    return await get_controllo_cantiere(conn, tenant_id, cantiere_id)


async def suggerisci_piano_pagamenti(
    conn: asyncpg.Connection, tenant_id: str, cantiere_id: str
) -> dict:
    """Precompila le rate dal contratto accettato, lasciando le date editabili."""
    cantiere = await _require_cantiere(conn, tenant_id, cantiere_id)
    row = await conn.fetchrow(
        """
        select p.*
        from public.preventivi p
        join public.computi co
          on co.tenant_id = p.tenant_id and co.id = p.computo_id
        where p.tenant_id = $1::uuid and co.cantiere_id = $2::uuid
          and p.stato = 'accettato' and co.stato = 'confermato'
        order by p.accettato_at desc nulls last, p.created_at desc
        limit 1
        """,
        tenant_id,
        cantiere_id,
    )
    if not row:
        raise HTTPException(
            status_code=409,
            detail="Non esiste un contratto accettato con computo confermato per il cantiere",
        )
    rate = preventivo_struttura.piano_pagamenti(
        row["snapshot_voci"] or [], row["totale_documento"]
    )
    suggested = []
    for index, rata in enumerate(rate, 1):
        if index == 1:
            tipo = "acconto"
        elif index == len(rate):
            tipo = "saldo"
        else:
            tipo = "sal"
        suggested.append(
            {
                "numero": index,
                "tipo": tipo,
                "titolo": rata["riferimento"],
                "descrizione": rata.get("descrizione"),
                "percentuale": rata["percentuale"],
                "importo": rata["importo"],
                "data_scadenza": (date.today() + timedelta(days=30 * (index - 1))).isoformat(),
                "modalita_pagamento": "Bonifico bancario",
            }
        )
    return {
        "preventivo_id": str(row["id"]),
        "contratto_numero": row["numero"],
        "totale_contratto": float(row["totale_documento"]),
        "cliente_nome": cantiere["cliente_nome"],
        "cliente_email": cantiere.get("cliente_email"),
        "cliente_telefono": cantiere.get("cliente_telefono"),
        "rate": suggested,
    }


async def pianifica_promemoria(
    conn: asyncpg.Connection, tenant_id: str, piano_id: str
) -> int:
    piano = await conn.fetchrow(
        """
        select * from public.piani_pagamento
        where tenant_id = $1::uuid and id = $2::uuid
        """,
        tenant_id,
        piano_id,
    )
    if not piano:
        raise HTTPException(status_code=404, detail="Piano pagamenti non trovato")
    rate = await conn.fetch(
        """
        select * from public.incassi
        where tenant_id = $1::uuid and piano_pagamento_id = $2::uuid
          and stato in ('previsto', 'parziale')
        order by numero_rata
        """,
        tenant_id,
        piano_id,
    )
    created = 0
    for rata in rate:
        for anticipo in piano["giorni_preavviso"]:
            planned = rata["data_prevista"] - timedelta(days=int(anticipo))
            tipo = "scadenza" if int(anticipo) == 0 else "preavviso"
            channels = []
            if piano["email_automatica"] and piano["cliente_email"]:
                channels.append(("email", piano["cliente_email"]))
            if piano["whatsapp_automatico"] and piano["cliente_telefono"]:
                channels.append(("whatsapp", piano["cliente_telefono"]))
            for channel, recipient in channels:
                status = await conn.execute(
                    """
                    insert into public.notifiche_pagamento (
                      tenant_id, cantiere_id, incasso_id, canale, tipo,
                      destinatario, programmata_per, payload
                    ) values ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8::jsonb)
                    on conflict (tenant_id, incasso_id, canale, tipo, programmata_per)
                    do nothing
                    """,
                    tenant_id,
                    str(piano["cantiere_id"]),
                    str(rata["id"]),
                    channel,
                    tipo,
                    recipient,
                    planned,
                    json.dumps(
                        {
                            "cliente": piano["cliente_nome"],
                            "rata": rata["numero_rata"],
                            "titolo": rata["descrizione"],
                            "importo": float(rata["importo"]),
                            "data_scadenza": rata["data_prevista"].isoformat(),
                        }
                    ),
                )
                if status.endswith("1"):
                    created += 1
    return created


async def registra_pagamento(
    conn: asyncpg.Connection,
    tenant_id: str,
    incasso_id: str,
    *,
    importo: Decimal,
    data_pagamento: date,
    metodo: str | None = None,
    riferimento: str | None = None,
    note: str | None = None,
) -> dict:
    rata = await conn.fetchrow(
        """
        select * from public.incassi
        where tenant_id = $1::uuid and id = $2::uuid
        for update
        """,
        tenant_id,
        incasso_id,
    )
    if not rata:
        raise HTTPException(status_code=404, detail="Rata non trovata")
    if rata["stato"] in {"incassato", "annullato"}:
        raise HTTPException(status_code=409, detail="Rata già chiusa")
    pagato = await conn.fetchval(
        """
        select coalesce(sum(importo), 0) from public.pagamenti_cliente
        where tenant_id = $1::uuid and incasso_id = $2::uuid
        """,
        tenant_id,
        incasso_id,
    )
    residuo = _money(rata["importo"]) - _money(pagato)
    value = _money(importo)
    if value <= 0 or value > residuo:
        raise HTTPException(
            status_code=400,
            detail=f"Importo non valido: residuo rata {residuo:.2f}",
        )
    payment = await conn.fetchrow(
        """
        insert into public.pagamenti_cliente (
          tenant_id, cantiere_id, incasso_id, importo,
          data_pagamento, metodo, riferimento, note
        ) values ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8)
        returning *
        """,
        tenant_id,
        str(rata["cantiere_id"]),
        incasso_id,
        value,
        data_pagamento,
        metodo,
        riferimento,
        note,
    )
    nuovo_totale = _money(pagato) + value
    stato = "incassato" if nuovo_totale >= _money(rata["importo"]) else "parziale"
    await conn.execute(
        """
        update public.incassi
        set stato = $1, data_incasso = $2, metodo = coalesce($3, metodo)
        where tenant_id = $4::uuid and id = $5::uuid
        """,
        stato,
        data_pagamento,
        metodo,
        tenant_id,
        incasso_id,
    )
    if stato == "incassato":
        await conn.execute(
            """
            update public.scadenze
            set stato = 'completata', completata_at = now()
            where tenant_id = $1::uuid and incasso_id = $2::uuid and stato = 'aperta'
            """,
            tenant_id,
            incasso_id,
        )
        await conn.execute(
            """
            update public.notifiche_pagamento set stato = 'saltata'
            where tenant_id = $1::uuid and incasso_id = $2::uuid
              and stato in ('programmata', 'fallita')
            """,
            tenant_id,
            incasso_id,
        )
    return _d(payment)


async def collega_sal_rata(
    conn: asyncpg.Connection,
    tenant_id: str,
    incasso_id: str,
    sal_id: str | None,
) -> dict:
    rata = await conn.fetchrow(
        """
        select * from public.incassi
        where tenant_id = $1::uuid and id = $2::uuid
          and piano_pagamento_id is not null
        """,
        tenant_id,
        incasso_id,
    )
    if not rata:
        raise HTTPException(status_code=404, detail="Rata del piano non trovata")
    if sal_id:
        exists = await conn.fetchval(
            """
            select exists(
              select 1 from public.sal
              where tenant_id = $1::uuid and id = $2::uuid
                and cantiere_id = $3::uuid and stato in ('emesso', 'approvato')
            )
            """,
            tenant_id,
            sal_id,
            str(rata["cantiere_id"]),
        )
        if not exists:
            raise HTTPException(status_code=404, detail="SAL emesso non trovato nel cantiere")
    row = await conn.fetchrow(
        """
        update public.incassi set sal_id = $1::uuid
        where tenant_id = $2::uuid and id = $3::uuid
        returning *
        """,
        sal_id,
        tenant_id,
        incasso_id,
    )
    return _d(row)


async def crea_extra(
    conn: asyncpg.Connection,
    tenant_id: str,
    cantiere_id: str,
    *,
    titolo: str,
    descrizione: str,
    imponibile: Decimal,
    iva_percentuale: Decimal,
    data_scadenza: date | None = None,
    sal_id: str | None = None,
) -> dict:
    await _require_cantiere(conn, tenant_id, cantiere_id)
    if sal_id:
        valid_sal = await conn.fetchval(
            """
            select exists(
              select 1 from public.sal
              where tenant_id = $1::uuid and cantiere_id = $2::uuid
                and id = $3::uuid and stato in ('emesso', 'approvato')
            )
            """,
            tenant_id,
            cantiere_id,
            sal_id,
        )
        if not valid_sal:
            raise HTTPException(status_code=400, detail="SAL non valido per il cantiere")
    await conn.fetchval(
        "select pg_advisory_xact_lock(hashtextextended($1, 0))",
        f"edilos:extra:{tenant_id}:{cantiere_id}",
    )
    numero = await conn.fetchval(
        """
        select coalesce(max(numero), 0) + 1 from public.extra_cantiere
        where tenant_id = $1::uuid and cantiere_id = $2::uuid
        """,
        tenant_id,
        cantiere_id,
    )
    row = await conn.fetchrow(
        """
        insert into public.extra_cantiere (
          tenant_id, cantiere_id, sal_id, numero, titolo,
          descrizione, imponibile, iva_percentuale, data_scadenza
        ) values ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9)
        returning *
        """,
        tenant_id,
        cantiere_id,
        sal_id,
        int(numero),
        titolo.strip(),
        descrizione.strip(),
        _money(imponibile),
        Decimal(str(iva_percentuale)),
        data_scadenza,
    )
    return _d(row)


def _snapshot_hash(snapshot: dict) -> str:
    raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def genera_documento_economico(
    conn: asyncpg.Connection,
    tenant_id: str,
    cantiere_id: str,
    *,
    tipo: str,
    riferimento_id: str,
) -> dict:
    cantiere = await _require_cantiere(conn, tenant_id, cantiere_id)
    cantiere_documento = {
        "id": cantiere["id"],
        "cliente": cantiere.get("cliente_nome") or cantiere.get("cliente"),
        "indirizzo": cantiere.get("indirizzo"),
    }
    if tipo == "riepilogo_sal":
        row = await conn.fetchrow(
            """
            select s.*, coalesce(sum(r.importo_periodo), 0)::numeric(14,2) as totale
            from public.sal s
            left join public.sal_righe r
              on r.tenant_id = s.tenant_id and r.sal_id = s.id
            where s.tenant_id = $1::uuid and s.cantiere_id = $2::uuid
              and s.id = $3::uuid and s.stato in ('emesso', 'approvato')
            group by s.id
            """,
            tenant_id,
            cantiere_id,
            riferimento_id,
        )
        if not row:
            raise HTTPException(status_code=409, detail="Emetti il SAL prima della nota")
        sal = _d(row)
        snapshot = {
            "tipo": tipo,
            "cantiere": cantiere_documento,
            "sal": {
                "id": sal["id"],
                "numero": sal["numero"],
                "periodo_da": sal["periodo_da"],
                "periodo_a": sal["periodo_a"],
                "stato": sal["stato"],
                "totale": sal["totale"],
            },
        }
        sal_id, extra_id = riferimento_id, None
    elif tipo == "autorizzazione_extra":
        row = await conn.fetchrow(
            """
            select * from public.extra_cantiere
            where tenant_id = $1::uuid and cantiere_id = $2::uuid and id = $3::uuid
              and stato <> 'annullato'
            """,
            tenant_id,
            cantiere_id,
            riferimento_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Extra non trovato")
        extra = _d(row)
        snapshot = {
            "tipo": tipo,
            "cantiere": cantiere_documento,
            "extra": {
                "id": extra["id"],
                "numero": extra["numero"],
                "titolo": extra["titolo"],
                "descrizione": extra["descrizione"],
                "imponibile": extra["imponibile"],
                "iva_percentuale": extra["iva_percentuale"],
                "totale": extra["totale"],
                "data_scadenza": extra["data_scadenza"],
            },
        }
        sal_id, extra_id = None, riferimento_id
    else:
        raise HTTPException(status_code=400, detail="Tipo documento non valido")
    digest = _snapshot_hash(snapshot)
    if sal_id:
        row = await conn.fetchrow(
            """
            insert into public.documenti_economici (
              tenant_id, cantiere_id, tipo, sal_id, snapshot, documento_hash
            ) values ($1::uuid, $2::uuid, $3, $4::uuid, $5::jsonb, $6)
            on conflict (tenant_id, sal_id) where sal_id is not null do update
              set snapshot = excluded.snapshot, documento_hash = excluded.documento_hash
              where public.documenti_economici.stato = 'generato'
            returning *
            """,
            tenant_id,
            cantiere_id,
            tipo,
            sal_id,
            json.dumps(snapshot, default=str),
            digest,
        )
    else:
        row = await conn.fetchrow(
            """
            insert into public.documenti_economici (
              tenant_id, cantiere_id, tipo, extra_id, snapshot, documento_hash
            ) values ($1::uuid, $2::uuid, $3, $4::uuid, $5::jsonb, $6)
            on conflict (tenant_id, extra_id) where extra_id is not null do update
              set snapshot = excluded.snapshot, documento_hash = excluded.documento_hash
              where public.documenti_economici.stato = 'generato'
            returning *
            """,
            tenant_id,
            cantiere_id,
            tipo,
            extra_id,
            json.dumps(snapshot, default=str),
            digest,
        )
    if not row:
        raise HTTPException(status_code=409, detail="Documento già inviato o sottoscritto")
    row = await conn.fetchrow(
        """
        update public.documenti_economici set stato = 'inviato'
        where tenant_id = $1::uuid and id = $2::uuid
        returning *
        """,
        tenant_id,
        str(row["id"]),
    )
    if extra_id:
        await conn.execute(
            """
            update public.extra_cantiere set stato = 'inviato'
            where tenant_id = $1::uuid and id = $2::uuid and stato = 'bozza'
            """,
            tenant_id,
            extra_id,
        )
    return _d(row)


async def get_controllo_cantiere(
    conn: asyncpg.Connection, tenant_id: str, cantiere_id: str
) -> dict:
    cantiere = await _require_cantiere(conn, tenant_id, cantiere_id)
    piano = await conn.fetchrow(
        """
        select p.*, pr.numero as contratto_numero
        from public.piani_pagamento p
        join public.preventivi pr
          on pr.tenant_id = p.tenant_id and pr.id = p.preventivo_id
        where p.tenant_id = $1::uuid and p.cantiere_id = $2::uuid
          and p.stato <> 'completato'
        order by p.created_at desc limit 1
        """,
        tenant_id,
        cantiere_id,
    )
    rate = await conn.fetch(
        """
        select i.*, s.numero as sal_numero,
               coalesce(sum(pc.importo), 0)::numeric(14,2) as pagato,
               (i.importo - coalesce(sum(pc.importo), 0))::numeric(14,2) as residuo
        from public.incassi i
        left join public.sal s on s.tenant_id = i.tenant_id and s.id = i.sal_id
        left join public.pagamenti_cliente pc
          on pc.tenant_id = i.tenant_id and pc.incasso_id = i.id
        where i.tenant_id = $1::uuid and i.cantiere_id = $2::uuid
          and (i.piano_pagamento_id is not null or i.tipo_rata = 'extra')
        group by i.id, s.numero
        order by i.numero_rata, i.data_prevista, i.id
        """,
        tenant_id,
        cantiere_id,
    )
    extras = await conn.fetch(
        """
        select e.*, s.numero as sal_numero
        from public.extra_cantiere e
        left join public.sal s on s.tenant_id = e.tenant_id and s.id = e.sal_id
        where e.tenant_id = $1::uuid and e.cantiere_id = $2::uuid
        order by e.numero desc
        """,
        tenant_id,
        cantiere_id,
    )
    documents = await conn.fetch(
        """
        select d.*,
               coalesce(bool_or(f.decisione = 'sottoscritto'), false) as sottoscritto,
               max(f.created_at) as sottoscritto_at
        from public.documenti_economici d
        left join public.documenti_economici_firme f
          on f.tenant_id = d.tenant_id and f.documento_id = d.id
        where d.tenant_id = $1::uuid and d.cantiere_id = $2::uuid
        group by d.id
        order by d.created_at desc
        """,
        tenant_id,
        cantiere_id,
    )
    notifications = await conn.fetch(
        """
        select n.*, i.numero_rata, i.descrizione as rata_descrizione
        from public.notifiche_pagamento n
        join public.incassi i
          on i.tenant_id = n.tenant_id and i.id = n.incasso_id
        where n.tenant_id = $1::uuid and n.cantiere_id = $2::uuid
        order by n.programmata_per desc, n.created_at desc
        limit 100
        """,
        tenant_id,
        cantiere_id,
    )
    available_sal = await conn.fetch(
        """
        select s.id, s.numero, s.periodo_da, s.periodo_a, s.stato,
               coalesce(sum(r.importo_periodo), 0)::numeric(14,2) as totale
        from public.sal s
        left join public.sal_righe r
          on r.tenant_id = s.tenant_id and r.sal_id = s.id
        where s.tenant_id = $1::uuid and s.cantiere_id = $2::uuid
          and s.stato in ('emesso', 'approvato')
        group by s.id
        order by s.numero desc
        """,
        tenant_id,
        cantiere_id,
    )
    rate_out = [_d(row) for row in rate]
    extra_out = [_d(row) for row in extras]
    totale_contratto = float(piano["totale_contratto"]) if piano else 0.0
    extra_approvati = sum(
        float(row["totale"] or 0) for row in extras if row["stato"] == "approvato"
    )
    pagato = sum(float(row.get("pagato") or 0) for row in rate_out)
    dovuto = totale_contratto + extra_approvati
    return {
        "cantiere": cantiere,
        "piano": _d(piano),
        "rate": rate_out,
        "extra": extra_out,
        "documenti": [_d(row) for row in documents],
        "notifiche": [_d(row) for row in notifications],
        "sal_disponibili": [_d(row) for row in available_sal],
        "riepilogo": {
            "contratto": totale_contratto,
            "extra_approvati": round(extra_approvati, 2),
            "totale_commessa": round(dovuto, 2),
            "incassato": round(pagato, 2),
            "residuo": round(max(0, dovuto - pagato), 2),
            "scaduto": round(
                sum(
                    float(row.get("residuo") or 0)
                    for row in rate_out
                    if row.get("data_prevista") < date.today()
                    and row.get("stato") not in {"incassato", "annullato"}
                ),
                2,
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
