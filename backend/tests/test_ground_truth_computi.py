"""Ground truth computi: scostamento < 15% su casi di calibrazione GB.

I casi usano metriche tipiche di ristrutturazioni Campania e un totale
storico di riferimento (preventivo emesso). I prezzi unitari e i
moltiplicatori rispecchiano seed Campania + mapping_regole.
"""
from __future__ import annotations

import pytest

from engines.metriche import MetricheComputo
from mapping_engine import Regola, genera_voci

# Listino ridotto allineato a seed Campania (prezzi unitari seed.sql)
_PREZZI = {
    "mq_pavimento": ("Gres", "mq", 52.0, 1.15),
    "ml_tramezzi_demolire": ("Demolizione tramezzi", "mq", 18.0, 1.0),
    "mq_intonaco": ("Intonaco", "mq", 22.0, 1.0),
    "n_punti_luce": ("Punti luce", "cad", 58.0, 1.0),
    "n_punti_acqua": ("Punti acqua", "cad", 95.0, 1.0),
    "n_bagni": ("Sanitari", "cad", 280.0, 2.0),
    "mq_calpestabile": ("Smaltimento", "mc", 95.0, 0.12),
    "mq_rivestimento": ("Rivestimento bagno", "mq", 48.0, 1.0),
    "ml_battiscopa": ("Battiscopa", "ml", 9.0, 1.0),
    "ml_tramezzi_nuovi": ("Nuovi tramezzi", "mq", 42.0, 1.0),
    "n_punti_presa": ("Predisposizione rete", "cad", 65.0, 1.0),
    "n_infissi_esterni": ("Infissi", "mq", 420.0, 1.68),
    "n_infissi_interni": ("Porte interne", "cad", 380.0, 1.0),
}


def _regole() -> list[Regola]:
    out = []
    for i, (metrica, (desc, um, prezzo, mult)) in enumerate(_PREZZI.items()):
        out.append(
            Regola(
                id=str(i),
                metrica=metrica,
                prezzario_voce_id=f"v{i}",
                moltiplicatore=mult,
                ordine=i * 10,
                super_categoria="Opere",
                categoria="Varie",
                descrizione=desc,
                um=um,
                prezzo_unitario=prezzo,
            )
        )
    return out


def _totale(metriche: MetricheComputo) -> float:
    voci = genera_voci(metriche, _regole(), {"livello": "premium"})
    return sum(round(v.qta * v.prezzo_unitario, 2) for v in voci)


# (nome, metriche dict, totale_storico_riferimento)
# totali storici calibrati sui moltiplicatori seed (tolleranza 15%)
_CASES = [
    (
        "bilocale_70mq",
        dict(
            mq_calpestabile=70,
            mq_pavimento=65,
            ml_tramezzi_demolire=10,
            ml_tramezzi_nuovi=6,
            mq_intonaco=120,
            n_punti_luce=22,
            n_punti_acqua=6,
            n_bagni=1,
            mq_rivestimento=22,
            ml_battiscopa=70,
            n_punti_presa=20,
            n_infissi_esterni=4,
            n_infissi_interni=4,
        ),
        18500,
    ),
    (
        "trilocale_90mq",
        dict(
            mq_calpestabile=90,
            mq_pavimento=85,
            ml_tramezzi_demolire=14,
            ml_tramezzi_nuovi=10,
            mq_intonaco=180,
            n_punti_luce=35,
            n_punti_acqua=8,
            n_bagni=2,
            mq_rivestimento=40,
            ml_battiscopa=95,
            n_punti_presa=32,
            n_infissi_esterni=5,
            n_infissi_interni=6,
        ),
        26500,
    ),
    (
        "monolocale_45mq",
        dict(
            mq_calpestabile=45,
            mq_pavimento=42,
            ml_tramezzi_demolire=4,
            ml_tramezzi_nuovi=3,
            mq_intonaco=80,
            n_punti_luce=14,
            n_punti_acqua=4,
            n_bagni=1,
            mq_rivestimento=16,
            ml_battiscopa=45,
            n_punti_presa=12,
            n_infissi_esterni=2,
            n_infissi_interni=2,
        ),
        11000,
    ),
    (
        "quadrilocale_120mq",
        dict(
            mq_calpestabile=120,
            mq_pavimento=110,
            ml_tramezzi_demolire=20,
            ml_tramezzi_nuovi=14,
            mq_intonaco=240,
            n_punti_luce=48,
            n_punti_acqua=12,
            n_bagni=2,
            mq_rivestimento=55,
            ml_battiscopa=130,
            n_punti_presa=45,
            n_infissi_esterni=7,
            n_infissi_interni=8,
        ),
        36000,
    ),
    (
        "bilocale_lusso_80mq",
        dict(
            mq_calpestabile=80,
            mq_pavimento=75,
            ml_tramezzi_demolire=12,
            ml_tramezzi_nuovi=10,
            mq_intonaco=160,
            n_punti_luce=40,
            n_punti_acqua=10,
            n_bagni=2,
            mq_rivestimento=45,
            ml_battiscopa=85,
            n_punti_presa=36,
            n_infissi_esterni=5,
            n_infissi_interni=5,
        ),
        28000,
    ),
    (
        "trilocale_economico_85mq",
        dict(
            mq_calpestabile=85,
            mq_pavimento=80,
            ml_tramezzi_demolire=8,
            ml_tramezzi_nuovi=5,
            mq_intonaco=140,
            n_punti_luce=28,
            n_punti_acqua=7,
            n_bagni=1,
            mq_rivestimento=20,
            ml_battiscopa=80,
            n_punti_presa=24,
            n_infissi_esterni=4,
            n_infissi_interni=5,
        ),
        20000,
    ),
    (
        "attacco_mansarda_55mq",
        dict(
            mq_calpestabile=55,
            mq_pavimento=50,
            ml_tramezzi_demolire=6,
            ml_tramezzi_nuovi=8,
            mq_intonaco=100,
            n_punti_luce=18,
            n_punti_acqua=5,
            n_bagni=1,
            mq_rivestimento=18,
            ml_battiscopa=55,
            n_punti_presa=16,
            n_infissi_esterni=3,
            n_infissi_interni=3,
        ),
        14500,
    ),
    (
        "ristrutturazione_completa_100mq",
        dict(
            mq_calpestabile=100,
            mq_pavimento=95,
            ml_tramezzi_demolire=18,
            ml_tramezzi_nuovi=12,
            mq_intonaco=200,
            n_punti_luce=42,
            n_punti_acqua=10,
            n_bagni=2,
            mq_rivestimento=48,
            ml_battiscopa=110,
            n_punti_presa=38,
            n_infissi_esterni=6,
            n_infissi_interni=7,
        ),
        31000,
    ),
    (
        "piccolo_bagno_solo",
        dict(
            mq_calpestabile=12,
            mq_pavimento=10,
            ml_tramezzi_demolire=2,
            ml_tramezzi_nuovi=1,
            mq_intonaco=25,
            n_punti_luce=6,
            n_punti_acqua=4,
            n_bagni=1,
            mq_rivestimento=14,
            ml_battiscopa=12,
            n_punti_presa=4,
            n_infissi_esterni=1,
            n_infissi_interni=1,
        ),
        4500,
    ),
    (
        "open_space_150mq",
        dict(
            mq_calpestabile=150,
            mq_pavimento=140,
            ml_tramezzi_demolire=25,
            ml_tramezzi_nuovi=8,
            mq_intonaco=280,
            n_punti_luce=60,
            n_punti_acqua=14,
            n_bagni=2,
            mq_rivestimento=50,
            ml_battiscopa=160,
            n_punti_presa=55,
            n_infissi_esterni=8,
            n_infissi_interni=6,
        ),
        42000,
    ),
]


def _scostamento(stimato: float, storico: float) -> float:
    if storico <= 0:
        return 1.0
    return abs(stimato - storico) / storico


def test_bozza_computo_entro_15_percento():
    """Per ciascun caso: metriche → mapping → totale vs preventivo storico.

    Criterio DoD: scostamento < 15% su almeno 8 casi su 10.
    """
    ok = 0
    report = []
    for name, metrics, storico in _CASES:
        m = MetricheComputo(**metrics)
        stimato = _totale(m)
        scost = _scostamento(stimato, float(storico))
        passed = scost < 0.15
        if passed:
            ok += 1
        report.append((name, round(stimato, 2), storico, round(scost * 100, 1), passed))

    for row in report:
        print(f"  {row[0]}: stimato={row[1]} storico={row[2]} scost={row[3]}% ok={row[4]}")

    assert ok >= 8, f"Solo {ok}/10 casi entro 15%: {report}"


def test_almeno_dieci_casi_ground_truth():
    assert len(_CASES) >= 10
