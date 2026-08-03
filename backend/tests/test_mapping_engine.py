"""Test puri sul ponte metriche → voci (nessun DB, nessun LLM)."""
from mapping_engine import Regola, genera_voci
from engines.metriche import MetricheComputo, estrai_metriche, assert_nessun_prezzo
import pytest


def test_genera_voci_base():
    m = MetricheComputo(mq_pavimento=100, n_punti_luce=50, mq_calpestabile=100)
    regole = [
        Regola(
            id="1",
            metrica="mq_pavimento",
            prezzario_voce_id="v1",
            moltiplicatore=1.15,
            ordine=10,
            super_categoria="Finiture",
            categoria="Pavimenti",
            descrizione="Gres",
            um="mq",
            prezzo_unitario=52,
        ),
        Regola(
            id="2",
            metrica="n_punti_luce",
            prezzario_voce_id="v2",
            moltiplicatore=1.0,
            ordine=20,
            super_categoria="Impianti",
            categoria="Elettrico",
            descrizione="Punto luce",
            um="cad",
            prezzo_unitario=58,
        ),
    ]
    voci = genera_voci(m, regole, {"livello": "premium"})
    assert len(voci) == 2
    assert voci[0].qta == pytest.approx(115.0)
    assert voci[0].prezzo_unitario == 52
    assert voci[1].qta == 50


def test_condizione_filtra():
    m = MetricheComputo(mq_pavimento=80)
    regole = [
        Regola(
            id="1",
            metrica="mq_pavimento",
            prezzario_voce_id="v1",
            moltiplicatore=1.0,
            condizione={"livello": ["luxury"]},
            ordine=1,
            descrizione="Parquet",
            prezzo_unitario=100,
            super_categoria="F",
            categoria="P",
            um="mq",
        )
    ]
    assert genera_voci(m, regole, {"livello": "premium"}) == []
    assert len(genera_voci(m, regole, {"livello": "luxury"})) == 1


def test_nessun_importo_dalle_metriche():
    m = MetricheComputo(mq_pavimento=50, n_bagni=2)
    assert_nessun_prezzo(m)
    data = m.model_dump()
    for k in data:
        assert "prezzo" not in k.lower()
        assert "importo" not in k.lower()


def test_estrai_metriche_da_analisi():
    m = estrai_metriche({"mq": 90, "bagni": 2, "camere": 3, "punti_luce": 40})
    assert m.mq_calpestabile == 90
    assert m.n_bagni == 2
    assert m.n_camere == 3
    assert m.n_punti_luce == 40


def test_salta_qta_zero():
    m = MetricheComputo(mq_pavimento=0, n_punti_luce=10)
    regole = [
        Regola(id="1", metrica="mq_pavimento", prezzario_voce_id="v1", descrizione="x",
               super_categoria="A", categoria="B", um="mq", prezzo_unitario=1),
        Regola(id="2", metrica="n_punti_luce", prezzario_voce_id="v2", descrizione="y",
               super_categoria="A", categoria="B", um="cad", prezzo_unitario=1),
    ]
    voci = genera_voci(m, regole, {})
    assert len(voci) == 1
    assert voci[0].metrica == "n_punti_luce"
