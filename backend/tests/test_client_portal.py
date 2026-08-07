from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import client_portal_service
import edilos_routes
from server import api
from system_jobs import client_invites

TENANT_ID = "a0000000-0000-4000-8000-000000000001"
CANTIERE_ID = "10000000-0000-4000-8000-000000000001"
VARIANTE_ID = "20000000-0000-4000-8000-000000000001"
USER_ID = "f1000000-0000-4000-8000-000000000004"


def _endpoint(path: str, method: str):
    for route in api.routes:
        if route.path == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route {method} {path} non registrata")


def test_route_portale_complete_sono_registrate():
    assert callable(_endpoint("/api/portal", "GET"))
    assert callable(
        _endpoint(
            "/api/portal/cantieri/{cantiere_id}/varianti/{variante_id}/approva",
            "POST",
        )
    )
    assert callable(_endpoint("/api/cantieri/{cantiere_id}/portale", "GET"))
    assert callable(_endpoint("/api/cantieri/{cantiere_id}/portale/invita", "POST"))
    assert callable(
        _endpoint("/api/cantieri/{cantiere_id}/portale/condivisioni", "POST")
    )


def test_dashboard_assembla_righe_variante_senza_perdere_tenant_filter():
    conn = AsyncMock()
    conn.fetch.side_effect = [
        [{"tenant_id": TENANT_ID, "cantiere_id": CANTIERE_ID}],
        [{"tenant_id": TENANT_ID, "sal_id": "s1", "righe": []}],
        [{"tenant_id": TENANT_ID, "variante_id": VARIANTE_ID}],
        [
            {
                "tenant_id": TENANT_ID,
                "variante_id": VARIANTE_ID,
                "classificazione": "nuova",
            }
        ],
        [{"tenant_id": TENANT_ID, "id": "asset-1", "tipo": "documento"}],
    ]

    result = asyncio.run(client_portal_service.get_portal_dashboard(conn, TENANT_ID))

    assert result["varianti"][0]["righe"][0]["classificazione"] == "nuova"
    assert result["assets"][0]["tipo"] == "documento"
    assert all(call.args[-1] == TENANT_ID for call in conn.fetch.await_args_list)


def test_approvazione_e_idempotente_e_conserva_audit():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "id": "30000000-0000-4000-8000-000000000001",
        "tenant_id": TENANT_ID,
        "cantiere_id": CANTIERE_ID,
        "variante_id": VARIANTE_ID,
        "user_id": USER_ID,
        "ip": "127.0.0.1",
        "created": True,
    }

    result = asyncio.run(
        client_portal_service.approva_variante(
            conn,
            TENANT_ID,
            CANTIERE_ID,
            VARIANTE_ID,
            USER_ID,
            ip="127.0.0.1",
            user_agent="pytest",
        )
    )

    assert result["created"] is True
    assert result["ip"] == "127.0.0.1"
    query = conn.fetchrow.await_args.args[0]
    assert "private.approva_variante_cliente" in query


def test_condivisione_blocca_path_di_un_altro_cantiere():
    conn = AsyncMock()
    conn.fetchval.return_value = True

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            client_portal_service.condividi_asset(
                conn,
                TENANT_ID,
                CANTIERE_ID,
                tipo="documento",
                bucket="documenti",
                storage_path=f"{TENANT_ID}/cantiere-altro/segreto.pdf",
                titolo="Segreto",
                descrizione=None,
            )
        )

    assert exc.value.status_code == 400
    assert "Percorso" in str(exc.value.detail)


def test_invito_collega_utente_supabase_come_client(monkeypatch):
    conn = AsyncMock()
    conn.fetchval.side_effect = [True, None]
    conn.fetchrow.return_value = {
        "tenant_id": TENANT_ID,
        "cantiere_id": CANTIERE_ID,
        "user_id": USER_ID,
        "email": "cliente@example.com",
        "attivo": True,
    }
    monkeypatch.setattr(
        client_portal_service,
        "find_or_invite_user",
        lambda email, nome=None: (SimpleNamespace(id=USER_ID, email=email), True),
    )

    result = asyncio.run(
        client_portal_service.invita_cliente(
            conn,
            TENANT_ID,
            CANTIERE_ID,
            email="Cliente@Example.com",
            nome="Cliente Test",
        )
    )

    assert result["invited"] is True
    assert result["email"] == "cliente@example.com"
    assert conn.execute.await_count == 1


def test_request_ip_scartando_header_non_valido():
    request = SimpleNamespace(
        headers={"x-forwarded-for": "non-un-ip"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert edilos_routes._request_ip(request) == "0.0.0.0"


def test_inviti_usano_secret_key_moderna(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co/")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_current")

    assert client_invites._supabase_credentials() == (
        "https://project.supabase.co",
        "sb_secret_current",
    )
