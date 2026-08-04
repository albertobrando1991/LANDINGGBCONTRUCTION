"""Ponte deterministico: metriche AI → voci di computo via prezzario.
L'AI non produce prezzi. I prezzi arrivano solo dal prezzario.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import asyncpg
from fastapi import HTTPException

from engines.metriche import MetricheComputo, assert_nessun_prezzo, estrai_metriche


@dataclass
class Regola:
    id: str
    metrica: str
    prezzario_voce_id: str
    moltiplicatore: float = 1.0
    condizione: Optional[dict] = None
    ordine: int = 0
    # snapshot fields from prezzario voce (joined at load time)
    super_categoria: str = ""
    categoria: str = ""
    sub_categoria: Optional[str] = None
    descrizione: str = ""
    um: str = "cad"
    tipo: str = "a_misura"
    prezzo_unitario: float = 0.0


@dataclass
class VoceComputo:
    origine_voce_id: str
    super_categoria: str
    categoria: str
    sub_categoria: Optional[str]
    descrizione: str
    um: str
    tipo: str
    qta: float
    prezzo_unitario: float
    ordine: int
    generata_da_ai: bool = True
    validata_umano: bool = False
    metrica: str = ""


def _condizione_ok(condizione: Optional[dict], config_lead: dict) -> bool:
    if not condizione:
        return True
    for key, expected in condizione.items():
        actual = config_lead.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def genera_voci(
    metriche: MetricheComputo,
    regole: list[Regola],
    config_lead: dict,
) -> list[VoceComputo]:
    """Puro, deterministico, senza I/O."""
    assert_nessun_prezzo(metriche)
    data = metriche.model_dump()
    out: list[VoceComputo] = []
    sorted_regole = sorted(regole, key=lambda r: (r.ordine, r.super_categoria or ""))
    for regola in sorted_regole:
        if not _condizione_ok(regola.condizione, config_lead or {}):
            continue
        raw = data.get(regola.metrica)
        if raw is None:
            continue
        try:
            base = float(raw)
        except (TypeError, ValueError):
            continue
        qta = base * float(regola.moltiplicatore)
        if qta <= 0:
            continue
        out.append(
            VoceComputo(
                origine_voce_id=regola.prezzario_voce_id,
                super_categoria=regola.super_categoria,
                categoria=regola.categoria,
                sub_categoria=regola.sub_categoria,
                descrizione=regola.descrizione,
                um=regola.um,
                tipo=regola.tipo,
                qta=round(qta, 3),
                prezzo_unitario=float(regola.prezzo_unitario),
                ordine=regola.ordine,
                metrica=regola.metrica,
            )
        )
    out.sort(key=lambda v: (v.ordine, v.super_categoria, v.descrizione))
    return out


async def carica_regole(
    conn: asyncpg.Connection, tenant_id: str, prezzario_id: Optional[str] = None
) -> list[Regola]:
    if prezzario_id:
        # Le regole sono stabili e puntano alle voci regionali. Per un listino
        # duplicato risolviamo la voce equivalente per codice, così il ponte AI
        # usa davvero descrizione e prezzo personalizzati. Se una voce manca,
        # il riferimento regionale resta un fallback esplicito e deterministico.
        rows = await conn.fetch(
            """
            select r.id, r.metrica,
                   coalesce(target.id, source.id) as prezzario_voce_id,
                   r.moltiplicatore, r.condizione, r.ordine,
                   coalesce(target.super_categoria, source.super_categoria) as super_categoria,
                   coalesce(target.categoria, source.categoria) as categoria,
                   coalesce(target.sub_categoria, source.sub_categoria) as sub_categoria,
                   coalesce(target.descrizione, source.descrizione) as descrizione,
                   coalesce(target.um, source.um) as um,
                   coalesce(target.tipo, source.tipo) as tipo,
                   coalesce(target.prezzo_unitario, source.prezzo_unitario) as prezzo_unitario
            from public.mapping_regole r
            join public.prezzario_voci source on source.id = r.prezzario_voce_id
            left join lateral (
              select candidate.*
              from public.prezzario_voci candidate
              where candidate.tenant_id = r.tenant_id
                and candidate.prezzario_id = $2::uuid
                and candidate.codice = source.codice
                and candidate.attiva = true
              order by candidate.id
              limit 1
            ) target on true
            where r.tenant_id = $1::uuid and r.attiva = true
            order by r.ordine
            """,
            tenant_id,
            prezzario_id,
        )
    else:
        rows = await conn.fetch(
            """
            select r.id, r.metrica, r.prezzario_voce_id, r.moltiplicatore,
                   r.condizione, r.ordine, v.super_categoria, v.categoria,
                   v.sub_categoria, v.descrizione, v.um, v.tipo, v.prezzo_unitario
            from public.mapping_regole r
            join public.prezzario_voci v on v.id = r.prezzario_voce_id
            where r.tenant_id = $1::uuid and r.attiva = true
            order by r.ordine
            """,
            tenant_id,
        )
    regole = []
    for r in rows:
        regole.append(
            Regola(
                id=str(r["id"]),
                metrica=r["metrica"],
                prezzario_voce_id=str(r["prezzario_voce_id"]),
                moltiplicatore=float(r["moltiplicatore"]),
                condizione=r["condizione"] if isinstance(r["condizione"], dict) else None,
                ordine=int(r["ordine"] or 0),
                super_categoria=r["super_categoria"],
                categoria=r["categoria"],
                sub_categoria=r["sub_categoria"],
                descrizione=r["descrizione"],
                um=r["um"],
                tipo=r["tipo"],
                prezzo_unitario=float(r["prezzo_unitario"] or 0),
            )
        )
    return regole


async def genera_computo_da_ai(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    metriche: Optional[MetricheComputo] = None,
    analisi_ai: Optional[dict] = None,
    lead_id: Optional[str] = None,
    config_lead: Optional[dict] = None,
    prezzario_id: Optional[str] = None,
) -> dict:
    """Orchestrazione: metriche + regole → computo ai_da_revisionare."""
    if metriche is None:
        if not analisi_ai:
            raise HTTPException(status_code=400, detail="Metriche o analisi AI richieste")
        metriche = estrai_metriche(analisi_ai)

    if not prezzario_id:
        prezzario_id = await conn.fetchval(
            """
            select id from public.prezzari
            where tenant_id = $1::uuid and is_default = true
            limit 1
            """,
            tenant_id,
        )
    if not prezzario_id:
        raise HTTPException(status_code=404, detail="Nessun prezzario di default per il tenant")

    cfg = config_lead or {}
    if lead_id and not cfg:
        lead = await conn.fetchrow(
            "select config from public.leads where id = $1::uuid and tenant_id = $2::uuid",
            lead_id,
            tenant_id,
        )
        if lead and isinstance(lead["config"], dict):
            cfg = lead["config"]

    regole = await carica_regole(conn, tenant_id, str(prezzario_id))
    voci = genera_voci(metriche, regole, cfg)

    computo_id = await conn.fetchval(
        """
        insert into public.computi (tenant_id, lead_id, prezzario_id, tipo, stato, note)
        values ($1::uuid, $2::uuid, $3::uuid, 'estimativo', 'ai_da_revisionare',
                'Bozza generata da AI — validazione umana obbligatoria')
        returning id
        """,
        tenant_id,
        lead_id,
        prezzario_id,
    )

    for i, v in enumerate(voci):
        await conn.execute(
            """
            insert into public.computo_voci (
              tenant_id, computo_id, origine_voce_id, ordine,
              super_categoria, categoria, sub_categoria, descrizione, um, tipo,
              qta, prezzo_unitario, generata_da_ai, validata_umano
            ) values (
              $1::uuid, $2::uuid, $3::uuid, $4,
              $5, $6, $7, $8, $9, $10,
              $11, $12, true, false
            )
            """,
            tenant_id,
            computo_id,
            v.origine_voce_id,
            v.ordine or i * 10,
            v.super_categoria,
            v.categoria,
            v.sub_categoria,
            v.descrizione,
            v.um,
            v.tipo,
            v.qta,
            v.prezzo_unitario,
        )

    totale = await conn.fetchval(
        "select totale from public.computi_totali where computo_id = $1",
        computo_id,
    )
    return {
        "id": str(computo_id),
        "stato": "ai_da_revisionare",
        "n_voci": len(voci),
        "totale": float(totale or 0),
        "metriche": metriche.model_dump(),
    }
