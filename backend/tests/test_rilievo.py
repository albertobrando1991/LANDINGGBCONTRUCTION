"""Test del Primo rilievo Campo Fase 1."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
import fitz
from fastapi import APIRouter, HTTPException, Request

import edilos_routes
import rilievo_service

TENANT_ID = "a0000000-0000-4000-8000-000000000001"
RILIEVO_ID = "10000000-0000-4000-8000-000000000001"
AMBIENTE_CLIENT_UUID = "20000000-0000-4000-8000-000000000001"


def _request(method: str = "GET") -> Request:
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


def _rilievo(**overrides):
    row = {
        "id": UUID(RILIEVO_ID),
        "tenant_id": UUID(TENANT_ID),
        "client_uuid": UUID("30000000-0000-4000-8000-000000000001"),
        "cliente": "Cliente prova",
        "data_rilievo": date(2026, 8, 9),
        "stato": "bozza",
        "planimetria_data": {"version": 1, "elementi": []},
        "foto_paths": [],
    }
    row.update(overrides)
    return row


def _ambiente(**overrides):
    row = {
        "id": UUID("40000000-0000-4000-8000-000000000001"),
        "tenant_id": UUID(TENANT_ID),
        "rilievo_id": UUID(RILIEVO_ID),
        "client_uuid": UUID(AMBIENTE_CLIENT_UUID),
        "nome": "Cucina",
        "lunghezza": Decimal("4.000"),
        "larghezza": Decimal("3.000"),
        "altezza": Decimal("2.700"),
        "superficie": Decimal("12.000"),
        "misure_extra": [],
        "foto_paths": [],
    }
    row.update(overrides)
    return row


def test_route_rilievi_e_ambienti_registrate():
    api = APIRouter(prefix="/api")
    edilos_routes.register_edilos_routes(api, object(), object())
    routes = {(route.path, tuple(sorted(route.methods or []))) for route in api.routes}

    assert any(
        path == "/api/campo/rilievi" and "GET" in methods for path, methods in routes
    )
    assert any(
        path == "/api/campo/rilievi" and "POST" in methods for path, methods in routes
    )
    assert any(
        path == "/api/campo/rilievi/{rilievo_id}/ambienti/{ambiente_client_uuid}"
        and "PUT" in methods
        for path, methods in routes
    )
    assert any(
        path == "/api/campo/rilievi/{rilievo_id}/tavola" and "PUT" in methods
        for path, methods in routes
    )
    assert any(
        path == "/api/campo/rilievi/{rilievo_id}/planimetria/preview"
        and "POST" in methods
        for path, methods in routes
    )


def test_crea_rilievo_upsert_idempotente_tenant_scoped():
    conn = AsyncMock()
    conn.fetchrow.return_value = _rilievo()

    result = asyncio.run(
        rilievo_service.crea_rilievo(
            conn,
            TENANT_ID,
            client_uuid="30000000-0000-4000-8000-000000000001",
            cliente="Cliente prova",
            data_rilievo=date(2026, 8, 9),
        )
    )

    sql = conn.fetchrow.await_args.args[0]
    assert "on conflict (tenant_id, client_uuid) do update" in sql
    assert "auth.uid()" in sql
    assert result["id"] == RILIEVO_ID


def test_salva_ambiente_calcola_superficie_e_valida_path_foto():
    conn = AsyncMock()
    conn.fetchrow.side_effect = [_rilievo(), _ambiente()]
    path = (
        f"{TENANT_ID}/rilievo-{RILIEVO_ID}/" f"ambiente-{AMBIENTE_CLIENT_UUID}/foto.jpg"
    )

    result = asyncio.run(
        rilievo_service.salva_ambiente(
            conn,
            TENANT_ID,
            RILIEVO_ID,
            AMBIENTE_CLIENT_UUID,
            nome="Cucina",
            lunghezza=Decimal("4"),
            larghezza=Decimal("3"),
            altezza=Decimal("2.7"),
            foto_paths=[path],
        )
    )

    insert = conn.fetchrow.await_args_list[1]
    assert (
        "on conflict (tenant_id, rilievo_id, client_uuid) do update" in insert.args[0]
    )
    assert Decimal("12.000") in insert.args
    assert result["superficie"] == 12.0


def test_salva_ambiente_blocca_foto_di_un_altro_rilievo():
    conn = AsyncMock()
    conn.fetchrow.return_value = _rilievo()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            rilievo_service.salva_ambiente(
                conn,
                TENANT_ID,
                RILIEVO_ID,
                AMBIENTE_CLIENT_UUID,
                nome="Bagno",
                foto_paths=[f"{TENANT_ID}/rilievo-altro/foto.jpg"],
            )
        )

    assert exc.value.status_code == 400


def test_render_pdf_preview_restituisce_png():
    document = fitz.open()
    page = document.new_page(width=600, height=400)
    page.draw_rect(fitz.Rect(40, 40, 560, 360))
    content = document.tobytes()
    document.close()

    preview = rilievo_service.render_pdf_preview(content)

    assert preview.startswith(b"\x89PNG\r\n\x1a\n")


def test_salva_tavola_valida_asset_tenant_scoped():
    conn = AsyncMock()
    plan = f"{TENANT_ID}/rilievo-{RILIEVO_ID}/planimetria/originale-casa.pdf"
    preview = f"{TENANT_ID}/rilievo-{RILIEVO_ID}/planimetria/preview.png"
    photo = f"{TENANT_ID}/rilievo-{RILIEVO_ID}/generali/foto.jpg"
    saved = _rilievo(
        planimetria_path=plan,
        planimetria_preview_path=preview,
        foto_paths=[photo],
    )
    conn.fetchrow.side_effect = [_rilievo(), {"id": UUID(RILIEVO_ID)}, saved]
    conn.fetch.return_value = []

    result = asyncio.run(
        rilievo_service.salva_tavola(
            conn,
            TENANT_ID,
            RILIEVO_ID,
            planimetria_path=plan,
            planimetria_preview_path=preview,
            planimetria_filename="casa.pdf",
            planimetria_mime_type="application/pdf",
            planimetria_data={"version": 1, "elementi": []},
            foto_paths=[photo],
        )
    )

    update = conn.fetchrow.await_args_list[1]
    assert "planimetria_data = $7::jsonb" in update.args[0]
    assert result["planimetria_path"] == plan
    assert result["n_foto_generali"] == 1


def test_salva_tavola_blocca_foto_generale_di_un_altro_rilievo():
    conn = AsyncMock()
    conn.fetchrow.return_value = _rilievo()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            rilievo_service.salva_tavola(
                conn,
                TENANT_ID,
                RILIEVO_ID,
                planimetria_path=None,
                planimetria_preview_path=None,
                planimetria_filename=None,
                planimetria_mime_type=None,
                planimetria_data={"version": 1, "elementi": []},
                foto_paths=[f"{TENANT_ID}/rilievo-altro/generali/foto.jpg"],
            )
        )

    assert exc.value.status_code == 400
    assert "foto generali" in exc.value.detail.lower()


def test_completa_rilievo_richiede_almeno_un_ambiente():
    conn = AsyncMock()
    conn.fetchrow.return_value = _rilievo()
    conn.fetchval.return_value = 0

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            rilievo_service.aggiorna_rilievo(
                conn, TENANT_ID, RILIEVO_ID, {"stato": "completato"}
            )
        )

    assert exc.value.status_code == 409
    assert "ambiente" in exc.value.detail.lower()


def test_route_blocca_ruolo_client(monkeypatch):
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
        if route.path == "/api/campo/rilievi" and "GET" in (route.methods or set())
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(_request()))
    assert exc.value.status_code == 403
