from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

import boq_service
import server


def test_commercial_workflow_routes_are_registered():
    paths = {route.path for route in server.app.routes}
    assert "/api/computi/{computo_id}/riapri" in paths
    assert "/api/leads/{lead_id}/commerciale" in paths
    assert "/api/leads/{lead_id}/cantiere-da-preventivo" in paths
    assert "/api/leads/{lead_id}/with-artifacts" in paths


def test_riapertura_aggiorna_lo_stesso_preventivo(monkeypatch):
    computo_id = str(uuid4())
    preventivo_id = uuid4()
    lead_id = uuid4()
    conn = SimpleNamespace(
        fetchrow=AsyncMock(
            side_effect=[
                {"id": computo_id, "stato": "confermato"},
                {
                    "id": preventivo_id,
                    "numero": "PREV-2026-0012",
                    "stato": "inviato",
                    "lead_id": lead_id,
                },
            ]
        ),
        fetchval=AsyncMock(return_value=False),
        execute=AsyncMock(),
    )
    get_computo = AsyncMock(
        return_value={"id": computo_id, "preventivo_id": str(preventivo_id)}
    )
    sync_lead = AsyncMock()
    monkeypatch.setattr(boq_service, "get_computo", get_computo)
    monkeypatch.setattr(boq_service, "_aggiorna_lead_da_preventivo", sync_lead)

    result = asyncio.run(
        boq_service.riapri_computo_preventivo(
            conn, str(uuid4()), computo_id, autore="Admin GB"
        )
    )

    statements = "\n".join(call.args[0].lower() for call in conn.execute.await_args_list)
    assert "update public.preventivi" in statements
    assert "set stato = 'bozza'" in statements
    assert "update public.scelte_pagamento_cliente" in statements
    assert "set stato = 'revocata'" in statements
    assert "update public.computi" in statements
    assert "insert into public.preventivi" not in statements
    assert result["preventivo_id"] == str(preventivo_id)
    sync_lead.assert_awaited_once()


def test_generazione_blocca_una_seconda_copia_del_preventivo(monkeypatch):
    computo_id = str(uuid4())
    conn = SimpleNamespace(
        fetchval=AsyncMock(return_value=None),
        fetchrow=AsyncMock(
            return_value={
                "id": uuid4(),
                "numero": "PREV-2026-0012",
                "stato": "inviato",
            }
        ),
    )
    monkeypatch.setattr(
        boq_service,
        "get_computo",
        AsyncMock(
            return_value={
                "id": computo_id,
                "stato": "confermato",
                "totali": {"n_da_validare": 0, "totale": 1000},
                "voci": [
                    {
                        "id": str(uuid4()),
                        "fase_ordine": 10,
                        "totale": 1000,
                    }
                ],
                "superficie_mq": 80,
                "durate_fasi": {},
            }
        ),
    )
    monkeypatch.setattr(
        boq_service.cronoprogramma,
        "stima",
        lambda *_args, **_kwargs: {"profilo": "intervento_parziale"},
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            boq_service.computo_to_preventivo(
                conn, str(uuid4()), computo_id, autore="Admin GB"
            )
        )

    assert exc.value.status_code == 409
    assert "senza creare copie" in exc.value.detail


def test_riepilogo_commerciale_restituisce_valore_inviato_e_cantiere():
    lead_id = uuid4()
    quote_id = uuid4()
    site_id = uuid4()
    conn = SimpleNamespace(
        fetchval=AsyncMock(return_value=lead_id),
        fetchrow=AsyncMock(
            side_effect=[
                {
                    "id": quote_id,
                    "numero": "PREV-2026-0012",
                    "stato": "inviato",
                    "totale_documento": 125000,
                },
                {
                    "id": site_id,
                    "legacy_mongo_id": "66aabbccddeeff0011223344",
                    "stato": "attivo",
                    "importo": 125000,
                },
            ]
        ),
    )

    result = asyncio.run(
        boq_service.riepilogo_commerciale_lead(
            conn, str(uuid4()), "65aabbccddeeff0011223344"
        )
    )

    assert result["preventivo"]["id"] == str(quote_id)
    assert result["preventivo"]["totale_documento"] == 125000
    assert result["cantiere"]["legacy_mongo_id"] == "66aabbccddeeff0011223344"


def test_creazione_cantiere_usa_importo_e_fasi_del_preventivo():
    tenant_id = str(uuid4())
    lead_id = uuid4()
    quote_id = uuid4()
    computo_id = uuid4()
    site_id = uuid4()
    conn = SimpleNamespace(
        fetchrow=AsyncMock(
            side_effect=[
                {
                    "preventivo_id": quote_id,
                    "numero": "PREV-2026-0012",
                    "computo_id": computo_id,
                    "lead_id": lead_id,
                    "cliente_id": None,
                    "preventivo_stato": "inviato",
                    "totale_documento": 125000,
                    "snapshot_voci": json.dumps(
                        [
                            {"fase": "Demolizioni"},
                            {"fase": "Impianti"},
                            {"fase": "Demolizioni"},
                        ]
                    ),
                    "cliente": "Cliente Demo",
                    "telefono": "+39 333 0000000",
                    "indirizzo": "Via Roma 1",
                },
                None,
                {
                    "id": site_id,
                    "cliente": "Cliente Demo",
                    "indirizzo": "Via Roma 1",
                    "importo": 125000,
                    "stato": "attivo",
                },
            ]
        ),
        execute=AsyncMock(),
    )

    result = asyncio.run(
        boq_service.crea_cantiere_da_preventivo(
            conn,
            tenant_id,
            "65aabbccddeeff0011223344",
            str(quote_id),
            "66aabbccddeeff0011223344",
            autore="Admin GB",
        )
    )

    assert result["id"] == str(site_id)
    assert result["importo"] == 125000
    assert [phase["nome"] for phase in result["fasi"]] == [
        "Demolizioni",
        "Impianti",
    ]
    statements = "\n".join(call.args[0].lower() for call in conn.execute.await_args_list)
    assert "update public.computi" in statements
    assert "update public.leads" in statements


def test_eliminazione_lead_rimuove_preventivo_prima_del_computo():
    tenant_id = str(uuid4())
    lead_id = uuid4()
    computo_id = uuid4()
    quote_id = uuid4()
    conn = SimpleNamespace(
        fetchval=AsyncMock(side_effect=[lead_id, False, False]),
        fetch=AsyncMock(
            side_effect=[
                [{"id": computo_id}],
                [{"id": quote_id}],
            ]
        ),
        execute=AsyncMock(),
    )

    result = asyncio.run(
        boq_service.elimina_documenti_lead(
            conn, tenant_id, "65aabbccddeeff0011223344"
        )
    )

    statements = [call.args[0].lower() for call in conn.execute.await_args_list]
    quote_delete = next(i for i, sql in enumerate(statements) if "delete from public.preventivi" in sql)
    computo_delete = next(i for i, sql in enumerate(statements) if "delete from public.computi" in sql)
    lead_delete = next(i for i, sql in enumerate(statements) if "delete from public.leads" in sql)
    assert quote_delete < computo_delete < lead_delete
    assert result == {"lead": 1, "preventivi": 1, "computi": 1}
