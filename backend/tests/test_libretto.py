"""API e servizio del libretto di misura append-only."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import ValidationError

import edilos_routes
import libretto_service

TENANT_ID = "a0000000-0000-4000-8000-000000000001"
CANTIERE_ID = "10000000-0000-4000-8000-000000000001"
VOCE_ID = "20000000-0000-4000-8000-000000000001"
CLIENT_UUID = "30000000-0000-4000-8000-000000000001"
MISURA_ID = "40000000-0000-4000-8000-000000000001"


def _misura(**overrides):
    row = {
        "id": UUID(MISURA_ID),
        "tenant_id": UUID(TENANT_ID),
        "cantiere_id": UUID(CANTIERE_ID),
        "computo_voce_id": UUID(VOCE_ID),
        "data_misura": date(2026, 8, 5),
        "rilevata_da": UUID("f1000000-0000-4000-8000-000000000001"),
        "descrizione": "Parete cucina",
        "parti": 1,
        "lunghezza": Decimal("2.500"),
        "larghezza": Decimal("3.000"),
        "altezza": None,
        "qta": Decimal("7.500"),
        "foto_paths": [],
        "client_uuid": UUID(CLIENT_UUID),
    }
    row.update(overrides)
    return row


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


def _route(method: str):
    api = APIRouter(prefix="/api")
    edilos_routes.register_edilos_routes(api, object(), object())
    return next(
        route.endpoint
        for route in api.routes
        if route.path == "/api/cantieri/{cantiere_id}/libretto-misure"
        and method in (route.methods or set())
    )


def test_route_get_e_post_sono_registrate():
    assert callable(_route("GET"))
    assert callable(_route("POST"))


def test_body_accetta_correzioni_negative_ma_non_quantita_zero():
    body = edilos_routes.CreaMisuraBody(
        client_uuid=CLIENT_UUID,
        data_misura="2026-08-05",
        qta="-1.250",
    )
    assert body.qta == Decimal("-1.250")

    with pytest.raises(ValidationError):
        edilos_routes.CreaMisuraBody(
            client_uuid=CLIENT_UUID,
            data_misura="2026-08-05",
            qta="0",
        )


def test_registra_misura_usa_insert_atomico_append_only():
    conn = AsyncMock()
    conn.fetchval.side_effect = [True, True]
    conn.fetchrow.return_value = _misura()

    result, created = asyncio.run(
        libretto_service.registra_misura(
            conn,
            TENANT_ID,
            CANTIERE_ID,
            client_uuid=CLIENT_UUID,
            data_misura=date(2026, 8, 5),
            qta=Decimal("7.500"),
            computo_voce_id=VOCE_ID,
            descrizione="Parete cucina",
            lunghezza=Decimal("2.500"),
            larghezza=Decimal("3.000"),
        )
    )

    assert created is True
    assert result["id"] == MISURA_ID
    insert_call = conn.fetchrow.await_args
    assert "on conflict (tenant_id, client_uuid) do nothing" in insert_call.args[0]
    assert "auth.uid()" in insert_call.args[0]
    assert "do update" not in insert_call.args[0].lower()
    assert insert_call.args[1:4] == (TENANT_ID, CANTIERE_ID, VOCE_ID)


def test_retry_identico_restituisce_la_misura_senza_update():
    conn = AsyncMock()
    conn.fetchval.side_effect = [True, True]
    conn.fetchrow.side_effect = [None, _misura()]

    result, created = asyncio.run(
        libretto_service.registra_misura(
            conn,
            TENANT_ID,
            CANTIERE_ID,
            client_uuid=CLIENT_UUID,
            data_misura=date(2026, 8, 5),
            qta=Decimal("7.500"),
            computo_voce_id=VOCE_ID,
            descrizione="Parete cucina",
            lunghezza=Decimal("2.500"),
            larghezza=Decimal("3.000"),
        )
    )

    assert created is False
    assert result["client_uuid"] == CLIENT_UUID
    assert conn.fetchrow.await_count == 2
    retry_call = conn.fetchrow.await_args_list[1]
    assert "tenant_id = $1::uuid and client_uuid = $2::uuid" in retry_call.args[0]
    assert retry_call.args[1:] == (TENANT_ID, CLIENT_UUID)


def test_retry_con_payload_diverso_restituisce_409():
    conn = AsyncMock()
    conn.fetchval.side_effect = [True, True]
    conn.fetchrow.side_effect = [None, _misura()]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            libretto_service.registra_misura(
                conn,
                TENANT_ID,
                CANTIERE_ID,
                client_uuid=CLIENT_UUID,
                data_misura=date(2026, 8, 5),
                qta=Decimal("9.000"),
                computo_voce_id=VOCE_ID,
                descrizione="Parete cucina",
                lunghezza=Decimal("2.500"),
                larghezza=Decimal("3.000"),
            )
        )

    assert exc.value.status_code == 409
    assert "misura diversa" in exc.value.detail


def test_lista_misure_filtra_tenant_cantiere_e_intervallo():
    conn = AsyncMock()
    conn.fetchval.return_value = True
    conn.fetch.return_value = [_misura(computo_voce_qta=Decimal("10.000"))]

    rows = asyncio.run(
        libretto_service.lista_misure(
            conn,
            TENANT_ID,
            CANTIERE_ID,
            data_da=date(2026, 8, 1),
            data_a=date(2026, 8, 31),
            limit=50,
        )
    )

    assert rows[0]["qta"] == 7.5
    query_call = conn.fetch.await_args
    assert "m.tenant_id = $1::uuid" in query_call.args[0]
    assert "m.cantiere_id = $2::uuid" in query_call.args[0]
    assert "m.data_misura >= $3::date" in query_call.args[0]
    assert "m.data_misura <= $4::date" in query_call.args[0]
    assert query_call.args[1:] == (
        TENANT_ID,
        CANTIERE_ID,
        date(2026, 8, 1),
        date(2026, 8, 31),
        50,
    )


def test_blocca_voce_di_un_altro_cantiere_e_path_foto_estraneo():
    conn = AsyncMock()
    conn.fetchval.side_effect = [True, False]
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            libretto_service.registra_misura(
                conn,
                TENANT_ID,
                CANTIERE_ID,
                client_uuid=CLIENT_UUID,
                data_misura=date(2026, 8, 5),
                qta=Decimal("1"),
                computo_voce_id=VOCE_ID,
            )
        )
    assert exc.value.status_code == 404

    conn = AsyncMock()
    conn.fetchval.return_value = True
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            libretto_service.registra_misura(
                conn,
                TENANT_ID,
                CANTIERE_ID,
                client_uuid=CLIENT_UUID,
                data_misura=date(2026, 8, 5),
                qta=Decimal("1"),
                foto_paths=["a0000000-0000-4000-8000-000000000002/other.jpg"],
            )
        )
    assert exc.value.status_code == 400
    assert conn.fetchrow.await_count == 0


def test_post_route_restituisce_200_sul_retry(monkeypatch):
    async def fake_user(request, db):
        return {"id": "user"}

    @asynccontextmanager
    async def tenant_conn(request, user):
        yield AsyncMock(), {"id": TENANT_ID, "role": "staff"}

    registra = AsyncMock(return_value=(_misura(), False))
    monkeypatch.setattr(edilos_routes, "_user", fake_user)
    monkeypatch.setattr(libretto_service, "registra_misura", registra)
    api = APIRouter(prefix="/api")
    edilos_routes.register_edilos_routes(api, object(), tenant_conn)
    endpoint = next(
        route.endpoint
        for route in api.routes
        if route.path == "/api/cantieri/{cantiere_id}/libretto-misure"
        and "POST" in (route.methods or set())
    )
    response = Response()
    body = edilos_routes.CreaMisuraBody(
        client_uuid=CLIENT_UUID,
        data_misura="2026-08-05",
        qta="7.500",
        computo_voce_id=VOCE_ID,
        descrizione="Parete cucina",
    )

    result = asyncio.run(endpoint(_request(), CANTIERE_ID, body, response))

    assert response.status_code == 200
    assert result["created"] is False
    assert result["misura"]["id"] == UUID(MISURA_ID)
    registra.assert_awaited_once()


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
        if route.path == "/api/cantieri/{cantiere_id}/libretto-misure"
        and "POST" in (route.methods or set())
    )
    body = edilos_routes.CreaMisuraBody(
        client_uuid=CLIENT_UUID,
        data_misura="2026-08-05",
        qta="1",
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(_request(), CANTIERE_ID, body, Response()))
    assert exc.value.status_code == 403
