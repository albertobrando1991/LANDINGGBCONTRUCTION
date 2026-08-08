"""Stima della durata dei lavori a partire dal peso economico di ogni fase.

Modello volutamente semplice e ispezionabile: ogni fase ha un valore
giornaliero di lavorazione (euro di importo che una squadra tipo produce in una
giornata) e un minimo di presidio. Niente date, niente festivita, niente
calendario: si ragiona in giorni lavorativi e in scostamenti cumulati, cosi la
stima resta valida qualunque sia la data di avvio.
"""
from __future__ import annotations

import math
from typing import Iterable

from fasi_lavorazione import raggruppa_per_fase

GIORNI_SETTIMANA = 5

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

# Fasi che non occupano il cantiere: corrono insieme alle lavorazioni.
FASI_SENZA_DURATA = frozenset({95, 96, 97})

# Impianti diversi lavorano in contemporanea sullo stesso cantiere.
GRUPPI_PARALLELI: dict[int, str] = {35: "impianti", 40: "impianti", 45: "impianti"}


def giorni_fase(fase_ordine: int, importo: float) -> int:
    if fase_ordine in FASI_SENZA_DURATA:
        return 0
    valore = VALORE_GIORNALIERO.get(fase_ordine, VALORE_GIORNALIERO[99])
    minimo = GIORNI_MINIMI.get(fase_ordine, GIORNI_MINIMI_DEFAULT)
    return max(minimo, math.ceil(float(importo or 0) / valore))


def stima(voci: Iterable[dict]) -> dict:
    """Blocchi in sequenza, con inizio e fine in giorni lavorativi dall'avvio."""
    gruppi = [gruppo for gruppo in raggruppa_per_fase(voci) if gruppo["totale"] > 0]
    blocchi: list[dict] = []
    cursore = 0
    indice = 0

    while indice < len(gruppi):
        chiave = GRUPPI_PARALLELI.get(gruppi[indice]["fase_ordine"])
        insieme = [gruppi[indice]]
        while (
            chiave
            and indice + len(insieme) < len(gruppi)
            and GRUPPI_PARALLELI.get(gruppi[indice + len(insieme)]["fase_ordine"])
            == chiave
        ):
            insieme.append(gruppi[indice + len(insieme)])

        durate = [giorni_fase(g["fase_ordine"], g["totale"]) for g in insieme]
        for gruppo, giorni in zip(insieme, durate):
            blocchi.append(
                {
                    "fase": gruppo["fase"],
                    "fase_ordine": gruppo["fase_ordine"],
                    "importo": gruppo["totale"],
                    "giorni": giorni,
                    "inizio": cursore if giorni else 0,
                    "fine": (cursore + giorni) if giorni else 0,
                    "parallela": len(insieme) > 1,
                    "continuativa": giorni == 0,
                }
            )
        cursore += max(durate) if durate else 0
        indice += len(insieme)

    return {
        "blocchi": blocchi,
        "giorni_totali": cursore,
        "settimane": round(cursore / GIORNI_SETTIMANA, 1) if cursore else 0.0,
        "unita": "giorni lavorativi",
    }
