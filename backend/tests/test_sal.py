"""API e regole applicative dei SAL derivati dal libretto misure."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import APIRouter, HTTPException, Request

import edilos_routes
import sal_service

TENANT_ID = "a0000000-0000-4000-8000-000000000001"
CANTIERE_ID = "10000000-0000-4000-8000-000000000001"
SAL_ID = "50000000-0000-4000-8000-000000000001"
VOCE_ID = "20000000-0000-4000-8000-000000000001"


def _request(method: str = "POST") -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 123),
        }
    )


def _endpoint(path: str, method: str):
    api = APIRouter(prefix="/api")
    edilos_routes.register_edilos_routes(api, object(), object())
    return next(
        route.endpoint
        for route in api.routes
        if route.path == path and method in (route.methods or set())
    )


def test_route_sal_complete_sono_registrate():
    assert callable(_endpoint("/api/cantieri/{cantiere_id}/sal", "GET"))
    assert callable(_endpoint("/api/cantieri/{cantiere_id}/sal", "POST"))
    assert callable(_endpoint("/api/sal/{sal_id}", "GET"))
    assert callable(_endpoint("/api/sal/{sal_id}/pdf", "GET"))
    assert callable(_endpoint("/api/sal/{sal_id}/stato", "PATCH"))


def test_route_pdf_sal_restituisce_allegato_autenticato(monkeypatch):
    async def fake_user(request, db):
        return {"id": "user"}

    route_conn = AsyncMock()

    @asynccontextmanager
    async def tenant_conn(request, user):
        yield route_conn, {"id": TENANT_ID, "role": "staff"}

    documento = {
        "sal": {"id": SAL_ID, "numero": 7, "stato": "emesso"},
        "cantiere": {},
        "tenant": {},
        "misure": [],
    }
    get_documento = AsyncMock(return_value=documento)
    monkeypatch.setattr(edilos_routes, "_user", fake_user)
    monkeypatch.setattr(sal_service, "get_sal_documento", get_documento)
    monkeypatch.setattr(edilos_routes, "genera_pdf_sal", lambda value: b"%PDF-test")
    api = APIRouter(prefix="/api")
    edilos_routes.register_edilos_routes(api, object(), tenant_conn)
    endpoint = next(
        route.endpoint for route in api.routes if route.path == "/api/sal/{sal_id}/pdf"
    )

    response = asyncio.run(endpoint(_request("GET"), SAL_ID))

    assert response.body == b"%PDF-test"
    assert response.media_type == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="SAL-07-con-libretto.pdf"'
    )
    get_documento.assert_awaited_once_with(route_conn, TENANT_ID, SAL_ID)


def test_body_sal_valida_stati_esposti():
    body = edilos_routes.GeneraSalBody(periodo_da="2026-08-01", periodo_a="2026-08-31")
    stato = edilos_routes.SalStatoBody(stato="emesso")

    assert body.periodo_da == date(2026, 8, 1)
    assert stato.stato == "emesso"


def test_linea_segnala_eccedenza_senza_bloccarla():
    linea = sal_service._linea(
        {
            "id": UUID(VOCE_ID),
            "qta_periodo": Decimal("3.000"),
            "qta_progressiva": Decimal("7.500"),
            "qta_contrattuale": Decimal("6.000"),
            "prezzo_unitario": Decimal("25.00"),
            "importo_periodo": Decimal("75.00"),
        }
    )

    assert linea["id"] == VOCE_ID
    assert linea["eccedenza_qta"] == 1.5
    assert linea["in_eccedenza"] is True
    assert linea["proponi_variante"] is True


def test_genera_sal_rifiuta_periodo_inverso_prima_del_database():
    conn = AsyncMock()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            sal_service.genera_sal(
                conn,
                TENANT_ID,
                CANTIERE_ID,
                periodo_da=date(2026, 9, 1),
                periodo_a=date(2026, 8, 31),
            )
        )

    assert exc.value.status_code == 400
    assert conn.fetchval.await_count == 0


def test_genera_sal_rifiuta_periodo_senza_misure_valorizzate():
    conn = AsyncMock()
    conn.fetchval.side_effect = [True, None]
    conn.fetchrow.return_value = None
    conn.fetch.return_value = []

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            sal_service.genera_sal(
                conn,
                TENANT_ID,
                CANTIERE_ID,
                periodo_da=date(2026, 8, 1),
                periodo_a=date(2026, 8, 31),
            )
        )

    assert exc.value.status_code == 409
    assert "Nessuna misura" in str(exc.value.detail)
    assert "c.stato = 'confermato'" in conn.fetch.await_args.args[0]


def test_aggiorna_stato_rifiuta_sal_gia_approvato():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": UUID(SAL_ID),
        "tenant_id": UUID(TENANT_ID),
        "stato": "approvato",
    }
    conn.fetch.return_value = []

    with pytest.raises(HTTPException) as exc:
        asyncio.run(sal_service.aggiorna_stato(conn, TENANT_ID, SAL_ID, "approvato"))

    assert exc.value.status_code == 409
    assert "approvato -> approvato" in str(exc.value.detail)
    assert conn.fetchrow.await_count == 1


def test_documento_sal_limita_cantiere_e_misure_al_tenant(monkeypatch):
    sal = {
        "id": SAL_ID,
        "cantiere_id": CANTIERE_ID,
        "numero": 2,
        "periodo_da": date(2026, 8, 1),
        "periodo_a": date(2026, 8, 31),
        "righe": [],
    }
    monkeypatch.setattr(sal_service, "get_sal", AsyncMock(return_value=sal))
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {"id": UUID(CANTIERE_ID), "cliente": "Cliente tenant A"},
        {"id": UUID(TENANT_ID), "slug": "tenant-a"},
    ]
    conn.fetch.return_value = [
        {"id": UUID(VOCE_ID), "qta": Decimal("2.500"), "foto_paths": []}
    ]

    documento = asyncio.run(sal_service.get_sal_documento(conn, TENANT_ID, SAL_ID))

    assert documento["cantiere"]["id"] == CANTIERE_ID
    assert documento["tenant"]["id"] == TENANT_ID
    assert documento["misure"][0]["qta"] == 2.5
    cantiere_sql = conn.fetchrow.await_args_list[0].args[0]
    tenant_sql = conn.fetchrow.await_args_list[1].args[0]
    misure_sql = conn.fetch.await_args.args[0]
    assert "tenant_id = $2::uuid" in cantiere_sql
    assert "where id = $1::uuid" in tenant_sql
    assert "m.tenant_id = $2::uuid" in misure_sql
    assert "m.cantiere_id = $3::uuid" in misure_sql


def test_post_route_genera_sal_per_staff(monkeypatch):
    async def fake_user(request, db):
        return {"id": "user"}

    route_conn = AsyncMock()

    @asynccontextmanager
    async def tenant_conn(request, user):
        yield route_conn, {"id": TENANT_ID, "role": "staff"}

    genera = AsyncMock(return_value={"id": SAL_ID, "numero": 1, "stato": "bozza"})
    monkeypatch.setattr(edilos_routes, "_user", fake_user)
    monkeypatch.setattr(sal_service, "genera_sal", genera)
    api = APIRouter(prefix="/api")
    edilos_routes.register_edilos_routes(api, object(), tenant_conn)
    endpoint = next(
        route.endpoint
        for route in api.routes
        if route.path == "/api/cantieri/{cantiere_id}/sal"
        and "POST" in (route.methods or set())
    )
    body = edilos_routes.GeneraSalBody(periodo_da="2026-08-01", periodo_a="2026-08-31")

    result = asyncio.run(endpoint(_request(), CANTIERE_ID, body))

    assert result["id"] == SAL_ID
    genera.assert_awaited_once_with(
        route_conn,
        TENANT_ID,
        CANTIERE_ID,
        periodo_da=date(2026, 8, 1),
        periodo_a=date(2026, 8, 31),
    )


def test_post_route_blocca_ruolo_client(monkeypatch):
    async def fake_user(request, db):
        return {"id": "user"}

    @asynccontextmanager
    async def tenant_conn(request, user):
        yield AsyncMock(), {"id": TENANT_ID, "role": "client"}

    monkeypatch.setattr(edilos_routes, "_user", fake_user)
    api = APIRouter(prefix="/api")
    edilos_routes.register_edilos_routes(api, object(), tenant_conn)
    endpoint = next(
        route.endpoint
        for route in api.routes
        if route.path == "/api/cantieri/{cantiere_id}/sal"
        and "POST" in (route.methods or set())
    )
    body = edilos_routes.GeneraSalBody(periodo_da="2026-08-01", periodo_a="2026-08-31")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(_request(), CANTIERE_ID, body))
    assert exc.value.status_code == 403
