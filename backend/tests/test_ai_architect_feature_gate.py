import asyncio
import re
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

import server


def _request(path="/api/ai-architect/jobs", method="GET"):
    return SimpleNamespace(url=SimpleNamespace(path=path), method=method)


async def _ok_response(_request):
    return JSONResponse({"ok": True})


def test_private_beta_blocks_anonymous_ai_routes(monkeypatch):
    monkeypatch.delenv("AI_ARCHITECT_PUBLIC_ENABLED", raising=False)

    async def anonymous(_request):
        raise HTTPException(status_code=401, detail="Non autenticato")

    monkeypatch.setattr(server, "current_user", anonymous)
    response = asyncio.run(
        server.ai_architect_beta_access(_request(), _ok_response)
    )

    assert response.status_code == 404


def test_private_beta_allows_authenticated_staff(monkeypatch):
    monkeypatch.setenv("AI_ARCHITECT_PUBLIC_ENABLED", "false")

    async def staff(_request):
        return {"id": "staff-1", "role": "staff"}

    monkeypatch.setattr(server, "current_user", staff)
    response = asyncio.run(
        server.ai_architect_beta_access(_request(), _ok_response)
    )

    assert response.status_code == 200


def test_private_beta_rejects_authenticated_non_staff(monkeypatch):
    monkeypatch.setenv("AI_ARCHITECT_PUBLIC_ENABLED", "false")

    async def customer(_request):
        return {"id": "customer-1", "role": "customer"}

    monkeypatch.setattr(server, "current_user", customer)
    response = asyncio.run(
        server.ai_architect_beta_access(_request(), _ok_response)
    )

    assert response.status_code == 404


def test_public_flag_allows_anonymous_ai_routes(monkeypatch):
    monkeypatch.setenv("AI_ARCHITECT_PUBLIC_ENABLED", "true")

    async def must_not_authenticate(_request):
        raise AssertionError("La route pubblica non deve richiedere login")

    monkeypatch.setattr(server, "current_user", must_not_authenticate)
    response = asyncio.run(
        server.ai_architect_beta_access(_request(), _ok_response)
    )

    assert response.status_code == 200


def test_private_beta_does_not_gate_other_routes(monkeypatch):
    monkeypatch.setenv("AI_ARCHITECT_PUBLIC_ENABLED", "false")
    response = asyncio.run(
        server.ai_architect_beta_access(_request("/api/health"), _ok_response)
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
