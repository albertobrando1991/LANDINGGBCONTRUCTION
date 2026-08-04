import asyncio
from types import SimpleNamespace

from fastapi import HTTPException
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
