"""Contratti editabili, scelta pagamenti e fascicolo documentale cliente."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import asyncpg
from fastapi import HTTPException, UploadFile

from system_jobs.client_documents import download_document, upload_document
from system_jobs.client_invites import find_or_invite_user

PAYMENT_METHODS = {
    "sal": {
        "titolo": "Pagamento a Stato Avanzamento Lavori (SAL)",
        "sintesi": "25% all'accettazione e quote successive collegate all'avanzamento dei lavori.",
        "condizioni": [
            "25% all'accettazione del preventivo",
            "Pagamenti intermedi in base allo stato di avanzamento",
            "Il calendario definitivo viene concordato nel piano lavori",
        ],
    },
    "scaglionato_fisso": {
        "titolo": "Pagamento Scaglionato Fisso",
        "sintesi": "25% iniziale, quote durante i lavori e 25% finale dilazionato in 8 mesi.",
        "condizioni": [
            "25% all'accettazione del preventivo",
            "50% durante i lavori in due quote fisse del 25%",
            "25% finale suddiviso in 8 rate mensili",
        ],
    },
    "due_tranche": {
        "titolo": "Pagamento in Due Tranche",
        "sintesi": "50% all'accettazione e 50% entro 15 giorni dalla consegna dell'immobile.",
        "condizioni": [
            "50% all'accettazione del preventivo",
            "50% entro 15 giorni dalla consegna dell'immobile",
        ],
    },
}

GENERAL_PAYMENT_TERMS = [
    "Pagamenti tramite bonifico bancario alle coordinate indicate in fattura.",
    "Per ritardi superiori a 30 giorni possono applicarsi interessi del 5%, nei limiti di legge.",
    "Il mancato pagamento può comportare la sospensione delle prestazioni previa comunicazione scritta.",
]


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


def payment_options() -> list[dict]:
    return [{"tipo": key, **value} for key, value in PAYMENT_METHODS.items()]


def payment_snapshot(tipo: str, totale: Any) -> dict:
    if tipo not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="Modalità di pagamento non valida")
    total = Decimal(str(totale or 0)).quantize(Decimal("0.01"))
    if total <= 0:
        raise HTTPException(
            status_code=409, detail="Il preventivo non ha un totale valido"
        )

    def quota(percent: Decimal) -> float:
        return float((total * percent / Decimal("100")).quantize(Decimal("0.01")))

    if tipo == "sal":
        quarter = Decimal(str(quota(Decimal("25"))))
        rate = [
            {
                "riferimento": "All'accettazione",
                "descrizione": "Acconto",
                "percentuale": 25,
                "importo": float(quarter),
            },
            {
                "riferimento": "Durante i lavori",
                "descrizione": "SAL 1",
                "percentuale": 25,
                "importo": float(quarter),
            },
            {
                "riferimento": "Durante i lavori",
                "descrizione": "SAL 2",
                "percentuale": 25,
                "importo": float(quarter),
            },
            {
                "riferimento": "A ultimazione",
                "descrizione": "SAL finale",
                "percentuale": 25,
                "importo": float(total - quarter * 3),
            },
        ]
    elif tipo == "scaglionato_fisso":
        rate = [
            {
                "riferimento": "All'accettazione",
                "descrizione": "Acconto",
                "percentuale": 25,
                "importo": quota(Decimal("25")),
            },
            {
                "riferimento": "Durante i lavori",
                "descrizione": "Quota fissa 1",
                "percentuale": 25,
                "importo": quota(Decimal("25")),
            },
            {
                "riferimento": "Durante i lavori",
                "descrizione": "Quota fissa 2",
                "percentuale": 25,
                "importo": quota(Decimal("25")),
            },
        ]
        residuo = total - sum(Decimal(str(item["importo"])) for item in rate)
        mensile = (residuo / Decimal("8")).quantize(Decimal("0.01"))
        distribuito = Decimal("0")
        for index in range(1, 9):
            amount = mensile if index < 8 else residuo - distribuito
            distribuito += amount
            rate.append(
                {
                    "riferimento": f"Mese {index} dopo ultimazione",
                    "descrizione": "Quota saldo dilazionato",
                    "percentuale": 3.125,
                    "importo": float(amount),
                }
            )
    else:
        rate = [
            {
                "riferimento": "All'accettazione",
                "descrizione": "Prima tranche",
                "percentuale": 50,
                "importo": quota(Decimal("50")),
            },
            {
                "riferimento": "Entro 15 giorni dalla consegna",
                "descrizione": "Seconda tranche",
                "percentuale": 50,
                "importo": float(total - Decimal(str(quota(Decimal("50"))))),
            },
        ]
    return {
        "tipo": tipo,
        **PAYMENT_METHODS[tipo],
        "condizioni_generali": GENERAL_PAYMENT_TERMS,
        "totale": float(total),
        "rate": rate,
    }


def default_sections(preventivo: dict) -> list[dict]:
    numero = preventivo.get("numero") or "il preventivo allegato"
    totale = preventivo.get("totale_documento") or 0
    cantiere = (
        preventivo.get("cantiere_indirizzo")
        or preventivo.get("cliente_indirizzo")
        or "indirizzo da definire"
    )
    return [
        {
            "titolo": "ART. 1 — DICHIARAZIONI DELL'IMPRESA APPALTATRICE",
            "testo": "L'Appaltatrice dichiara di avere esaminato le opere, di disporre dell'organizzazione necessaria e di eseguirle a perfetta regola d'arte, nel rispetto degli elaborati approvati e della normativa vigente.",
        },
        {
            "titolo": "ART. 2 — CESSIONE, SUBAPPALTO E RISOLUZIONE",
            "testo": "È vietata la cessione del contratto. Il subappalto è ammesso nel rispetto della legge e previo consenso scritto della Committenza; l'Appaltatrice resta responsabile delle opere affidate.",
        },
        {
            "titolo": "ART. 3 — OSSERVANZA DI LEGGI E REGOLAMENTI",
            "testo": "Le opere sono soggette alle leggi, ai regolamenti e alle prescrizioni vigenti in materia edilizia, sicurezza, materiali, esecuzione, contabilizzazione e collaudo.",
        },
        {
            "titolo": "ART. 4 — TIPOLOGIA E OGGETTO DELL'APPALTO",
            "testo": f"L'appalto riguarda le lavorazioni del preventivo {numero} e del computo collegato, per l'intervento presso {cantiere}. Il totale contrattuale IVA inclusa è pari a euro {float(totale):,.2f}.",
        },
        {
            "titolo": "ART. 5 — VARIAZIONI AL PROGETTO",
            "testo": "Ogni variante, lavorazione extra o modifica quantitativa deve essere descritta, valorizzata e approvata per iscritto prima dell'esecuzione, con aggiornamento di importi e tempi.",
        },
        {
            "titolo": "ART. 6 — NUOVI PREZZI",
            "testo": "Per opere non previste sarà concordato preventivamente un nuovo prezzo, ricavato ove possibile dalle voci presenti o dal prezzario regionale vigente.",
        },
        {
            "titolo": "ART. 7 — OPERE IN ECONOMIA",
            "testo": "Le prestazioni in economia saranno preventivamente autorizzate e annotate con manodopera, materiali e noli impiegati.",
        },
        {
            "titolo": "ART. 8 — INVARIABILITÀ DEI PREZZI",
            "testo": "I prezzi restano fissi per lavorazioni e quantità indicate. Varianti, imprevisti non conoscibili e quantità eccedenti sono contabilizzati e approvati separatamente.",
        },
        {
            "titolo": "ART. 9 — CONSEGNA E PROGRAMMA DEI LAVORI",
            "testo": "L'avvio avverrà dopo disponibilità del cantiere, titoli abilitativi e verbale di consegna, secondo il programma lavori concordato.",
        },
        {
            "titolo": "ART. 10 — TERMINE E ULTIMAZIONE",
            "testo": "Tempi e proroghe sono definiti nel programma lavori. Il termine è sospeso per forza maggiore, condizioni incompatibili, ritardi autorizzativi, varianti o cause non imputabili all'Appaltatrice.",
        },
        {
            "titolo": "ART. 11 — DIREZIONE LAVORI",
            "testo": "I lavori sono coordinati con la Direzione Lavori nominata dalla Committenza e con i referenti tecnici indicati negli atti di cantiere.",
        },
        {
            "titolo": "ART. 12 — MATERIALI, ELABORATI E ATTREZZATURE",
            "testo": "Materiali e attrezzature devono essere idonei e conformi. Le approvazioni non esonerano l'Appaltatrice dalle responsabilità di qualità e corretta posa.",
        },
        {
            "titolo": "ART. 13 — CONDIZIONI DI PAGAMENTO",
            "testo": "Il pagamento avviene secondo la modalità scelta e confermata dal Committente nella propria area personale, riportata nel piano allegato al presente contratto.",
        },
        {
            "titolo": "ART. 14 — CAPITOLATO E ALLEGATI",
            "testo": f"Il preventivo {numero}, il computo metrico, il piano pagamenti e gli atti successivamente sottoscritti costituiscono parte integrante del contratto.",
        },
        {
            "titolo": "ART. 15 — ASSICURAZIONI E RESPONSABILITÀ",
            "testo": "L'Appaltatrice garantisce regolarità del personale, coperture previste dalla legge e responsabilità per i danni imputabili all'esecuzione delle proprie opere.",
        },
        {
            "titolo": "ART. 16 — SICUREZZA",
            "testo": "L'Appaltatrice osserva il D.Lgs. 81/2008 e le ulteriori disposizioni applicabili. La Committenza assicura l'accessibilità e comunica i rischi specifici noti.",
        },
        {
            "titolo": "ART. 17 — GARANZIE PER DIFETTI E VIZI",
            "testo": "Restano ferme le garanzie di legge. Vizi e difformità imputabili all'Appaltatrice, tempestivamente denunciati, saranno verificati e rimossi in tempi compatibili.",
        },
        {
            "titolo": "ART. 18 — CLAUSOLA RISOLUTIVA ESPRESSA",
            "testo": "Il grave inadempimento degli obblighi essenziali può determinare la risoluzione ai sensi dell'art. 1456 c.c., previa comunicazione scritta della parte adempiente.",
        },
        {
            "titolo": "ART. 19 — DISPOSIZIONI FINALI",
            "testo": "Per quanto non previsto si applicano il Codice Civile e la normativa vigente. La scrittura sarà registrata in caso d'uso.",
        },
        {
            "titolo": "ART. 20 — MANCATO PAGAMENTO E SOSPENSIONE",
            "testo": "Il ritardo oltre i termini concordati può comportare interessi nei limiti di legge e la sospensione dei lavori previa comunicazione scritta.",
        },
        {
            "titolo": "ART. 21 — VERBALI DI CONSEGNA E FINE LAVORI",
            "testo": "Avvio e ultimazione sono formalizzati con verbali che riportano stato delle opere, eventuali riserve e documentazione consegnata.",
        },
    ]


def validate_sections(sections: list[dict]) -> list[dict]:
    if not isinstance(sections, list) or not 1 <= len(sections) <= 80:
        raise HTTPException(
            status_code=422, detail="Il contratto deve contenere da 1 a 80 sezioni"
        )
    clean = []
    for index, section in enumerate(sections, 1):
        title = str(section.get("titolo") or "").strip()
        text = str(section.get("testo") or "").strip()
        if not title or len(title) > 250 or not text or len(text) > 12000:
            raise HTTPException(
                status_code=422, detail=f"Sezione {index} incompleta o troppo lunga"
            )
        clean.append({"titolo": title, "testo": text})
    return clean


async def _preventivo(
    conn: asyncpg.Connection, tenant_id: str, preventivo_id: str
) -> dict:
    row = await conn.fetchrow(
        """
        select p.*, coalesce(l.nome, cl.nome) as cliente_nome,
               coalesce(l.email, cl.email) as cliente_email,
               coalesce(l.telefono, cl.telefono) as cliente_telefono,
               coalesce(l.indirizzo, cl.indirizzo) as cliente_indirizzo,
               coalesce(l.citta, cl.citta) as cliente_citta,
               cl.cf as cliente_cf, cl.piva as cliente_piva,
               co.stato as computo_stato, ca.id as cantiere_id,
               coalesce(ca.indirizzo, l.indirizzo, cl.indirizzo) as cantiere_indirizzo
        from public.preventivi p
        left join public.leads l on l.id = p.lead_id and l.tenant_id = p.tenant_id
        left join public.clienti cl on cl.id = p.cliente_id and cl.tenant_id = p.tenant_id
        left join public.computi co on co.id = p.computo_id and co.tenant_id = p.tenant_id
        left join public.cantieri ca on ca.id = co.cantiere_id and ca.tenant_id = p.tenant_id
        where p.tenant_id = $1::uuid and p.id = $2::uuid
        """,
        tenant_id,
        preventivo_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")
    return _row(row)


async def invite_preventivo_client(
    conn, tenant_id: str, preventivo_id: str, *, email: str, nome: str | None
) -> dict:
    preventivo = await _preventivo(conn, tenant_id, preventivo_id)
    normalized = email.strip().lower()
    user, invited = await asyncio.to_thread(
        find_or_invite_user, normalized, nome, context="preventivo"
    )
    user_id = str(getattr(user, "id", "") or "")
    if not user_id:
        raise HTTPException(status_code=502, detail="Invito Supabase non completato")
    existing_role = await conn.fetchval(
        "select role from public.tenant_members where tenant_id=$1::uuid and user_id=$2::uuid",
        tenant_id,
        user_id,
    )
    if existing_role and str(existing_role) != "client":
        raise HTTPException(
            status_code=409, detail="L'email appartiene già a un membro interno"
        )
    await conn.execute(
        """insert into public.tenant_members (tenant_id,user_id,role,nome)
           values ($1::uuid,$2::uuid,'client',$3)
           on conflict (tenant_id,user_id) do update set nome=coalesce(excluded.nome,tenant_members.nome)""",
        tenant_id,
        user_id,
        (nome or preventivo.get("cliente_nome") or "").strip() or None,
    )
    row = await conn.fetchrow(
        """insert into public.preventivo_clienti (tenant_id,preventivo_id,user_id,email,nome,attivo)
           values ($1::uuid,$2::uuid,$3::uuid,$4,$5,true)
           on conflict (tenant_id,preventivo_id,user_id) do update
           set email=excluded.email,nome=coalesce(excluded.nome,preventivo_clienti.nome),attivo=true
           returning *""",
        tenant_id,
        preventivo_id,
        user_id,
        normalized,
        (nome or preventivo.get("cliente_nome") or "").strip() or None,
    )
    result = _row(row)
    result["invited"] = invited
    return result


async def get_editor(conn, tenant_id: str, preventivo_id: str) -> dict:
    preventivo = await _preventivo(conn, tenant_id, preventivo_id)
    contract = await conn.fetchrow(
        "select * from public.contratti where tenant_id=$1::uuid and preventivo_id=$2::uuid",
        tenant_id,
        preventivo_id,
    )
    clients = await conn.fetch(
        "select user_id,email,nome,attivo,created_at from public.preventivo_clienti where tenant_id=$1::uuid and preventivo_id=$2::uuid order by created_at",
        tenant_id,
        preventivo_id,
    )
    choice = await conn.fetchrow(
        """select sp.* from public.scelte_pagamento_cliente sp
           where sp.tenant_id=$1::uuid and sp.preventivo_id=$2::uuid and sp.stato='confermata'
           order by sp.confermata_at desc limit 1""",
        tenant_id,
        preventivo_id,
    )
    documents = await conn.fetch(
        """select * from public.documenti_cliente
           where tenant_id=$1::uuid and preventivo_id=$2::uuid
           order by created_at desc""",
        tenant_id,
        preventivo_id,
    )
    version = None
    if contract:
        version = await conn.fetchrow(
            """select * from public.contratto_versioni
               where tenant_id=$1::uuid and contratto_id=$2::uuid
               order by versione desc limit 1""",
            tenant_id,
            contract["id"],
        )
    sections = _json(version["sezioni"]) if version else default_sections(preventivo)
    return {
        "preventivo": preventivo,
        "contratto": _row(contract),
        "versione": _row(version),
        "sezioni": sections,
        "clienti": _rows(clients),
        "scelta_pagamento": _row(choice),
        "documenti": _rows(documents),
        "modalita_pagamento": payment_options(),
        "condizioni_generali": GENERAL_PAYMENT_TERMS,
    }


async def save_draft(
    conn, tenant_id: str, preventivo_id: str, sections: list[dict], actor_id: str
) -> dict:
    preventivo = await _preventivo(conn, tenant_id, preventivo_id)
    clean = validate_sections(sections)
    contract = await conn.fetchrow(
        """insert into public.contratti (tenant_id,preventivo_id,cantiere_id,numero,stato)
           values ($1::uuid,$2::uuid,$3::uuid,$4,'bozza')
           on conflict (tenant_id,preventivo_id) do update set stato='bozza', validato_at=null,
             validato_da=null, pubblicato_at=null
           returning *""",
        tenant_id,
        preventivo_id,
        preventivo.get("cantiere_id"),
        str(preventivo.get("numero") or "CONTRATTO").replace("PREV", "CTR", 1),
    )
    next_version = await conn.fetchval(
        "select coalesce(max(versione),0)+1 from public.contratto_versioni where tenant_id=$1::uuid and contratto_id=$2::uuid",
        tenant_id,
        contract["id"],
    )
    raw = json.dumps(clean, ensure_ascii=False, sort_keys=True).encode("utf-8")
    row = await conn.fetchrow(
        """insert into public.contratto_versioni
           (tenant_id,contratto_id,versione,stato,sezioni,pagamento_snapshot,contenuto_hash,created_by)
           values ($1::uuid,$2::uuid,$3,'bozza',$4::jsonb,'{}'::jsonb,$5,$6::uuid) returning *""",
        tenant_id,
        contract["id"],
        next_version,
        json.dumps(clean, ensure_ascii=False),
        hashlib.sha256(raw).hexdigest(),
        actor_id,
    )
    await conn.execute(
        "update public.contratti set versione_corrente=$3 where tenant_id=$1::uuid and id=$2::uuid",
        tenant_id,
        contract["id"],
        next_version,
    )
    return _row(row)


async def validate_contract(
    conn, tenant_id: str, preventivo_id: str, actor_id: str
) -> dict:
    preventivo = await _preventivo(conn, tenant_id, preventivo_id)
    if preventivo.get("computo_stato") != "confermato":
        raise HTTPException(
            status_code=409, detail="Conferma il computo prima di validare il contratto"
        )
    contract = await conn.fetchrow(
        "select * from public.contratti where tenant_id=$1::uuid and preventivo_id=$2::uuid for update",
        tenant_id,
        preventivo_id,
    )
    if not contract:
        raise HTTPException(
            status_code=409, detail="Salva prima una bozza del contratto"
        )
    draft = await conn.fetchrow(
        """select * from public.contratto_versioni where tenant_id=$1::uuid and contratto_id=$2::uuid
           order by versione desc limit 1""",
        tenant_id,
        contract["id"],
    )
    if not draft:
        raise HTTPException(
            status_code=409, detail="Salva prima una bozza del contratto"
        )
    choice = await conn.fetchrow(
        """select * from public.scelte_pagamento_cliente
           where tenant_id=$1::uuid and preventivo_id=$2::uuid and stato='confermata'
           order by confermata_at desc limit 1""",
        tenant_id,
        preventivo_id,
    )
    if not choice:
        raise HTTPException(
            status_code=409,
            detail="Il cliente deve prima confermare la modalità di pagamento nel portale",
        )
    snapshot = payment_snapshot(str(choice["tipo"]), preventivo.get("totale_documento"))
    next_version = int(draft["versione"]) + 1
    raw = json.dumps(
        {"sezioni": _json(draft["sezioni"]), "pagamento": snapshot},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    version = await conn.fetchrow(
        """insert into public.contratto_versioni
           (tenant_id,contratto_id,versione,stato,sezioni,pagamento_snapshot,contenuto_hash,created_by)
           values ($1::uuid,$2::uuid,$3,'validata',$4::jsonb,$5::jsonb,$6,$7::uuid) returning *""",
        tenant_id,
        contract["id"],
        next_version,
        json.dumps(_json(draft["sezioni"]), ensure_ascii=False),
        json.dumps(snapshot, ensure_ascii=False),
        hashlib.sha256(raw).hexdigest(),
        actor_id,
    )
    updated = await conn.fetchrow(
        """update public.contratti set stato='pubblicato',versione_corrente=$3,
             scelta_pagamento_id=$4::uuid,validato_da=$5::uuid,validato_at=now(),pubblicato_at=now()
           where tenant_id=$1::uuid and id=$2::uuid returning *""",
        tenant_id,
        contract["id"],
        next_version,
        choice["id"],
        actor_id,
    )
    await conn.execute(
        """insert into public.documenti_cliente
           (tenant_id,preventivo_id,cantiere_id,contratto_id,tipo,provenienza,stato,titolo,versione)
           values ($1::uuid,$2::uuid,$3::uuid,$4::uuid,'contratto','azienda','da_firmare',$5,$6)
           on conflict (tenant_id,contratto_id,versione) where tipo='contratto' and provenienza='azienda' and storage_path is null
           do update set stato='da_firmare',titolo=excluded.titolo""",
        tenant_id,
        preventivo_id,
        preventivo.get("cantiere_id"),
        contract["id"],
        f"Contratto {updated['numero']} - versione {next_version}",
        next_version,
    )
    return {"contratto": _row(updated), "versione": _row(version)}


async def validated_contract_payload(conn, tenant_id: str, preventivo_id: str) -> dict:
    preventivo = await _preventivo(conn, tenant_id, preventivo_id)
    row = await conn.fetchrow(
        """select c.*, cv.sezioni, cv.pagamento_snapshot, t.piva as tenant_piva
           from public.contratti c
           join public.contratto_versioni cv
             on cv.tenant_id=c.tenant_id and cv.contratto_id=c.id
            and cv.versione=c.versione_corrente and cv.stato='validata'
           join public.tenants t on t.id=c.tenant_id
           where c.tenant_id=$1::uuid and c.preventivo_id=$2::uuid
             and c.stato in ('validato','pubblicato','firmato')""",
        tenant_id,
        preventivo_id,
    )
    if not row:
        raise HTTPException(
            status_code=409,
            detail="Il contratto deve essere validato dopo la scelta del pagamento",
        )
    return {
        "preventivo": preventivo,
        "contratto": _row(row),
        "sezioni": _json(row["sezioni"]),
        "pagamento": _json(row["pagamento_snapshot"]),
        "tenant_piva": row["tenant_piva"],
    }


async def choose_payment(
    conn,
    tenant_id: str,
    preventivo_id: str,
    user_id: str,
    tipo: str,
    *,
    ip: str,
    user_agent: str | None,
) -> dict:
    if tipo not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="Modalità di pagamento non valida")
    total = await conn.fetchval(
        "select totale_documento from public.portale_preventivi_contratti where tenant_id=$1::uuid and preventivo_id=$2::uuid and user_id=$3::uuid",
        tenant_id,
        preventivo_id,
        user_id,
    )
    if total is None:
        raise HTTPException(
            status_code=404, detail="Preventivo non disponibile nel portale"
        )
    snapshot = payment_snapshot(tipo, total)
    row = await conn.fetchrow(
        """insert into public.scelte_pagamento_cliente
           (tenant_id,preventivo_id,user_id,tipo,stato,condizioni,confermata_at,ip,user_agent)
           values ($1::uuid,$2::uuid,$3::uuid,$4,'confermata',$5::jsonb,now(),$6::inet,$7)
           on conflict (tenant_id,preventivo_id,user_id) do update set
             tipo=excluded.tipo,stato='confermata',condizioni=excluded.condizioni,
             confermata_at=now(),ip=excluded.ip,user_agent=excluded.user_agent
           returning *""",
        tenant_id,
        preventivo_id,
        user_id,
        tipo,
        json.dumps(snapshot, ensure_ascii=False),
        ip,
        (user_agent or "")[:500] or None,
    )
    return _row(row)


async def portal_contract_data(conn, tenant_id: str) -> dict:
    quotes = await conn.fetch(
        "select * from public.portale_preventivi_contratti where tenant_id=$1::uuid order by numero_preventivo desc",
        tenant_id,
    )
    documents = await conn.fetch(
        """select * from public.documenti_cliente where tenant_id=$1::uuid
           order by created_at desc, id""",
        tenant_id,
    )
    return {
        "preventivi_contratti": _rows(quotes),
        "documenti_cliente": _rows(documents),
        "modalita_pagamento": payment_options(),
        "condizioni_generali_pagamento": GENERAL_PAYMENT_TERMS,
    }


async def register_upload(
    conn,
    tenant_id: str,
    user_id: str,
    file: UploadFile,
    *,
    tipo: str,
    titolo: str,
    preventivo_id: str | None,
    cantiere_id: str | None,
    originale_id: str | None,
    provenienza: str,
) -> dict:
    allowed = {
        "contratto",
        "sal",
        "fattura",
        "contabile_pagamento",
        "ricevuta",
        "extra",
        "verbale",
        "altro",
    }
    if tipo not in allowed:
        raise HTTPException(status_code=422, detail="Tipo documento non valido")
    content = await file.read(25 * 1024 * 1024 + 1)
    if not content or len(content) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Il documento deve essere compreso tra 1 byte e 25 MB",
        )
    mime = (file.content_type or "application/octet-stream").lower()
    allowed_mime = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    if mime not in allowed_mime:
        raise HTTPException(
            status_code=415,
            detail="Formato non supportato: usa PDF, immagini, Word o Excel",
        )
    if not preventivo_id and not cantiere_id:
        raise HTTPException(
            status_code=422, detail="Indica il preventivo o il cantiere"
        )
    if preventivo_id:
        access = await conn.fetchval(
            "select public.is_preventivo_client($1::uuid,$2::uuid) or public.is_internal_member($1::uuid)",
            tenant_id,
            preventivo_id,
        )
        if not access:
            raise HTTPException(status_code=403, detail="Preventivo non autorizzato")
    if cantiere_id:
        access = await conn.fetchval(
            "select public.is_cantiere_client($1::uuid,$2::uuid) or public.is_internal_member($1::uuid)",
            tenant_id,
            cantiere_id,
        )
        if not access:
            raise HTTPException(status_code=403, detail="Cantiere non autorizzato")
    if originale_id:
        original = await conn.fetchrow(
            """select id, preventivo_id, cantiere_id, stato
               from public.documenti_cliente
               where tenant_id=$1::uuid and id=$2::uuid""",
            tenant_id,
            originale_id,
        )
        same_reference = original and (
            (preventivo_id and str(original["preventivo_id"] or "") == preventivo_id)
            or (cantiere_id and str(original["cantiere_id"] or "") == cantiere_id)
        )
        if not same_reference or original["stato"] != "da_firmare":
            raise HTTPException(
                status_code=409,
                detail="Il documento originale non è firmabile o non appartiene alla pratica",
            )
    safe_name = "".join(
        ch if ch.isalnum() or ch in ".-_" else "-"
        for ch in (file.filename or "documento")
    )[:120]
    reference = (
        f"cantiere-{cantiere_id}" if cantiere_id else f"preventivo-{preventivo_id}"
    )
    path = f"{tenant_id}/{reference}/fascicolo-cliente/{uuid4()}-{safe_name}"
    await asyncio.to_thread(upload_document, path, content, mime)
    state = "caricato_firmato" if originale_id else "pubblicato"
    try:
        row = await conn.fetchrow(
            """insert into public.documenti_cliente
               (tenant_id,preventivo_id,cantiere_id,documento_originale_id,tipo,provenienza,stato,
                titolo,bucket,storage_path,nome_file,mime_type,dimensione,caricato_da)
               values ($1::uuid,$2::uuid,$3::uuid,$4::uuid,$5,$6,$7,$8,'documenti',$9,$10,$11,$12,$13::uuid)
               returning *""",
            tenant_id,
            preventivo_id,
            cantiere_id,
            originale_id,
            tipo,
            provenienza,
            state,
            titolo.strip(),
            path,
            file.filename or safe_name,
            mime,
            len(content),
            user_id,
        )
    except Exception:
        from system_jobs.client_documents import remove_document

        await asyncio.to_thread(remove_document, path)
        raise
    return _row(row)


async def document_download(
    conn, tenant_id: str, document_id: str
) -> tuple[bytes, str, str]:
    row = await conn.fetchrow(
        "select * from public.documenti_cliente where tenant_id=$1::uuid and id=$2::uuid",
        tenant_id,
        document_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Documento non disponibile")
    if not row["storage_path"]:
        raise HTTPException(
            status_code=409, detail="Documento generato: usa il download contratto"
        )
    content = await asyncio.to_thread(download_document, row["storage_path"])
    return (
        content,
        row["mime_type"] or "application/octet-stream",
        row["nome_file"] or "documento",
    )
