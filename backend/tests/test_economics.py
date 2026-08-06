"""Economics cantiere: riepilogo, tenant filter, allegati ed export."""
from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException

import economics_service


TENANT_ID = "a0000000-0000-4000-8000-000000000001"
CANTIERE_ID = "10000000-0000-4000-8000-000000000001"


def test_dashboard_aggrega_margini_e_filtra_tenant():
    conn = AsyncMock()
    conn.fetch.side_effect = [
        [
            {
                "tenant_id": UUID(TENANT_ID),
                "cantiere_id": UUID(CANTIERE_ID),
                "cliente": "Cliente test",
                "ricavi_maturati": Decimal("1000.00"),
                "costi_registrati": Decimal("600.00"),
                "incassato": Decimal("500.00"),
                "da_incassare": Decimal("500.00"),
                "scadenze_aperte": 2,
                "scadenze_scadute": 1,
            }
        ],
        [],
        [],
        [],
        [],
    ]

    result = asyncio.run(economics_service.get_dashboard(conn, TENANT_ID))

    assert result["riepilogo"]["margine"] == 400.0
    assert result["riepilogo"]["margine_percentuale"] == 40.0
    assert result["riepilogo"]["scadenze_scadute"] == 1
    assert conn.fetch.await_count == 5
    for call in conn.fetch.await_args_list:
        assert "tenant_id = $1::uuid" in call.args[0]
        assert call.args[1] == TENANT_ID


def test_crea_spesa_accetta_solo_allegato_del_cantiere():
    conn = AsyncMock()
    conn.fetchval.return_value = True
    conn.fetchrow.return_value = {
        "id": UUID("20000000-0000-4000-8000-000000000001"),
        "tenant_id": UUID(TENANT_ID),
        "cantiere_id": UUID(CANTIERE_ID),
        "imponibile": Decimal("100.00"),
        "iva_importo": Decimal("22.00"),
        "totale": Decimal("122.00"),
    }
    data = {
        "cantiere_id": CANTIERE_ID,
        "fornitore_id": None,
        "categoria": "materiali",
        "descrizione": "Colla e piastrelle",
        "numero_documento": "F-001",
        "data_documento": date(2026, 8, 6),
        "imponibile": Decimal("100"),
        "iva_percentuale": Decimal("22"),
        "stato": "registrata",
        "allegato_path": f"{TENANT_ID}/cantiere-{CANTIERE_ID}/fattura.pdf",
    }

    result = asyncio.run(economics_service.crea_spesa(conn, TENANT_ID, data))

    assert result["totale"] == 122.0
    insert = conn.fetchrow.await_args
    assert "insert into public.spese" in insert.args[0]
    assert insert.args[1] == TENANT_ID
    assert insert.args[2] == CANTIERE_ID


def test_crea_spesa_blocca_allegato_di_un_altro_cantiere():
    conn = AsyncMock()
    conn.fetchval.return_value = True
    data = {
        "cantiere_id": CANTIERE_ID,
        "fornitore_id": None,
        "categoria": "altro",
        "descrizione": "Documento non autorizzato",
        "data_documento": date.today(),
        "imponibile": Decimal("10"),
        "iva_percentuale": Decimal("0"),
        "allegato_path": f"{TENANT_ID}/cantiere-altro/documento.pdf",
    }

    with pytest.raises(HTTPException) as exc:
        asyncio.run(economics_service.crea_spesa(conn, TENANT_ID, data))

    assert exc.value.status_code == 400
    assert "Allegato" in exc.value.detail
    assert conn.fetchrow.await_count == 0


def test_incasso_pagato_imposta_data_e_filtra_tenant():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": UUID("30000000-0000-4000-8000-000000000001"),
        "stato": "incassato",
        "data_incasso": date.today(),
    }

    result = asyncio.run(
        economics_service.aggiorna_incasso(
            conn,
            TENANT_ID,
            "30000000-0000-4000-8000-000000000001",
            {"stato": "incassato"},
        )
    )

    assert result["stato"] == "incassato"
    update = conn.fetchrow.await_args
    assert "tenant_id = $3::uuid" in update.args[0]
    assert update.args[-2] == TENANT_ID
    assert isinstance(update.args[2], date)


def test_export_csv_usa_formato_italiano_excel_compatibile():
    dashboard = {
        "cantieri": [{"cantiere_id": CANTIERE_ID, "cliente": "Rossi"}],
        "spese": [
            {
                "cantiere_id": CANTIERE_ID,
                "data_documento": date(2026, 8, 6),
                "fornitore": "Edil Forniture",
                "descrizione": "Materiali",
                "imponibile": 100.0,
                "iva_importo": 22.0,
                "totale": 122.0,
                "stato": "registrata",
                "numero_documento": "F-001",
            }
        ],
        "incassi": [],
    }
    with patch(
        "economics_service.get_dashboard", new=AsyncMock(return_value=dashboard)
    ):
        content = asyncio.run(economics_service.export_csv(None, TENANT_ID))

    assert content.startswith("\ufefftipo;data;cantiere")
    assert "spesa;2026-08-06;Rossi;Edil Forniture;Materiali;100.00;22.00;122.00" in content
