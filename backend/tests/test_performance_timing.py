from __future__ import annotations

import asyncio

from fastapi import Request
from fastapi.responses import JSONResponse

import server


def test_performance_middleware_exposes_action_timing(monkeypatch):
    monkeypatch.setenv("SLOW_REQUEST_MS", "10000")
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "PATCH",
            "scheme": "https",
            "path": "/api/cantieri/example",
            "raw_path": b"/api/cantieri/example",
            "query_string": b"",
            "headers": [(b"x-request-id", b"test-request")],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 443),
        }
    )

    async def call_next(_request):
        return JSONResponse({"ok": True})

    response = asyncio.run(server.performance_timing(request, call_next))

    assert response.headers["server-timing"].startswith("app;dur=")
    assert float(response.headers["x-response-time-ms"]) >= 0
    assert response.headers["x-request-id"] == "test-request"
