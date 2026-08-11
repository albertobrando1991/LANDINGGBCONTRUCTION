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


def test_costi_fissi_totale_esclude_voci_scadute():
    conn = AsyncMock()
    conn.fetch.return_value = [
        {
            "id": UUID("50000000-0000-4000-8000-000000000001"),
            "descrizione": "Affitto sede",
            "importo_mensile": Decimal("1200.00"),
            "attivo": True,
            "corrente": True,
        },
        {
            "id": UUID("50000000-0000-4000-8000-000000000002"),
            "descrizione": "Leasing concluso",
            "importo_mensile": Decimal("450.00"),
            "attivo": True,
            "data_fine": date(2026, 7, 31),
            "corrente": False,
        },
    ]

    result = asyncio.run(economics_service.get_costi_fissi(conn, TENANT_ID))

    assert result["totale_mensile"] == 1200.0
    assert len(result["righe"]) == 2
    query = conn.fetch.await_args
    assert "data_fine >= current_date" in query.args[0]
    assert query.args[1:] == (TENANT_ID, None)


def test_crud_costo_fisso_filtra_sempre_il_tenant():
    conn = AsyncMock()
    costo_id = "50000000-0000-4000-8000-000000000001"
    conn.fetchrow.side_effect = [
        {
            "id": UUID(costo_id),
            "tenant_id": UUID(TENANT_ID),
            "descrizione": "Assicurazione aziendale",
            "importo_mensile": Decimal("300.00"),
        },
        {"data_inizio": date(2026, 8, 1), "data_fine": None},
        {
            "id": UUID(costo_id),
            "tenant_id": UUID(TENANT_ID),
            "descrizione": "Assicurazione aziendale",
            "importo_mensile": Decimal("320.00"),
        },
    ]

    created = asyncio.run(
        economics_service.crea_costo_fisso(
            conn,
            TENANT_ID,
            {
                "categoria": "assicurazioni",
                "descrizione": " Assicurazione aziendale ",
                "importo_mensile": Decimal("300"),
                "data_inizio": date(2026, 8, 1),
            },
        )
    )
    updated = asyncio.run(
        economics_service.aggiorna_costo_fisso(
            conn,
            TENANT_ID,
            costo_id,
            {"importo_mensile": Decimal("320")},
        )
    )

    assert created["importo_mensile"] == 300.0
    assert updated["importo_mensile"] == 320.0
    assert conn.fetchrow.await_args_list[0].args[1] == TENANT_ID
    update = conn.fetchrow.await_args_list[2]
    assert "update public.costi_fissi" in update.args[0]
    assert update.args[-2:] == (TENANT_ID, costo_id)


def test_subappalti_aggregati_per_fornitore_e_cantiere():
    conn = AsyncMock()
    conn.fetch.return_value = [
        {
            "fornitore_id": UUID("60000000-0000-4000-8000-000000000001"),
            "ragione_sociale": "Impianti Alfa",
            "cantiere_id": UUID(CANTIERE_ID),
            "numero_spese": 2,
            "totale_speso": Decimal("1500.00"),
            "totale_pagato": Decimal("1000.00"),
        },
        {
            "fornitore_id": UUID("60000000-0000-4000-8000-000000000002"),
            "ragione_sociale": "Edil Beta",
            "cantiere_id": UUID(CANTIERE_ID),
            "numero_spese": 1,
            "totale_speso": Decimal("800.00"),
            "totale_pagato": Decimal("0.00"),
        },
    ]

    result = asyncio.run(
        economics_service.get_subappalti_dashboard(conn, TENANT_ID)
    )

    assert result["totale_speso"] == 2300.0
    assert result["totale_pagato"] == 1000.0
    assert len(result["righe"]) == 2
    query = conn.fetch.await_args
    assert "s.categoria = 'subappalto'" in query.args[0]
    assert "s.stato <> 'annullata'" in query.args[0]
    assert query.args[1:] == (TENANT_ID, None)
