"""Derivazioni deterministiche sul preventivo gia validato.

Tutto quello che sta qui e calcolato dalle voci: nessuna stima inventata,
nessuna scrittura su database. Serve al PDF e ai controlli pre-invio.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Iterable

from fasi_lavorazione import NOME_FASE, fasi_presenti, raggruppa_per_fase

# Politica commerciale di default: acconto alla firma, saldo alla consegna,
# quota restante ripartita sulle fasi in proporzione al loro peso economico.
ACCONTO_FIRMA_PERCENTUALE = Decimal("20")
SALDO_CONSEGNA_PERCENTUALE = Decimal("10")

_SPAZI = re.compile(r"\s+")

# Cosa il cliente NON sta comprando, dedotto dalle fasi assenti dal computo.
# Solo lavorazioni sensate per un intervento edilizio ordinario.
ESCLUSIONI_STANDARD: dict[int, str] = {
    15: "Demolizioni, rimozioni e opere di smontaggio non elencate",
    25: "Opere strutturali, murarie e di consolidamento",
    30: "Rifacimento di coperture e impermeabilizzazioni",
    35: "Rifacimento dell'impianto idrico-sanitario e degli scarichi",
    45: "Rifacimento dell'impianto elettrico e degli impianti speciali",
    55: "Impianto termico, di climatizzazione e ventilazione",
    60: "Massetti, sottofondi e isolamenti termo-acustici",
    65: "Intonaci, cartongessi e controsoffitti",
    70: "Fornitura e posa di pavimenti e rivestimenti",
    75: "Fornitura e posa di serramenti, porte e opere da vetraio",
    80: "Tinteggiature e finiture decorative",
    90: "Opere esterne, sistemazioni a verde e urbanizzazioni",
}

# Co-occorrenze attese: se c'e la fase scatenante deve esserci almeno una attesa.
REGOLE_COERENZA: tuple[dict[str, Any], ...] = (
    {
        "codice": "demolizioni_senza_smaltimento",
        "se_presente": (15,),
        "richiede": (95,),
        "messaggio": (
            "Ci sono demolizioni o rimozioni ma nessuna voce di trasporto e "
            "smaltimento in discarica."
        ),
    },
    {
        "codice": "impianti_senza_ripristini",
        "se_presente": (35, 45, 55),
        "richiede": (65,),
        "messaggio": (
            "Sono previsti impianti ma nessuna voce di intonaci o chiusura tracce: "
            "verifica i ripristini murari."
        ),
    },
    {
        "codice": "pavimenti_senza_massetto",
        "se_presente": (70,),
        "richiede": (60, 25),
        "messaggio": (
            "Sono previsti pavimenti ma nessun massetto o sottofondo: verifica il "
            "piano di posa."
        ),
    },
    {
        "codice": "serramenti_senza_ripristini",
        "se_presente": (75,),
        "richiede": (65, 25),
        "messaggio": (
            "Sono previsti serramenti ma nessuna opera muraria o di intonaco: "
            "verifica il ripristino di mazzette e davanzali."
        ),
    },
    {
        "codice": "lavori_senza_cantiere",
        "se_presente": (15, 25, 30, 70, 75),
        "richiede": (5,),
        "messaggio": (
            "Nessuna voce di allestimento cantiere o sicurezza a fronte di "
            "lavorazioni che la richiedono."
        ),
    },
    {
        "codice": "lavori_senza_pulizie",
        "se_presente": (15, 65, 70, 80),
        "richiede": (92,),
        "messaggio": "Nessuna voce di pulizia finale prima della consegna.",
    },
)


def _testo_chiave(valore: Any) -> str:
    return _SPAZI.sub(" ", str(valore or "").strip()).lower()


def _totale(voce: dict) -> float:
    if voce.get("totale") is not None:
        return round(float(voce["totale"]), 2)
    return round(float(voce.get("qta") or 0) * float(voce.get("prezzo_unitario") or 0), 2)


def aggrega_voci_gemelle(voci: Iterable[dict]) -> list[dict]:
    """Unisce le voci identiche per descrizione, unita e prezzo sommandone le quantita.

    ACCA esplode la stessa lavorazione per ogni ambiente: al cliente arriva una
    riga sola con il conteggio delle posizioni originali. Le voci di partenza non
    vengono modificate.
    """
    aggregate: list[dict] = []
    indice: dict[tuple[str, str, str, str], int] = {}
    for voce in voci:
        chiave = (
            _testo_chiave(voce.get("descrizione")),
            _testo_chiave(voce.get("um")),
            _testo_chiave(voce.get("sub_categoria")),
            f"{float(voce.get('prezzo_unitario') or 0):.2f}",
        )
        posizione = indice.get(chiave)
        if posizione is None:
            indice[chiave] = len(aggregate)
            aree = [str(voce["area"]).strip()] if voce.get("area") else []
            aggregate.append(
                {
                    **voce,
                    "qta": float(voce.get("qta") or 0),
                    "totale": _totale(voce),
                    "n_posizioni": 1,
                    "aree": aree,
                }
            )
            continue
        corrente = aggregate[posizione]
        area = str(voce.get("area") or "").strip()
        aggregate[posizione] = {
            **corrente,
            "qta": round(corrente["qta"] + float(voce.get("qta") or 0), 3),
            "totale": round(corrente["totale"] + _totale(voce), 2),
            "n_posizioni": corrente["n_posizioni"] + 1,
            "aree": (
                [*corrente["aree"], area]
                if area and area not in corrente["aree"]
                else corrente["aree"]
            ),
        }
    return aggregate


def esclusioni(voci: Iterable[dict]) -> list[str]:
    """Prestazioni non comprese, dedotte dalle fasi che il computo non contiene."""
    presenti = fasi_presenti(voci)
    return [
        testo for ordine, testo in ESCLUSIONI_STANDARD.items() if ordine not in presenti
    ]


def controlli_coerenza(voci: Iterable[dict]) -> list[dict]:
    """Avvisi non bloccanti sulle lavorazioni che di norma viaggiano insieme."""
    elenco = list(voci)
    if not elenco:
        return []
    presenti = fasi_presenti(elenco)
    avvisi: list[dict] = []
    for regola in REGOLE_COERENZA:
        scatenanti = [ordine for ordine in regola["se_presente"] if ordine in presenti]
        if not scatenanti:
            continue
        if any(ordine in presenti for ordine in regola["richiede"]):
            continue
        avvisi.append(
            {
                "codice": regola["codice"],
                "livello": "avviso",
                "messaggio": regola["messaggio"],
                "fasi_presenti": [NOME_FASE[ordine] for ordine in scatenanti],
                "fasi_attese": [NOME_FASE[ordine] for ordine in regola["richiede"]],
            }
        )
    return avvisi


def piano_pagamenti(
    voci: Iterable[dict],
    totale_documento: Any,
    *,
    acconto_percentuale: Decimal = ACCONTO_FIRMA_PERCENTUALE,
    saldo_percentuale: Decimal = SALDO_CONSEGNA_PERCENTUALE,
) -> list[dict]:
    """Milestone di pagamento: acconto, SAL a fine fase, saldo alla consegna.

    Le quote intermedie pesano quanto la fase corrispondente. L'ultima riga
    assorbe l'arrotondamento, cosi la somma coincide sempre con il totale.
    """
    totale = Decimal(str(totale_documento or 0)).quantize(Decimal("0.01"))
    gruppi = [gruppo for gruppo in raggruppa_per_fase(voci) if gruppo["totale"] > 0]
    if totale <= 0 or not gruppi:
        return []

    acconto = (totale * acconto_percentuale / 100).quantize(Decimal("0.01"))
    saldo = (totale * saldo_percentuale / 100).quantize(Decimal("0.01"))
    avanzamento = totale - acconto - saldo
    if avanzamento < 0:
        raise ValueError("Acconto e saldo non possono superare il totale del preventivo")

    imponibile_fasi = Decimal(str(sum(gruppo["totale"] for gruppo in gruppi)))
    rate: list[dict] = [
        {
            "riferimento": "Alla firma del contratto",
            "descrizione": "Acconto per avvio lavori e approvvigionamenti",
            "percentuale": float(acconto_percentuale),
            "importo": float(acconto),
        }
    ]
    distribuito = Decimal("0")
    for gruppo in gruppi:
        quota = (
            avanzamento * Decimal(str(gruppo["totale"])) / imponibile_fasi
        ).quantize(Decimal("0.01"))
        distribuito += quota
        rate.append(
            {
                "riferimento": f"A completamento: {gruppo['fase']}",
                "descrizione": "Stato avanzamento lavori",
                "percentuale": round(float(quota / totale * 100), 1),
                "importo": float(quota),
            }
        )
    residuo = saldo + (avanzamento - distribuito)
    rate.append(
        {
            "riferimento": "Alla consegna dei lavori",
            "descrizione": "Saldo finale dopo verifica e consegna",
            "percentuale": round(float(residuo / totale * 100), 1),
            "importo": float(residuo),
        }
    )
    return rate
