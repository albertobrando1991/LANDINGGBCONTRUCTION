"""Derivazioni sul preventivo: aggregazione, esclusioni, controlli, pagamenti."""

from __future__ import annotations

from decimal import Decimal

import preventivo_struttura as struttura


def _voce(descrizione, um, prezzo, qta, **extra):
    return {
        "descrizione": descrizione,
        "um": um,
        "prezzo_unitario": prezzo,
        "qta": qta,
        "totale": round(prezzo * qta, 2),
        **extra,
    }


def test_aggrega_le_voci_identiche_e_conserva_le_aree():
    voci = [
        _voce("Posa di pavimento in gres", "mq", 45.0, 12, area="Bagno"),
        _voce("posa di pavimento in gres", "mq", 45.0, 20, area="Cucina"),
        _voce("Posa di pavimento in gres", "mq", 52.0, 8, area="Camera"),
    ]
    aggregate = struttura.aggrega_voci_gemelle(voci)

    assert len(aggregate) == 2
    assert aggregate[0]["qta"] == 32
    assert aggregate[0]["totale"] == 1440.0
    assert aggregate[0]["n_posizioni"] == 2
    assert aggregate[0]["aree"] == ["Bagno", "Cucina"]
    assert aggregate[1]["n_posizioni"] == 1


def test_aggregazione_non_muta_le_voci_originali():
    originale = _voce("Tinteggiatura", "mq", 10.0, 5)
    struttura.aggrega_voci_gemelle([originale, dict(originale)])
    assert originale["qta"] == 5
    assert "n_posizioni" not in originale


def test_esclusioni_elenca_solo_le_fasi_assenti():
    voci = [{"fase": "Pavimenti e rivestimenti", "fase_ordine": 70, "totale": 100}]
    testi = struttura.esclusioni(voci)
    assert "Fornitura e posa di pavimenti e rivestimenti" not in testi
    assert "Rifacimento dell'impianto elettrico e degli impianti speciali" in testi


def test_controllo_segnala_demolizioni_senza_smaltimento():
    voci = [{"fase": "Demolizioni e rimozioni", "fase_ordine": 15, "totale": 500}]
    codici = [avviso["codice"] for avviso in struttura.controlli_coerenza(voci)]
    assert "demolizioni_senza_smaltimento" in codici


def test_controllo_tace_quando_la_fase_attesa_esiste():
    voci = [
        {"fase": "Demolizioni e rimozioni", "fase_ordine": 15, "totale": 500},
        {"fase": "Noli, trasporti e smaltimenti", "fase_ordine": 95, "totale": 200},
    ]
    codici = [avviso["codice"] for avviso in struttura.controlli_coerenza(voci)]
    assert "demolizioni_senza_smaltimento" not in codici


def test_controlli_su_computo_vuoto_non_producono_avvisi():
    assert struttura.controlli_coerenza([]) == []


def test_piano_pagamenti_somma_esattamente_il_totale():
    voci = [
        {"fase": "Demolizioni e rimozioni", "fase_ordine": 15, "totale": 3333.33},
        {"fase": "Pavimenti e rivestimenti", "fase_ordine": 70, "totale": 6666.67},
    ]
    rate = struttura.piano_pagamenti(voci, 10000)

    assert len(rate) == 4
    assert rate[0]["riferimento"] == "Alla firma del contratto"
    assert rate[0]["importo"] == 2000.0
    assert rate[1]["riferimento"] == "A completamento: Demolizioni e rimozioni"
    assert rate[-1]["riferimento"] == "Alla consegna dei lavori"
    assert round(sum(rata["importo"] for rata in rate), 2) == 10000.0


def test_piano_pagamenti_assorbe_gli_arrotondamenti_nel_saldo():
    voci = [
        {"fase": "Demolizioni e rimozioni", "fase_ordine": 15, "totale": 33.33},
        {
            "fase": "Intonaci, cartongesso e controsoffitti",
            "fase_ordine": 65,
            "totale": 33.33,
        },
        {"fase": "Pavimenti e rivestimenti", "fase_ordine": 70, "totale": 33.34},
    ]
    rate = struttura.piano_pagamenti(voci, Decimal("100.00"))
    assert round(sum(rata["importo"] for rata in rate), 2) == 100.0


def test_piano_pagamenti_vuoto_senza_importo():
    assert struttura.piano_pagamenti([], 0) == []
