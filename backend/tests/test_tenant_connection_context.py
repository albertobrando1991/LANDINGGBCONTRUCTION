from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import legacy_tenant
import server


def test_errore_route_non_attiva_fallback_connessione(monkeypatch):
    fallback_calls = []

    @asynccontextmanager
    async def token_connection(_token):
        yield object()

    @asynccontextmanager
    async def claims_connection(_claims):
        fallback_calls.append(True)
        yield object()

    monkeypatch.setattr(server.db_pg, "pool_ready", lambda: True)
    monkeypatch.setattr(server.db_pg, "tenant_conn", token_connection)
    monkeypatch.setattr(server.db_pg, "tenant_conn_claims", claims_connection)
    monkeypatch.setattr(legacy_tenant, "map_legacy_user", lambda user: user)
    monkeypatch.setattr(legacy_tenant, "claims_for_user", lambda _user: {})

    async def current_tenant(_request, _user, *, conn):
        return {"id": "a0000000-0000-4000-8000-000000000001", "role": "client"}

    monkeypatch.setattr(server.tenancy, "current_tenant", current_tenant)

    async def exercise():
        with pytest.raises(RuntimeError, match="errore route originale"):
            async with server.get_tenant_conn(
                SimpleNamespace(),
                {"auth_provider": "supabase", "access_token": "presente"},
            ):
                raise RuntimeError("errore route originale")

    import asyncio

    asyncio.run(exercise())
    assert fallback_calls == []
