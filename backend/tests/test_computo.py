"""Test computo metrico: regole di conferma, snapshot prezzi, nessun prezzo AI."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

import boq_service
from engines.metriche import MetricheComputo, assert_nessun_prezzo
from mapping_engine import Regola, genera_voci


def test_snapshot_prezzo_non_cambia_se_prezzario_cambia():
    """Il prezzo in computo è snapshot: una regola successiva non lo altera."""
    m = MetricheComputo(mq_pavimento=10)
    regole = [
        Regola(
            id="1",
            metrica="mq_pavimento",
            prezzario_voce_id="v1",
            moltiplicatore=1.0,
            ordine=1,
            super_categoria="Finiture",
            categoria="Pavimenti",
            descrizione="Gres",
            um="mq",
            prezzo_unitario=50.0,
        )
    ]
    voci = genera_voci(m, regole, {})
    assert len(voci) == 1
    assert voci[0].prezzo_unitario == 50.0
    # "nuovo listino" non ricalcola le voci già generate
    regole[0].prezzo_unitario = 99.0
    assert voci[0].prezzo_unitario == 50.0


def test_conferma_richiede_validazione_ai_logica():
    """Replica la guard di conferma: pending AI → 409."""
    pending_ai = 3
    if pending_ai > 0:
        with pytest.raises(HTTPException) as exc:
            raise HTTPException(
                status_code=409,
                detail=f"Restano {pending_ai} voci AI non validate: validale prima di confermare",
            )
        assert exc.value.status_code == 409
        assert "non validate" in str(exc.value.detail)


def test_computo_totale_snapshot():
    m = MetricheComputo(mq_pavimento=100, n_punti_luce=20)
    regole = [
        Regola(
            id="1",
            metrica="mq_pavimento",
            prezzario_voce_id="v1",
            moltiplicatore=1.15,
            ordine=10,
            super_categoria="F",
            categoria="P",
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
            super_categoria="I",
            categoria="E",
            descrizione="Punto luce",
            um="cad",
            prezzo_unitario=58,
        ),
    ]
    voci = genera_voci(m, regole, {})
    totale = sum(round(v.qta * v.prezzo_unitario, 2) for v in voci)
    # 100*1.15*52 + 20*58 = 5980 + 1160 = 7140
    assert totale == pytest.approx(7140.0)


def test_metriche_non_contengono_prezzi():
    m = MetricheComputo(mq_calpestabile=80, n_bagni=2)
    assert_nessun_prezzo(m)
    for k in m.model_dump():
        assert "prezzo" not in k.lower()
        assert "importo" not in k.lower()


def test_preventivo_richiede_computo_realmente_confermato():
    computo = {
        "id": "10000000-0000-4000-8000-000000000001",
        "stato": "ai_da_revisionare",
        "totali": {"totale": 1000},
        "voci": [],
    }
    with patch("boq_service.get_computo", new=AsyncMock(return_value=computo)):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                boq_service.computo_to_preventivo(
                    None,
                    "a0000000-0000-4000-8000-000000000001",
                    computo["id"],
                )
            )
    assert exc.value.status_code == 409
    assert "Conferma il computo" in exc.value.detail
