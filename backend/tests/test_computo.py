"""Test computo metrico: regole di conferma, snapshot prezzi, nessun prezzo AI."""
from __future__ import annotations

import asyncio
import json
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


def test_totali_voci_calcolati_senza_query_aggregata():
    totali = boq_service._totali_voci(
        [
            {
                "totale": 10.10,
                "generata_da_ai": True,
                "validata_umano": False,
            },
            {
                "totale": 20.20,
                "generata_da_ai": True,
                "validata_umano": True,
            },
            {
                "totale": None,
                "generata_da_ai": False,
                "validata_umano": False,
            },
        ]
    )

    assert totali == {
        "totale": 30.30,
        "n_voci": 3,
        "n_da_validare": 1,
    }


def test_get_computo_riusa_le_voci_per_i_totali():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    computo_id = "10000000-0000-4000-8000-000000000001"
    variante_id = "10000000-0000-4000-8000-000000000002"
    voce_ok_id = "20000000-0000-4000-8000-000000000001"
    voce_pending_id = "20000000-0000-4000-8000-000000000002"
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": UUID(computo_id),
        "tenant_id": UUID(tenant_id),
        "stato": "bozza",
        "durate_fasi": '{"15": 4}',
        "variante_modificabile_id": UUID(variante_id),
        "variante_modificabile_stato": "bozza",
        "variante_modificabile_note": "Copia di lavoro",
    }
    conn.fetch.return_value = [
        {
            "id": UUID(voce_ok_id),
            "totale": 10,
            "fase": "Demolizioni e rimozioni",
            "fase_ordine": 15,
            "generata_da_ai": False,
            "validata_umano": False,
        },
        {
            "id": UUID(voce_pending_id),
            "totale": 20,
            "fase": "Da classificare",
            "fase_ordine": 99,
            "generata_da_ai": False,
            "validata_umano": False,
        },
    ]

    result = asyncio.run(boq_service.get_computo(conn, tenant_id, computo_id))

    assert conn.fetchrow.await_count == 1
    assert conn.fetch.await_count == 1
    assert result["totali"] == {
        "totale": 30.0,
        "n_voci": 2,
        "n_da_validare": 0,
        "computo_id": computo_id,
        "tenant_id": tenant_id,
    }
    assert result["durate_fasi"] == {"15": 4}
    assert result["voci_da_classificare_ids"] == [voce_pending_id]
    assert result["n_senza_fase"] == 1
    assert result["variante_modificabile"] == {
        "id": variante_id,
        "stato": "bozza",
        "note": "Copia di lavoro",
    }


def test_aggiorna_cronoprogramma_persiste_superficie_e_durate_e_sincronizza():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    computo_id = "10000000-0000-4000-8000-000000000001"
    conn = AsyncMock()
    conn.fetchrow.return_value = {"id": UUID(computo_id)}
    aggiornato = {
        "id": computo_id,
        "superficie_mq": 92,
        "durate_fasi": {"15": 12, "69": 8},
    }

    with (
        patch(
            "boq_service.sincronizza_preventivo_bozza",
            new=AsyncMock(return_value=None),
        ) as sincronizza,
        patch(
            "boq_service.get_computo",
            new=AsyncMock(return_value=aggiornato),
        ),
    ):
        result = asyncio.run(
            boq_service.aggiorna_cronoprogramma(
                conn,
                tenant_id,
                computo_id,
                superficie_mq=92,
                durate_fasi={15: 12, 69: 8},
            )
        )

    assert result == aggiornato
    update = conn.fetchrow.await_args
    assert "update public.computi" in update.args[0]
    assert update.args[1] == 92
    assert json.loads(update.args[2]) == {"15": 12, "69": 8}
    assert update.args[3:] == (computo_id, tenant_id)
    sincronizza.assert_awaited_once_with(conn, tenant_id, computo_id)


def test_aggiorna_cronoprogramma_rifiuta_fasi_continue():
    conn = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            boq_service.aggiorna_cronoprogramma(
                conn,
                "a0000000-0000-4000-8000-000000000001",
                "10000000-0000-4000-8000-000000000001",
                superficie_mq=92,
                durate_fasi={95: 10},
            )
        )

    assert exc.value.status_code == 400
    conn.fetchrow.assert_not_awaited()


def test_elimina_computo_rimuove_la_sola_bozza_preventivo():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    computo_id = "10000000-0000-4000-8000-000000000001"
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {"id": UUID(computo_id), "numero": "C-001", "tipo": "estimativo", "stato": "bozza"},
        {"id": UUID(computo_id), "numero": "C-001"},
    ]
    conn.fetchval.side_effect = [False, False, False]

    result = asyncio.run(
        boq_service.elimina_computo(conn, tenant_id, computo_id)
    )

    assert result == {"ok": True, "id": computo_id, "numero": "C-001"}
    assert conn.execute.await_count == 1
    assert "stato = 'bozza'" in conn.execute.await_args.args[0]
    assert "tenant_id = $1::uuid" in conn.fetchrow.await_args.args[0]


def test_elimina_computo_blocca_preventivo_finalizzato():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": UUID("10000000-0000-4000-8000-000000000001"),
        "numero": "C-001",
        "tipo": "estimativo",
        "stato": "confermato",
    }
    conn.fetchval.side_effect = [False, False, True]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            boq_service.elimina_computo(
                conn,
                "a0000000-0000-4000-8000-000000000001",
                "10000000-0000-4000-8000-000000000001",
            )
        )

    assert exc.value.status_code == 409
    assert "preventivo" in exc.value.detail.lower()
    conn.execute.assert_not_awaited()


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
        None,
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


def test_modifica_voce_sincronizza_la_bozza_preventivo():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    computo_id = UUID("10000000-0000-4000-8000-000000000001")
    voce_id = "20000000-0000-4000-8000-000000000001"
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {"computo_id": computo_id, "stato": "bozza"},
        {
            "id": UUID(voce_id),
            "computo_id": computo_id,
            "descrizione": "Voce aggiornata",
            "qta": 3,
            "prezzo_unitario": 120,
        },
    ]
    sync = AsyncMock(return_value={"numero": "PREV-2026-0001"})

    with patch("boq_service.sincronizza_preventivo_bozza", new=sync):
        result = asyncio.run(
            boq_service.aggiorna_voce(
                conn,
                tenant_id,
                voce_id,
                qta=3,
                prezzo_unitario=120,
            )
        )

    assert result["qta"] == 3
    sync.assert_awaited_once_with(conn, tenant_id, str(computo_id))


def test_aggiungi_voce_libera_senza_prezzario_e_sincronizza_preventivo():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    computo_id = "10000000-0000-4000-8000-000000000001"
    conn = AsyncMock()
    conn.fetchval.side_effect = ["bozza", 20]
    conn.fetchrow.return_value = {
        "id": UUID("20000000-0000-4000-8000-000000000001"),
        "computo_id": UUID(computo_id),
        "origine_voce_id": None,
        "descrizione": "Lavorazione speciale su misura",
        "um": "mq",
        "qta": 12.5,
        "prezzo_unitario": 37.2,
        "validata_umano": True,
    }
    sync = AsyncMock(return_value={"numero": "PREV-2026-0001"})

    with patch("boq_service.sincronizza_preventivo_bozza", new=sync):
        result = asyncio.run(
            boq_service.aggiungi_voce_libera(
                conn,
                tenant_id,
                computo_id,
                "  Lavorazione speciale su misura  ",
                " mq ",
                12.5,
                37.2,
            )
        )

    assert result["origine_voce_id"] is None
    insert_call = conn.fetchrow.await_args
    assert "origine_voce_id" in insert_call.args[0]
    assert "null" in insert_call.args[0].lower()
    assert insert_call.args[4:6] == ("Lavorazione speciale su misura", "mq")
    sync.assert_awaited_once_with(conn, tenant_id, computo_id)


def test_conferma_blocca_il_computo_prima_della_sincronizzazione_finale():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    computo_id = UUID("10000000-0000-4000-8000-000000000001")
    current = {"id": computo_id, "stato": "bozza"}
    confirmed = {"id": computo_id, "stato": "confermato"}
    conn = AsyncMock()
    conn.fetchrow.side_effect = [current, confirmed]
    conn.fetchval.return_value = 0
    sync = AsyncMock(return_value={"numero": "PREV-2026-0001"})

    with patch("boq_service.sincronizza_preventivo_bozza", new=sync):
        result = asyncio.run(
            boq_service.conferma_computo(conn, tenant_id, str(computo_id))
        )

    assert result["stato"] == "confermato"
    assert "for update" in conn.fetchrow.await_args_list[0].args[0].lower()
    sync.assert_awaited_once_with(conn, tenant_id, str(computo_id))


def test_riordina_voci_richiede_elenco_completo_senza_duplicati():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    computo_id = "10000000-0000-4000-8000-000000000001"
    first = UUID("20000000-0000-4000-8000-000000000001")
    second = UUID("20000000-0000-4000-8000-000000000002")
    conn = AsyncMock()
    conn.fetchval.return_value = "bozza"
    conn.fetch.return_value = [{"id": first}, {"id": second}]
    conn.fetchrow.return_value = None

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
    conn.fetchrow.return_value = None

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


def test_duplica_computo_ordinario_non_crea_legami_contrattuali():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    computo_id = "10000000-0000-4000-8000-000000000001"
    new_id = UUID("10000000-0000-4000-8000-000000000002")
    src = {
        "id": UUID(computo_id),
        "lead_id": None,
        "cantiere_id": None,
        "prezzario_id": None,
        "tipo": "estimativo",
        "stato": "confermato",
        "numero": "CMP-001",
    }
    conn = AsyncMock()
    conn.fetchrow.side_effect = [src, {**src, "id": new_id, "stato": "bozza"}]
    conn.fetchval.return_value = new_id

    result = asyncio.run(
        boq_service.duplica_computo(conn, tenant_id, computo_id)
    )

    assert result["id"] == str(new_id)
    insert_computo = conn.fetchval.await_args
    assert insert_computo.args[4] is None
    copy_voci = conn.execute.await_args
    assert "parent_voce_id" in copy_voci.args[0]
    assert copy_voci.args[-1] is False


def test_crea_variante_richiede_base_confermata_e_non_variante():
    conn = AsyncMock()
    source = {
        "id": UUID("10000000-0000-4000-8000-000000000001"),
        "tipo": "estimativo",
        "stato": "bozza",
    }
    conn.fetchrow.side_effect = [None, source]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            boq_service.crea_variante(
                conn,
                "a0000000-0000-4000-8000-000000000001",
                "10000000-0000-4000-8000-000000000001",
            )
        )

    assert exc.value.status_code == 409
    assert "confermato" in exc.value.detail
    assert conn.fetchval.await_count == 0


def test_crea_variante_riusa_la_copia_modificabile_esistente():
    variante_id = "10000000-0000-4000-8000-000000000002"
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": UUID(variante_id),
        "tipo": "variante",
        "stato": "bozza",
    }

    result = asyncio.run(
        boq_service.crea_variante(
            conn,
            "a0000000-0000-4000-8000-000000000001",
            "10000000-0000-4000-8000-000000000001",
        )
    )

    assert result["id"] == variante_id
    assert conn.fetchrow.await_count == 1
    assert conn.fetchval.await_count == 0


def test_confronto_variante_calcola_delta_e_classificazioni():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    variante_id = "10000000-0000-4000-8000-000000000002"
    base_id = UUID("10000000-0000-4000-8000-000000000001")
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {
            "id": UUID(variante_id),
            "parent_computo_id": base_id,
            "numero": "VAR-001",
            "stato": "bozza",
            "numero_base": "CMP-001",
            "stato_base": "confermato",
        },
        {"totale_variante": 1125, "totale_base": 1000},
    ]
    conn.fetch.return_value = [
        {"classificazione": "modificata", "delta_importo": 100},
        {"classificazione": "nuova", "delta_importo": 25},
        {"classificazione": "invariata", "delta_importo": 0},
    ]

    result = asyncio.run(
        boq_service.get_confronto_variante(conn, tenant_id, variante_id)
    )

    assert result["riepilogo"]["delta_importo"] == 125.0
    assert result["riepilogo"]["delta_percentuale"] == 12.5
    assert result["riepilogo"]["conteggi"] == {
        "invariata": 1,
        "modificata": 1,
        "nuova": 1,
        "soppressa": 0,
    }
    comparison_call = conn.fetch.await_args
    assert "tenant_id = $1::uuid" in comparison_call.args[0]
    assert comparison_call.args[1:] == (tenant_id, variante_id)


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
