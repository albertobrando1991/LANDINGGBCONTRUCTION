from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

import client_portal_service
import contract_workflow_service
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
    assert callable(_endpoint("/api/leads/{lead_id}/portale", "GET"))
    assert callable(_endpoint("/api/leads/{lead_id}/portale/invita", "POST"))
    assert callable(_endpoint("/api/preventivi/{preventivo_id}/contratto/pdf", "GET"))
    assert callable(_endpoint("/api/preventivi/{preventivo_id}/contratto", "GET"))
    assert callable(
        _endpoint("/api/portal/preventivi/{preventivo_id}/modalita-pagamento", "PUT")
    )
    assert callable(_endpoint("/api/portal/documenti", "POST"))
    assert callable(_endpoint("/api/portal/documenti/{documento_id}/download", "GET"))
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
        [{"tenant_id": TENANT_ID, "incasso_id": "incasso-1", "residuo": 100}],
        [{"tenant_id": TENANT_ID, "documento_id": "documento-1"}],
    ]

    result = asyncio.run(client_portal_service.get_portal_dashboard(conn, TENANT_ID))

    assert result["varianti"][0]["righe"][0]["classificazione"] == "nuova"
    assert result["assets"][0]["tipo"] == "documento"
    assert result["pagamenti"][0]["residuo"] == 100
    assert result["documenti_economici"][0]["documento_id"] == "documento-1"
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
        lambda email, nome=None, **kwargs: (
            SimpleNamespace(id=USER_ID, email=email),
            True,
        ),
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


def test_scheda_lead_mostra_accesso_e_scelta_pagamento_del_preventivo_recente():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "preventivo_id": "40000000-0000-4000-8000-000000000001",
        "numero_preventivo": "PREV-2026-0042",
        "stato_preventivo": "inviato",
        "cliente_nome": "Cliente Test",
        "cliente_email": "cliente@example.com",
        "accesso_attivo": True,
        "modalita_pagamento": "sal",
        "pagamento_confermato_at": "2026-08-10T12:00:00Z",
    }

    result = asyncio.run(
        contract_workflow_service.get_lead_portal_access(
            conn,
            TENANT_ID,
            "50000000-0000-4000-8000-000000000001",
        )
    )

    assert result["available"] is True
    assert result["accesso_attivo"] is True
    assert result["pagamento_confermato"] is True
    assert result["modalita_pagamento"] == "sal"
    query = conn.fetchrow.await_args.args[0]
    assert "p.lead_id = $2::uuid" in query
    assert "order by p.created_at desc" in query.lower()


def test_scheda_lead_senza_preventivo_disabilita_invito_portale():
    conn = AsyncMock()
    conn.fetchrow.return_value = None

    result = asyncio.run(
        contract_workflow_service.get_lead_portal_access(
            conn,
            TENANT_ID,
            "50000000-0000-4000-8000-000000000001",
        )
    )

    assert result == {
        "available": False,
        "preventivo_id": None,
        "accesso_attivo": False,
        "pagamento_confermato": False,
    }


def test_reinvio_staff_non_riscrive_membership_cliente_esistente(monkeypatch):
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {
            "id": "40000000-0000-4000-8000-000000000001",
            "cliente_nome": "Cliente Test",
            "cliente_email": "cliente@example.com",
        },
        {
            "tenant_id": TENANT_ID,
            "preventivo_id": "40000000-0000-4000-8000-000000000001",
            "user_id": USER_ID,
            "email": "cliente@example.com",
            "attivo": True,
        },
    ]
    conn.fetchval.return_value = "client"
    monkeypatch.setattr(
        contract_workflow_service,
        "find_or_invite_user",
        lambda email, nome=None, **kwargs: (
            SimpleNamespace(id=USER_ID, email=email),
            False,
        ),
    )

    result = asyncio.run(
        contract_workflow_service.invite_preventivo_client(
            conn,
            TENANT_ID,
            "40000000-0000-4000-8000-000000000001",
            email="cliente@example.com",
            nome="Cliente Test",
        )
    )

    assert result["invited"] is False
    conn.execute.assert_not_awaited()


def test_nuovo_cliente_viene_inserito_senza_permesso_update(monkeypatch):
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {
            "id": "40000000-0000-4000-8000-000000000001",
            "cliente_nome": "Cliente Test",
            "cliente_email": "cliente@example.com",
        },
        {
            "tenant_id": TENANT_ID,
            "preventivo_id": "40000000-0000-4000-8000-000000000001",
            "user_id": USER_ID,
            "email": "cliente@example.com",
            "attivo": True,
        },
    ]
    conn.fetchval.side_effect = [None, "client"]
    monkeypatch.setattr(
        contract_workflow_service,
        "find_or_invite_user",
        lambda email, nome=None, **kwargs: (
            SimpleNamespace(id=USER_ID, email=email),
            True,
        ),
    )

    result = asyncio.run(
        contract_workflow_service.invite_preventivo_client(
            conn,
            TENANT_ID,
            "40000000-0000-4000-8000-000000000001",
            email="cliente@example.com",
            nome="Cliente Test",
        )
    )

    assert result["invited"] is True
    membership_sql = conn.execute.await_args.args[0].lower()
    assert "on conflict (tenant_id,user_id) do nothing" in membership_sql
    assert "do update" not in membership_sql


def test_policy_staff_consente_soltanto_inserimento_ruolo_client():
    migration = (
        Path(__file__).parents[2]
        / "supabase"
        / "migrations"
        / "20260810204601_allow_internal_client_invites.sql"
    ).read_text(encoding="utf-8")
    normalized = " ".join(migration.lower().split())

    assert "for insert to authenticated" in normalized
    assert "role = 'client'::public.tenant_role" in normalized
    assert "public.is_internal_member(tenant_id)" in normalized
    assert "create policy members_update" not in normalized
    assert "create policy members_delete" not in normalized


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


def test_nuovo_invito_genera_link_senza_email_supabase(monkeypatch):
    generated_calls = []
    sent = []
    user = SimpleNamespace(id=USER_ID, email="cliente@example.com")

    class FakeAdmin:
        def list_users(self, **kwargs):
            return SimpleNamespace(users=[])

        def generate_link(self, params):
            generated_calls.append(params)
            return SimpleNamespace(
                user=user,
                properties=SimpleNamespace(
                    action_link="https://project.supabase.co/auth/v1/verify?token=secret"
                ),
            )

    monkeypatch.setenv("APP_PUBLIC_URL", "https://gbconstruction.it")
    monkeypatch.setattr(
        client_invites,
        "_supabase_admin",
        lambda: SimpleNamespace(auth=SimpleNamespace(admin=FakeAdmin())),
    )
    monkeypatch.setattr(client_invites.email_service, "is_configured", lambda: True)
    monkeypatch.setattr(
        client_invites.email_service,
        "send_client_portal_invite",
        lambda **kwargs: sent.append(kwargs),
    )

    result, invited = client_invites.find_or_invite_user(
        "Cliente@Example.com", "Mario Rossi", context="preventivo"
    )

    assert result is user
    assert invited is True
    assert generated_calls == [
        {
            "type": "invite",
            "email": "cliente@example.com",
            "options": {
                "redirect_to": "https://gbconstruction.it/set-password",
                "data": {"name": "Mario Rossi"},
            },
        }
    ]
    assert sent == [
        {
            "to_email": "cliente@example.com",
            "nome": "Mario Rossi",
            "action_url": "https://project.supabase.co/auth/v1/verify?token=secret",
            "context": "preventivo",
        }
    ]


def test_utente_esistente_confermato_riceve_accesso_gb(monkeypatch):
    sent = []
    user = SimpleNamespace(
        id=USER_ID,
        email="cliente@example.com",
        email_confirmed_at="2026-08-10T12:00:00Z",
        confirmed_at=None,
    )

    class FakeAdmin:
        def list_users(self, **kwargs):
            return SimpleNamespace(users=[user])

        def generate_link(self, params):
            raise AssertionError("Un utente confermato non richiede un nuovo token")

    monkeypatch.setenv("APP_PUBLIC_URL", "https://gbconstruction.it")
    monkeypatch.setattr(
        client_invites,
        "_supabase_admin",
        lambda: SimpleNamespace(auth=SimpleNamespace(admin=FakeAdmin())),
    )
    monkeypatch.setattr(client_invites.email_service, "is_configured", lambda: True)
    monkeypatch.setattr(
        client_invites.email_service,
        "send_client_portal_invite",
        lambda **kwargs: sent.append(kwargs),
    )

    result, invited = client_invites.find_or_invite_user(
        "cliente@example.com", "Mario Rossi", context="cantiere"
    )

    assert result is user
    assert invited is False
    assert sent[0]["action_url"] == "https://gbconstruction.it/portal"
    assert sent[0]["context"] == "cantiere"


def test_utente_non_confermato_puo_ricevere_di_nuovo_invito_gb(monkeypatch):
    generated_calls = []
    sent = []
    user = SimpleNamespace(
        id=USER_ID,
        email="cliente@example.com",
        email_confirmed_at=None,
        confirmed_at=None,
    )

    class FakeAdmin:
        def list_users(self, **kwargs):
            return SimpleNamespace(users=[user])

        def generate_link(self, params):
            generated_calls.append(params)
            return SimpleNamespace(
                user=user,
                properties=SimpleNamespace(action_link="https://auth/retry"),
            )

    monkeypatch.setattr(
        client_invites,
        "_supabase_admin",
        lambda: SimpleNamespace(auth=SimpleNamespace(admin=FakeAdmin())),
    )
    monkeypatch.setattr(client_invites.email_service, "is_configured", lambda: True)
    monkeypatch.setattr(
        client_invites.email_service,
        "send_client_portal_invite",
        lambda **kwargs: sent.append(kwargs),
    )

    result, invited = client_invites.find_or_invite_user(
        "cliente@example.com", "Mario Rossi"
    )

    assert result is user
    assert invited is False
    assert generated_calls[0]["type"] == "magiclink"
    assert sent[0]["action_url"] == "https://auth/retry"


def test_invito_si_blocca_prima_di_supabase_se_email_gb_non_configurata(
    monkeypatch,
):
    monkeypatch.setattr(client_invites.email_service, "is_configured", lambda: False)
    monkeypatch.setattr(
        client_invites,
        "_supabase_admin",
        lambda: (_ for _ in ()).throw(AssertionError("Supabase non va chiamato")),
    )

    with pytest.raises(HTTPException) as exc:
        client_invites.find_or_invite_user("cliente@example.com")

    assert exc.value.status_code == 503
    assert "email ufficiale GB" in str(exc.value.detail)
