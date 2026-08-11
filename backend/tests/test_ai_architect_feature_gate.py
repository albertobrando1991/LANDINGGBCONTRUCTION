import asyncio
import re
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

import server


def _request(path="/api/ai-architect/jobs", method="GET"):
    return SimpleNamespace(url=SimpleNamespace(path=path), method=method)


async def _ok_response(_request):
    return JSONResponse({"ok": True})


def test_staff_gate_blocks_anonymous_ai_routes(monkeypatch):
    async def anonymous(_request):
        raise HTTPException(status_code=401, detail="Non autenticato")

    monkeypatch.setattr(server, "current_user", anonymous)
    response = asyncio.run(
        server.ai_architect_staff_access(_request(), _ok_response)
    )

    assert response.status_code == 404


def test_staff_gate_allows_authenticated_staff(monkeypatch):
    async def staff(_request):
        return {"id": "staff-1", "role": "staff"}

    monkeypatch.setattr(server, "current_user", staff)
    response = asyncio.run(
        server.ai_architect_staff_access(_request(), _ok_response)
    )

    assert response.status_code == 200


def test_staff_gate_rejects_authenticated_non_staff(monkeypatch):
    async def customer(_request):
        return {"id": "customer-1", "role": "customer"}

    monkeypatch.setattr(server, "current_user", customer)
    response = asyncio.run(
        server.ai_architect_staff_access(_request(), _ok_response)
    )

    assert response.status_code == 404


def test_public_flag_cannot_expose_ai_routes(monkeypatch):
    monkeypatch.setenv("AI_ARCHITECT_PUBLIC_ENABLED", "true")

    async def anonymous(_request):
        raise HTTPException(status_code=401, detail="Non autenticato")

    monkeypatch.setattr(server, "current_user", anonymous)
    response = asyncio.run(
        server.ai_architect_staff_access(_request(), _ok_response)
    )

    assert response.status_code == 404


def test_staff_gate_does_not_gate_other_routes(monkeypatch):
    response = asyncio.run(
        server.ai_architect_staff_access(_request("/api/health"), _ok_response)
    )

    assert response.status_code == 200


def test_production_cors_accepts_only_gb_frontends():
    for origin in (
        "https://gbconstruction.it",
        "https://www.gbconstruction.it",
        "https://app.gbconstruction.it",
    ):
        assert re.fullmatch(server.DEFAULT_CORS_ORIGIN_REGEX, origin)

    assert not re.fullmatch(
        server.DEFAULT_CORS_ORIGIN_REGEX, "https://demo.alantis.it"
    )
    assert not re.fullmatch(
        server.DEFAULT_CORS_ORIGIN_REGEX, "https://example.invalid"
    )


def test_production_cors_accepts_campo_put_preflight():
    client = TestClient(server.app)
    try:
        response = client.options(
            "/api/campo/rilievi/ab35adfc-2a06-43f9-b8d5-39c3df128b78/ambienti/"
            "bfbcc0c0-1be0-4d09-9f60-2e0b3436b3ff",
            headers={
                "Origin": "https://app.gbconstruction.it",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": (
                    "authorization,content-type,x-tenant-slug"
                ),
            },
        )
    finally:
        client.close()

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://app.gbconstruction.it"
    )
    assert "PUT" in response.headers["access-control-allow-methods"]


def test_ai_architect_creation_is_available_only_on_staff_route():
    public_routes = [
        route
        for route in server.api.routes
        if route.path == "/api/ai-architect/jobs" and "POST" in route.methods
    ]
    staff_routes = [
        route
        for route in server.api.routes
        if route.path == "/api/ai-architect/staff/jobs" and "POST" in route.methods
    ]

    assert public_routes == []
    assert len(staff_routes) == 1


def test_preventivo_da_progetto_ai_rifiuta_utenti_non_staff():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            server.quote_from_ai_project(
                _request("/api/quote/from-ai-project", method="POST"),
                SimpleNamespace(),
                SimpleNamespace(),
                {"id": "customer-1", "role": "customer"},
            )
        )

    assert exc.value.status_code == 403
