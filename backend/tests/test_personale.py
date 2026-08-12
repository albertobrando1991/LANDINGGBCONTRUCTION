"""Personale e assegnazioni: tenant isolation, CRUD e transizioni."""
from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import HTTPException

import personale_service


TENANT_ID = "a0000000-0000-4000-8000-000000000001"
CANTIERE_ID = "10000000-0000-4000-8000-000000000001"
PERSONALE_ID = "20000000-0000-4000-8000-000000000001"
ASSEGNAZIONE_ID = "30000000-0000-4000-8000-000000000001"
PRESENZA_ID = "50000000-0000-4000-8000-000000000001"


def test_get_personale_filtra_tenant_tipo_e_attivo():
    conn = AsyncMock()
    conn.fetch.return_value = [
        {
            "id": UUID(PERSONALE_ID),
            "tenant_id": UUID(TENANT_ID),
            "tipo": "interno",
            "nome": "Mario Rossi",
            "costo_giornaliero": Decimal("150.00"),
        }
    ]

    result = asyncio.run(
        personale_service.get_personale(
            conn, TENANT_ID, tipo="interno", attivo=True
        )
    )

    assert result[0]["id"] == PERSONALE_ID
    assert result[0]["costo_giornaliero"] == 150.0
    query = conn.fetch.await_args
    assert "p.tenant_id = $1::uuid" in query.args[0]
    assert query.args[1:] == (TENANT_ID, "interno", True)


def test_crea_personale_verifica_fornitore_del_tenant():
    conn = AsyncMock()
    conn.fetchval.return_value = True
    conn.fetchrow.return_value = {
        "id": UUID(PERSONALE_ID),
        "tenant_id": UUID(TENANT_ID),
        "tipo": "subappaltatore",
        "nome": "Squadra Alfa",
    }
    fornitore_id = "40000000-0000-4000-8000-000000000001"

    result = asyncio.run(
        personale_service.crea_personale(
            conn,
            TENANT_ID,
            {
                "tipo": "subappaltatore",
                "nome": " Squadra Alfa ",
                "fornitore_id": fornitore_id,
            },
        )
    )

    assert result["nome"] == "Squadra Alfa"
    reference = conn.fetchval.await_args
    assert "public.fornitori" in reference.args[0]
    assert reference.args[1:] == (TENANT_ID, fornitore_id)
    assert "insert into public.personale" in conn.fetchrow.await_args.args[0]


def test_crea_assegnazione_valida_cantiere_e_persona_del_tenant():
    conn = AsyncMock()
    conn.fetchval.side_effect = [True, True]
    conn.fetchrow.return_value = {
        "id": UUID(ASSEGNAZIONE_ID),
        "tenant_id": UUID(TENANT_ID),
        "cantiere_id": UUID(CANTIERE_ID),
        "personale_id": UUID(PERSONALE_ID),
        "stato": "assegnato",
    }

    result = asyncio.run(
        personale_service.crea_assegnazione(
            conn,
            TENANT_ID,
            {
                "cantiere_id": CANTIERE_ID,
                "personale_id": PERSONALE_ID,
                "data_da": date(2026, 8, 11),
                "stato": "assegnato",
            },
        )
    )

    assert result["id"] == ASSEGNAZIONE_ID
    assert conn.fetchval.await_count == 2
    assert "public.cantieri" in conn.fetchval.await_args_list[0].args[0]
    assert "public.personale" in conn.fetchval.await_args_list[1].args[0]
    insert = conn.fetchrow.await_args
    assert "insert into public.cantiere_personale" in insert.args[0]
    assert "on conflict (id) do update" in insert.args[0]
    assert "cantiere_personale.tenant_id = excluded.tenant_id" in insert.args[0]
    assert insert.args[1] is None


def test_crea_assegnazione_blocca_persona_di_altro_tenant():
    conn = AsyncMock()
    conn.fetchval.side_effect = [True, False]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            personale_service.crea_assegnazione(
                conn,
                TENANT_ID,
                {
                    "cantiere_id": CANTIERE_ID,
                    "personale_id": PERSONALE_ID,
                    "data_da": date(2026, 8, 11),
                },
            )
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Persona non trovato"
    assert conn.fetchrow.await_count == 0


def test_aggiorna_assegnazione_transizione_stato_e_periodo():
    conn = AsyncMock()
    conn.fetchrow.side_effect = [
        {
            "cantiere_id": UUID(CANTIERE_ID),
            "personale_id": UUID(PERSONALE_ID),
            "data_da": date(2026, 8, 11),
            "data_a": None,
        },
        {
            "id": UUID(ASSEGNAZIONE_ID),
            "stato": "in_corso",
            "data_da": date(2026, 8, 11),
        },
    ]

    result = asyncio.run(
        personale_service.aggiorna_assegnazione(
            conn,
            TENANT_ID,
            ASSEGNAZIONE_ID,
            {"stato": "in_corso"},
        )
    )

    assert result["stato"] == "in_corso"
    update = conn.fetchrow.await_args_list[1]
    assert "update public.cantiere_personale" in update.args[0]
    assert update.args[-2:] == (TENANT_ID, ASSEGNAZIONE_ID)


def test_aggiorna_assegnazione_blocca_periodo_invertito():
    conn = AsyncMock()
    conn.fetchrow.return_value = {
        "cantiere_id": UUID(CANTIERE_ID),
        "personale_id": UUID(PERSONALE_ID),
        "data_da": date(2026, 8, 11),
        "data_a": None,
    }

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            personale_service.aggiorna_assegnazione(
                conn,
                TENANT_ID,
                ASSEGNAZIONE_ID,
                {"data_a": date(2026, 8, 10)},
            )
        )

    assert exc.value.status_code == 400
    assert "data finale" in exc.value.detail


def test_get_presenze_calcola_totali_giornalieri():
    conn = AsyncMock()
    conn.fetch.return_value = [
        {
            "id": UUID(PRESENZA_ID),
            "cantiere_id": UUID(CANTIERE_ID),
            "personale_tipo": "interno",
            "unita_presenti": 1,
        },
        {
            "id": UUID("50000000-0000-4000-8000-000000000002"),
            "cantiere_id": UUID(CANTIERE_ID),
            "personale_tipo": "subappaltatore",
            "unita_presenti": 4,
        },
    ]

    result = asyncio.run(
        personale_service.get_presenze(
            conn, TENANT_ID, data=date(2026, 8, 11)
        )
    )

    assert result["totale_unita"] == 5
    assert result["totale_interni"] == 1
    assert result["totale_subappaltatori"] == 4
    assert result["cantieri_attivi"] == 1
    assert "pr.tenant_id = $1::uuid" in conn.fetch.await_args.args[0]


def test_crea_presenza_valida_tenant_e_imposta_otto_ore():
    conn = AsyncMock()
    conn.fetchval.side_effect = [True, True]
    conn.fetchrow.return_value = {
        "id": UUID(PRESENZA_ID),
        "unita_presenti": 1,
        "ore_lavorate": Decimal("8.00"),
    }

    result = asyncio.run(
        personale_service.crea_presenza(
            conn,
            TENANT_ID,
            {
                "cantiere_id": CANTIERE_ID,
                "personale_id": PERSONALE_ID,
                "data": date(2026, 8, 11),
                "tipo_giornata": "intera",
            },
        )
    )

    assert result["ore_lavorate"] == 8.0
    assert conn.fetchval.await_count == 2
    insert = conn.fetchrow.await_args
    assert "insert into public.presenze_cantiere" in insert.args[0]
    assert "on conflict (id) do update" in insert.args[0]
    assert "presenze_cantiere.tenant_id = excluded.tenant_id" in insert.args[0]
    assert insert.args[1] is None
    assert insert.args[8] == 8


def test_presenza_a_ore_richiede_quantita_ore():
    conn = AsyncMock()
    conn.fetchval.side_effect = [True, True]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            personale_service.crea_presenza(
                conn,
                TENANT_ID,
                {
                    "cantiere_id": CANTIERE_ID,
                    "personale_id": PERSONALE_ID,
                    "data": date(2026, 8, 11),
                    "tipo_giornata": "ore",
                },
            )
        )

    assert exc.value.status_code == 400
    assert "ore lavorate" in exc.value.detail
