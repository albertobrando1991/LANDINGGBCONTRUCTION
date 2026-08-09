"""Cronoprogramma tecnico per ristrutturazioni residenziali.

La durata non puo dipendere soltanto dall'importo: materiali costosi non
richiedono necessariamente piu manodopera, mentre coordinamento delle squadre e
tempi di maturazione occupano il calendario anche senza produrre valore. Il
modello combina quindi superficie, complessita delle fasi, produttivita
economica, sovrapposizioni parziali e attese tecniche.
"""
from __future__ import annotations

import math
from typing import Iterable

from fasi_lavorazione import raggruppa_per_fase

GIORNI_SETTIMANA = 5
GIORNI_MESE_MEDIO = 21.7

# Euro di importo prodotti in una giornata da una squadra tipo di due persone.
# Valori piu alti dove il materiale pesa molto sul prezzo (serramenti, termico),
# piu bassi dove il costo e quasi tutto manodopera (demolizioni, pittura).
VALORE_GIORNALIERO: dict[int, float] = {
    5: 1500.0,   # allestimento cantiere e sicurezza
    10: 1500.0,  # indagini e diagnostica
    15: 700.0,   # demolizioni e rimozioni
    20: 1400.0,  # scavi (mezzo meccanico)
    25: 900.0,   # strutture e opere murarie
    30: 1100.0,  # coperture e impermeabilizzazioni
    35: 800.0,   # idrico-sanitario
    40: 1000.0,  # antincendio
    45: 800.0,   # elettrico e speciali
    50: 3000.0,  # ascensori
    55: 1500.0,  # termico e climatizzazione
    60: 1200.0,  # massetti e sottofondi
    65: 900.0,   # intonaci e cartongesso
    70: 1200.0,  # pavimenti e rivestimenti
    75: 2500.0,  # serramenti
    80: 700.0,   # tinteggiature e finiture
    85: 500.0,   # restauro artistico
    90: 1000.0,  # opere esterne
    92: 1500.0,  # pulizie e consegna
    99: 1000.0,  # da classificare
}

GIORNI_MINIMI: dict[int, int] = {5: 1, 10: 1, 92: 1}
GIORNI_MINIMI_DEFAULT = 2

# Durate operative di riferimento per una ristrutturazione completa di 100 mq.
# Il profilo porta un cantiere standard, comprensivo delle attese tecniche, a
# circa 18-21 settimane (4-5 mesi). Per lavori parziali resta prevalente la
# produttivita economica e non viene applicato il profilo completo.
GIORNI_RIFERIMENTO_100_MQ: dict[int, int] = {
    5: 2,
    10: 2,
    15: 8,
    20: 8,
    25: 15,
    30: 10,
    35: 16,
    40: 6,
    45: 16,
    50: 12,
    55: 12,
    60: 8,
    65: 10,
    70: 12,
    75: 6,
    80: 10,
    85: 20,
    90: 12,
    92: 5,
    99: 5,
}

MATURAZIONE_MASSETTO_TRADIZIONALE = 20  # 28 giorni di calendario circa
MATURAZIONE_MASSETTO_RAPIDO = 3
COEFFICIENTE_IMPIANTI_COORDINATI = 0.45

# Fasi che non occupano il cantiere: corrono insieme alle lavorazioni.
FASI_SENZA_DURATA = frozenset({95, 96, 97})

# Impianti diversi lavorano in contemporanea sullo stesso cantiere.
GRUPPI_PARALLELI: dict[int, str] = {
    35: "impianti",
    40: "impianti",
    45: "impianti",
    55: "impianti",
}


def _fattore_superficie(superficie_mq: float) -> float:
    # La durata cresce meno che linearmente: su superfici maggiori aumentano
    # anche parallelismo e dimensione della squadra.
    return min(1.8, max(0.35, (float(superficie_mq) / 100.0) ** 0.65))


def _superficie_dalle_voci(voci: list[dict]) -> float | None:
    """Stima i mq calpestabili dalle quantita, senza usare pitture o pareti."""
    pavimenti: list[float] = []
    massetti: list[float] = []
    demolizioni: list[float] = []
    for voce in voci:
        um = str(voce.get("um") or "").strip().lower().replace("²", "2")
        if um not in {"mq", "m2"}:
            continue
        try:
            qta = float(voce.get("qta") or 0)
        except (TypeError, ValueError):
            continue
        if not 2 <= qta <= 300:
            continue
        ordine = int(voce.get("fase_ordine") or 99)
        testo = str(voce.get("descrizione") or "").lower()
        if ordine == 70 and not any(
            parola in testo for parola in ("rivestiment", "parete", "murale")
        ):
            pavimenti.append(qta)
        elif ordine == 60 and any(
            parola in testo for parola in ("masset", "sottofond", "caldana")
        ):
            massetti.append(qta)
        elif ordine == 15 and "paviment" in testo:
            demolizioni.append(qta)

    if pavimenti:
        # Le voci possono essere divise per ambiente: la somma e piu utile del
        # massimo, con un tetto che intercetta eventuali strati duplicati.
        return min(250.0, sum(pavimenti))
    if massetti:
        return min(250.0, max(massetti))
    if demolizioni:
        return min(250.0, max(demolizioni))
    return None


def _ristrutturazione_completa(gruppi: list[dict]) -> bool:
    presenti = {int(gruppo["fase_ordine"]) for gruppo in gruppi}
    indicatori = (
        15 in presenti,
        25 in presenti,
        len(presenti.intersection({35, 45, 55})) >= 2,
        bool(presenti.intersection({60, 65})),
        70 in presenti,
        80 in presenti,
    )
    return sum(indicatori) >= 5


def _massetto_rapido(voci: list[dict]) -> bool:
    parole = ("asciugamento rapido", "presa rapida", "mapecem", "topcem")
    pertinenti = [
        str(voce.get("descrizione") or "").lower()
        for voce in voci
        if int(voce.get("fase_ordine") or 99) == 60
    ]
    return bool(pertinenti) and any(
        parola in descrizione for descrizione in pertinenti for parola in parole
    )


def giorni_fase(
    fase_ordine: int,
    importo: float,
    *,
    superficie_mq: float | None = None,
) -> int:
    if fase_ordine in FASI_SENZA_DURATA:
        return 0
    valore = VALORE_GIORNALIERO.get(fase_ordine, VALORE_GIORNALIERO[99])
    minimo = GIORNI_MINIMI.get(fase_ordine, GIORNI_MINIMI_DEFAULT)
    if superficie_mq:
        riferimento = GIORNI_RIFERIMENTO_100_MQ.get(
            fase_ordine, GIORNI_RIFERIMENTO_100_MQ[99]
        )
        minimo = max(minimo, math.ceil(riferimento * _fattore_superficie(superficie_mq)))
    return max(minimo, math.ceil(float(importo or 0) / valore))


def stima(voci: Iterable[dict], *, superficie_mq: float | None = None) -> dict:
    """Blocchi in sequenza con impianti coordinati e maturazioni esplicite."""
    elenco_voci = list(voci)
    gruppi = [
        gruppo for gruppo in raggruppa_per_fase(elenco_voci) if gruppo["totale"] > 0
    ]
    completa = _ristrutturazione_completa(gruppi)
    superficie = float(superficie_mq or 0) or _superficie_dalle_voci(elenco_voci)
    if not superficie and completa:
        totale = sum(float(gruppo["totale"]) for gruppo in gruppi)
        superficie = min(180.0, max(50.0, totale / 1000.0)) if totale else 100.0

    blocchi: list[dict] = []
    cursore = 0
    indice = 0
    fine_massetto: int | None = None
    attesa_richiesta = (
        MATURAZIONE_MASSETTO_RAPIDO
        if _massetto_rapido(elenco_voci)
        else MATURAZIONE_MASSETTO_TRADIZIONALE
    )
    giorni_attesa = 0

    def aggiungi_attesa_se_necessaria(prossimo_ordine: int) -> None:
        nonlocal cursore, giorni_attesa, fine_massetto
        if fine_massetto is None or prossimo_ordine < 70:
            return
        trascorsi = cursore - fine_massetto
        residui = max(0, attesa_richiesta - trascorsi)
        if residui:
            blocchi.append(
                {
                    "fase": "Maturazione e asciugatura dei supporti",
                    "fase_ordine": 69,
                    "importo": 0.0,
                    "giorni": residui,
                    "inizio": cursore,
                    "fine": cursore + residui,
                    "parallela": False,
                    "continuativa": False,
                    "tecnica": True,
                }
            )
            cursore += residui
            giorni_attesa += residui
        fine_massetto = None

    while indice < len(gruppi):
        aggiungi_attesa_se_necessaria(int(gruppi[indice]["fase_ordine"]))
        chiave = GRUPPI_PARALLELI.get(gruppi[indice]["fase_ordine"])
        insieme = [gruppi[indice]]
        while (
            chiave
            and indice + len(insieme) < len(gruppi)
            and GRUPPI_PARALLELI.get(gruppi[indice + len(insieme)]["fase_ordine"])
            == chiave
        ):
            insieme.append(gruppi[indice + len(insieme)])

        durate = [
            giorni_fase(
                g["fase_ordine"],
                g["totale"],
                superficie_mq=superficie if (completa or superficie_mq) else None,
            )
            for g in insieme
        ]
        durata_insieme = max(durate, default=0)
        if chiave and len(insieme) > 1:
            durata_insieme = max(
                durata_insieme,
                math.ceil(sum(durate) * COEFFICIENTE_IMPIANTI_COORDINATI),
            )
        for posizione, (gruppo, giorni) in enumerate(zip(insieme, durate)):
            slittamento = 0
            if len(insieme) > 1 and durata_insieme > giorni:
                slittamento = round(
                    (durata_insieme - giorni) * posizione / (len(insieme) - 1)
                )
            inizio = cursore + slittamento
            blocchi.append(
                {
                    "fase": gruppo["fase"],
                    "fase_ordine": gruppo["fase_ordine"],
                    "importo": gruppo["totale"],
                    "giorni": giorni,
                    "inizio": inizio if giorni else 0,
                    "fine": (inizio + giorni) if giorni else 0,
                    "parallela": len(insieme) > 1,
                    "continuativa": giorni == 0,
                    "tecnica": False,
                }
            )
        cursore += durata_insieme
        if any(int(gruppo["fase_ordine"]) == 60 for gruppo in insieme):
            fine_massetto = cursore
        indice += len(insieme)

    aggiungi_attesa_se_necessaria(100)

    return {
        "blocchi": blocchi,
        "giorni_totali": cursore,
        "settimane": round(cursore / GIORNI_SETTIMANA, 1) if cursore else 0.0,
        "mesi": round(cursore / GIORNI_MESE_MEDIO, 1) if cursore else 0.0,
        "giorni_attesa_tecnica": giorni_attesa,
        "superficie_stimata_mq": round(superficie, 1) if superficie else None,
        "profilo": "ristrutturazione_completa" if completa else "intervento_parziale",
        "unita": "giorni lavorativi",
    }
