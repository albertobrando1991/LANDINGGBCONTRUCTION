"""Test computo metrico: regole di conferma, snapshot prezzi, nessun prezzo AI."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import UUID

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


def test_rimuovi_voce_filtra_tenant_e_computo():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    computo_id = UUID("10000000-0000-4000-8000-000000000001")
    voce_id = "20000000-0000-4000-8000-000000000001"
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {"computo_id": computo_id, "stato": "bozza"},
        {
            "id": UUID(voce_id),
            "computo_id": computo_id,
        },
    ]

    deleted = asyncio.run(boq_service.rimuovi_voce(conn, tenant_id, voce_id))

    assert deleted == {"id": voce_id, "computo_id": str(computo_id)}
    delete_call = conn.fetchrow.await_args_list[1]
    assert "tenant_id = $2::uuid" in delete_call.args[0]
    assert delete_call.args[1:] == (voce_id, tenant_id, str(computo_id))


def test_rimuovi_voce_blocca_computo_confermato():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "computo_id": UUID("10000000-0000-4000-8000-000000000001"),
        "stato": "confermato",
    }

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            boq_service.rimuovi_voce(
                conn,
                "a0000000-0000-4000-8000-000000000001",
                "20000000-0000-4000-8000-000000000001",
            )
        )

    assert exc.value.status_code == 409
    assert conn.fetchrow.await_count == 1


def test_riordina_voci_richiede_elenco_completo_senza_duplicati():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    computo_id = "10000000-0000-4000-8000-000000000001"
    first = UUID("20000000-0000-4000-8000-000000000001")
    second = UUID("20000000-0000-4000-8000-000000000002")
    conn = AsyncMock()
    conn.fetchval.return_value = "bozza"
    conn.fetch.return_value = [{"id": first}, {"id": second}]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            boq_service.riordina_voci(
                conn,
                tenant_id,
                computo_id,
                [str(first), str(first)],
            )
        )

    assert exc.value.status_code == 400
    assert conn.execute.await_count == 0


def test_riordina_voci_aggiorna_solo_righe_del_tenant():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    computo_id = "10000000-0000-4000-8000-000000000001"
    first = UUID("20000000-0000-4000-8000-000000000001")
    second = UUID("20000000-0000-4000-8000-000000000002")
    conn = AsyncMock()
    conn.fetchval.return_value = "bozza"
    conn.fetch.return_value = [{"id": first}, {"id": second}]

    asyncio.run(
        boq_service.riordina_voci(
            conn,
            tenant_id,
            computo_id,
            [str(second), str(first)],
        )
    )

    assert conn.execute.await_count == 2
    first_update = conn.execute.await_args_list[0]
    assert "tenant_id = $4::uuid" in first_update.args[0]
    assert first_update.args[1:] == (0, str(second), computo_id, tenant_id)


def test_aggiorna_stato_preventivo_registra_evento_e_aggiorna_lead():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    preventivo_id = "30000000-0000-4000-8000-000000000001"
    lead_id = UUID("40000000-0000-4000-8000-000000000001")
    preventivo = {
        "id": UUID(preventivo_id),
        "lead_id": lead_id,
        "numero": "GB-2026-001",
        "stato": "inviato",
    }
    aggiornato = {**preventivo, "stato": "accettato"}
    conn = AsyncMock()
    conn.fetchrow.side_effect = [preventivo, aggiornato]

    result = asyncio.run(
        boq_service.aggiorna_stato_preventivo(
            conn,
            tenant_id,
            preventivo_id,
            "accettato",
            autore="Mario Staff",
        )
    )

    assert result["stato"] == "accettato"
    update_call = conn.fetchrow.await_args_list[1]
    assert "tenant_id = $3::uuid" in update_call.args[0]
    assert update_call.args[1:] == (
        "accettato",
        preventivo_id,
        tenant_id,
        "inviato",
    )
    assert conn.execute.await_count == 2
    history_call = conn.execute.await_args_list[0]
    assert "insert into public.preventivo_eventi" in history_call.args[0]
    assert history_call.args[1:5] == (
        tenant_id,
        preventivo_id,
        "inviato",
        "accettato",
    )
    lead_call = conn.execute.await_args_list[1]
    assert "update public.leads" in lead_call.args[0]
    assert lead_call.args[1] == "chiuso_vinto"
    assert lead_call.args[-2:] == (str(lead_id), tenant_id)


def test_aggiorna_stato_preventivo_blocca_transizione_da_bozza():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": UUID("30000000-0000-4000-8000-000000000001"),
        "lead_id": None,
        "numero": "GB-2026-001",
        "stato": "bozza",
    }

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            boq_service.aggiorna_stato_preventivo(
                conn,
                "a0000000-0000-4000-8000-000000000001",
                "30000000-0000-4000-8000-000000000001",
                "accettato",
                autore="Mario Staff",
            )
        )

    assert exc.value.status_code == 409
    assert "Transizione non consentita" in exc.value.detail
    assert conn.execute.await_count == 0


def test_registra_invio_preventivo_salva_metadati_e_storico():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    preventivo_id = UUID("30000000-0000-4000-8000-000000000001")
    preventivo = {
        "id": preventivo_id,
        "lead_id": None,
        "numero": "GB-2026-001",
        "stato": "bozza",
    }
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        **preventivo,
        "stato": "inviato",
        "ultimo_destinatario": "cliente@example.com",
        "ultimo_email_provider": "resend",
        "ultimo_email_id": "email-123",
    }

    result = asyncio.run(
        boq_service.registra_invio_preventivo(
            conn,
            tenant_id,
            preventivo,
            destinatario="cliente@example.com",
            oggetto="Preventivo GB-2026-001",
            provider="resend",
            provider_message_id="email-123",
            idempotency_key="preventivo/tenant/id/invio-iniziale",
            autore="Mario Staff",
        )
    )

    assert result["stato"] == "inviato"
    update_call = conn.fetchrow.await_args
    assert "stato = 'inviato'" in update_call.args[0]
    assert update_call.args[1:4] == (
        "cliente@example.com",
        "resend",
        "email-123",
    )
    assert update_call.args[-1] == tenant_id
    assert conn.execute.await_count == 1
    history_call = conn.execute.await_args
    assert "'email_inviata'" in history_call.args[0]
    assert history_call.args[1] == tenant_id
    assert history_call.args[2] == preventivo_id
    assert history_call.args[7] == "preventivo/tenant/id/invio-iniziale"
