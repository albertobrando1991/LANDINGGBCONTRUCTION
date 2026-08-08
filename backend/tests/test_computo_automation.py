"""Flusso automatico PDF ACCA -> prezzi GB -> preventivo cliente."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

import boq_service


TENANT_ID = "a0000000-0000-4000-8000-000000000001"
LEAD_ID = "40000000-0000-4000-8000-000000000001"
CLIENTE_ID = UUID("41000000-0000-4000-8000-000000000001")
COMPUTO_ID = UUID("10000000-0000-4000-8000-000000000001")
PREZZARIO_ID = UUID("60000000-0000-4000-8000-000000000001")
VOCE_ID = UUID("70000000-0000-4000-8000-000000000001")


def _parsed() -> dict:
    return {
        "n_voci": 1,
        "totale_pdf": Decimal("100.00"),
        "voci": [
            {
                "numero": 1,
                "codice": "CAM24_R02.060.040.A",
                "descrizione": "Demolizione controllata",
                "um": "mq",
                "qta": Decimal("10.000"),
                "prezzo_unitario": Decimal("10.00"),
                "totale_pdf": Decimal("100.00"),
                "coerente": True,
            }
        ],
    }


def test_matching_acca_richiede_codice_um_e_univocita():
    item = _parsed()["voci"][0]
    candidate = {
        "id": str(VOCE_ID),
        "codice": "CAM24-R02.060.040.A",
        "um": "mq",
    }
    key = boq_service._normalizza_codice(candidate["codice"])

    assert boq_service._abbina_voce_acca(item, {key: [candidate]}) == candidate
    assert boq_service._abbina_voce_acca(item, {key: [candidate, candidate]}) is None
    assert boq_service._abbina_voce_acca(item, {key: [{**candidate, "um": "mc"}]}) is None


def test_nuovo_lead_crea_e_collega_anagrafica_cliente():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": UUID(LEAD_ID),
        "cliente_id": None,
        "nome": "Mario Rossi",
        "email": "mario@example.com",
        "telefono": "+390811234567",
        "citta": "Napoli",
        "indirizzo": "Via Roma 1",
    }
    conn.fetchval.side_effect = [None, CLIENTE_ID]

    cliente_id = asyncio.run(
        boq_service._ensure_cliente_for_lead(
            conn,
            TENANT_ID,
            {
                "id": UUID(LEAD_ID),
                "cliente_id": None,
                "nome": "Mario Rossi",
                "email": "MARIO@example.com",
                "telefono": "+390811234567",
                "citta": "Napoli",
                "indirizzo": "Via Roma 1",
            },
        )
    )

    assert cliente_id == str(CLIENTE_ID)
    assert "pg_advisory_xact_lock" in conn.execute.await_args_list[0].args[0]
    assert "insert into public.clienti" in conn.fetchval.await_args_list[1].args[0]
    assert "update public.leads set cliente_id" in conn.execute.await_args_list[1].args[0]


def test_import_acca_applica_prezzo_gb_solo_su_match_sicuro():
    conn = AsyncMock()
    conn.fetchval.return_value = True
    conn.fetchrow.side_effect = [
        {"id": UUID(LEAD_ID), "cliente_id": CLIENTE_ID},
        {
            "id": COMPUTO_ID,
            "tenant_id": UUID(TENANT_ID),
            "lead_id": UUID(LEAD_ID),
            "cantiere_id": None,
            "prezzario_id": PREZZARIO_ID,
            "tipo": "estimativo",
            "stato": "bozza",
        },
        {
            "id": COMPUTO_ID,
            "tenant_id": UUID(TENANT_ID),
            "lead_id": UUID(LEAD_ID),
            "cantiere_id": None,
            "prezzario_id": PREZZARIO_ID,
            "tipo": "estimativo",
            "stato": "bozza",
            "cliente": "Mario Rossi",
            "prezzario_nome": "Listino GB 2026",
        },
        {
            "computo_id": COMPUTO_ID,
            "tenant_id": UUID(TENANT_ID),
            "totale": Decimal("1450.00"),
            "n_voci": 1,
            "n_da_validare": 0,
        },
    ]
    conn.fetch.side_effect = [
        [
            {
                "id": VOCE_ID,
                "codice": "CAM24 R02.060.040.A",
                "super_categoria": "Demolizioni",
                "categoria": "Pavimenti",
                "sub_categoria": "Rimozioni",
                "descrizione": "Demolizione pavimento",
                "um": "mq",
                "tipo": "a_misura",
                "prezzo_unitario": Decimal("145.00"),
            }
        ],
        [],
    ]

    result = asyncio.run(
        boq_service.importa_computo_acca(
            conn,
            TENANT_ID,
            filename="computo-demo.pdf",
            parsed=_parsed(),
            lead_id=LEAD_ID,
            prezzario_id=str(PREZZARIO_ID),
        )
    )

    assert result["importazione"]["n_prezzi_gb"] == 1
    assert result["importazione"]["n_da_verificare"] == 0
    assert result["importazione"]["totale_pdf"] == 100.0
    assert result["importazione"]["totale_gb"] == 1450.0
    assert result["automazione"]["pronto_preventivo"] is True
    assert result["importazione"]["n_da_classificare"] == 0
    insert_voice = conn.execute.await_args_list[0]
    assert "insert into public.computo_voci" in insert_voice.args[0]
    assert insert_voice.args[3] == str(VOCE_ID)
    assert insert_voice.args[12] == Decimal("145.00")
    assert insert_voice.args[13:15] == ("Demolizioni e rimozioni", 15)
    assert insert_voice.args[15:] == (False, True)


def test_preventivo_automatico_persist_client_id():
    conn = AsyncMock()
    conn.fetchval.side_effect = [None, CLIENTE_ID, None, 1]
    preventivo = {
        "id": UUID("30000000-0000-4000-8000-000000000001"),
        "tenant_id": UUID(TENANT_ID),
        "computo_id": COMPUTO_ID,
        "lead_id": UUID(LEAD_ID),
        "cliente_id": CLIENTE_ID,
        "numero": "PREV-2026-0001",
        "stato": "bozza",
    }
    conn.fetchrow.side_effect = [None, preventivo]
    computo = {
        "id": str(COMPUTO_ID),
        "lead_id": LEAD_ID,
        "stato": "bozza",
        "totali": {"totale": 1000, "n_da_validare": 0},
        "voci": [{"descrizione": "Demolizione", "qta": 10, "prezzo_unitario": 100}],
    }

    with patch("boq_service.get_computo", new=AsyncMock(return_value=computo)):
        result = asyncio.run(
            boq_service.computo_to_preventivo(
                conn,
                TENANT_ID,
                str(COMPUTO_ID),
                autore="Operatore GB",
                consenti_computo_editabile=True,
            )
        )

    assert result["cliente_id"] == str(CLIENTE_ID)
    insert_preventivo = conn.fetchrow.await_args_list[1]
    assert "cliente_id" in insert_preventivo.args[0]
    assert insert_preventivo.args[4] == CLIENTE_ID


def test_rigenerazione_aggiorna_la_stessa_bozza_senza_creare_copie():
    preventivo_id = UUID("30000000-0000-4000-8000-000000000001")
    existing = {
        "id": preventivo_id,
        "tenant_id": UUID(TENANT_ID),
        "computo_id": COMPUTO_ID,
        "lead_id": UUID(LEAD_ID),
        "cliente_id": CLIENTE_ID,
        "numero": "PREV-2026-0001",
        "stato": "bozza",
        "sconto_percentuale": Decimal("0"),
        "iva_percentuale": Decimal("10"),
    }
    updated = {
        **existing,
        "totale_imponibile": Decimal("1200.00"),
        "totale_documento": Decimal("1254.00"),
    }
    computo = {
        "id": str(COMPUTO_ID),
        "lead_id": LEAD_ID,
        "stato": "bozza",
        "totali": {"totale": 1200, "n_da_validare": 0},
        "voci": [{"descrizione": "Demolizione", "qta": 12, "prezzo_unitario": 100}],
    }
    conn = AsyncMock()
    conn.fetchval.side_effect = [None, CLIENTE_ID]
    conn.fetchrow.side_effect = [existing, updated]

    with patch("boq_service.get_computo", new=AsyncMock(return_value=computo)):
        result = asyncio.run(
            boq_service.computo_to_preventivo(
                conn,
                TENANT_ID,
                str(COMPUTO_ID),
                sconto=5,
                iva=10,
                autore="Operatore GB",
                consenti_computo_editabile=True,
            )
        )

    assert result["id"] == str(preventivo_id)
    assert conn.fetchrow.await_count == 2
    assert "update public.preventivi" in conn.fetchrow.await_args_list[1].args[0]
    assert all(
        "insert into public.preventivi" not in call.args[0]
        for call in conn.fetchrow.await_args_list
    )
