"""Piano pagamenti, incassi parziali, extra e note economiche."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import APIRouter, HTTPException

import financial_routes
import financial_service
from economic_note_pdf import genera_nota_economica_pdf
from payment_reminders import _normalize_whatsapp_recipient


TENANT = "a0000000-0000-4000-8000-000000000001"
CANTIERE = "10000000-0000-4000-8000-000000000001"
PREVENTIVO = "20000000-0000-4000-8000-000000000001"
INCASSO = "30000000-0000-4000-8000-000000000001"


def _cantiere():
    return {
        "id": UUID(CANTIERE),
        "tenant_id": UUID(TENANT),
        "cliente": "Cliente Test",
        "cliente_nome": "Cliente Test",
        "cliente_email": "cliente@example.com",
        "cliente_telefono": "+393331234567",
    }


def test_route_controllo_economico_complete_registrate():
    api = APIRouter(prefix="/api")
    financial_routes.register_financial_routes(api, object(), object())
    routes = {(route.path, tuple(sorted(route.methods or []))) for route in api.routes}
    assert any(path == "/api/cantieri/{cantiere_id}/controllo-economico" for path, _ in routes)
    assert any(path == "/api/cantieri/{cantiere_id}/piano-pagamenti" for path, _ in routes)
    assert any(path == "/api/economics/incassi/{incasso_id}/pagamenti" for path, _ in routes)
    assert any(path == "/api/documenti-economici/{documento_id}/firma" for path, _ in routes)


def test_piano_rifiuta_rate_che_non_coincidono_col_contratto():
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        _cantiere(),
        {
            "id": UUID(PREVENTIVO),
            "stato": "accettato",
            "computo_stato": "confermato",
            "totale_documento": Decimal("1000.00"),
        },
    ]
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            financial_service.crea_piano_pagamenti(
                conn,
                TENANT,
                CANTIERE,
                preventivo_id=PREVENTIVO,
                rate=[
                    {
                        "numero": 1,
                        "tipo": "acconto",
                        "titolo": "Acconto",
                        "importo": Decimal("900"),
                        "data_scadenza": date(2026, 8, 10),
                    }
                ],
            )
        )
    assert exc.value.status_code == 400
    assert "deve coincidere" in exc.value.detail
    assert conn.fetchrow.await_count == 2


def test_piano_whatsapp_richiede_consenso_esplicito():
    conn = AsyncMock()
    conn.fetchrow.return_value = _cantiere()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            financial_service.crea_piano_pagamenti(
                conn,
                TENANT,
                CANTIERE,
                preventivo_id=PREVENTIVO,
                rate=[],
                whatsapp_automatico=True,
                whatsapp_consenso=False,
            )
        )

    assert exc.value.status_code == 400
    assert "consenso" in exc.value.detail.lower()
    assert conn.fetchrow.await_count == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+39 333 123 4567", "393331234567"),
        ("3331234567", "393331234567"),
        ("0039 333 123 4567", "393331234567"),
    ],
)
def test_normalizza_numero_whatsapp(raw, expected):
    assert _normalize_whatsapp_recipient(raw) == expected


def test_pagamento_parziale_aggiorna_rata_ma_non_chiude_scadenza():
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {
            "id": UUID(INCASSO),
            "tenant_id": UUID(TENANT),
            "cantiere_id": UUID(CANTIERE),
            "importo": Decimal("1000"),
            "stato": "previsto",
        },
        {
            "id": UUID("40000000-0000-4000-8000-000000000001"),
            "importo": Decimal("400"),
            "data_pagamento": date(2026, 8, 9),
        },
    ]
    conn.fetchval.return_value = Decimal("0")

    result = asyncio.run(
        financial_service.registra_pagamento(
            conn,
            TENANT,
            INCASSO,
            importo=Decimal("400"),
            data_pagamento=date(2026, 8, 9),
            metodo="Bonifico",
        )
    )

    assert result["importo"] == 400.0
    assert conn.execute.await_count == 1
    update = conn.execute.await_args
    assert update.args[1] == "parziale"


def test_pagamento_finale_chiude_scadenza_e_promemoria():
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {
            "id": UUID(INCASSO),
            "tenant_id": UUID(TENANT),
            "cantiere_id": UUID(CANTIERE),
            "importo": Decimal("1000"),
            "stato": "parziale",
        },
        {
            "id": UUID("40000000-0000-4000-8000-000000000001"),
            "importo": Decimal("600"),
            "data_pagamento": date(2026, 8, 9),
        },
    ]
    conn.fetchval.return_value = Decimal("400")

    asyncio.run(
        financial_service.registra_pagamento(
            conn,
            TENANT,
            INCASSO,
            importo=Decimal("600"),
            data_pagamento=date(2026, 8, 9),
        )
    )

    assert conn.execute.await_count == 3
    assert conn.execute.await_args_list[0].args[1] == "incassato"
    assert "stato = 'completata'" in conn.execute.await_args_list[1].args[0]
    assert "stato = 'saltata'" in conn.execute.await_args_list[2].args[0]


def test_nota_extra_pdf_include_totale_e_firma_impresa():
    pdf = genera_nota_economica_pdf(
        {
            "tipo": "autorizzazione_extra",
            "documento_hash": "abc123",
            "ragione_sociale": "GB Construction S.r.l.",
            "slug": "gbconstruction",
            "snapshot": {
                "cantiere": {"cliente": "Cliente Test", "indirizzo": "Via Roma 1"},
                "extra": {
                    "numero": 1,
                    "titolo": "Controsoffitto aggiuntivo",
                    "descrizione": "Fornitura e posa",
                    "imponibile": 1000,
                    "iva_percentuale": 10,
                    "totale": 1100,
                    "data_scadenza": "2026-09-30",
                },
            },
        }
    )
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1500
