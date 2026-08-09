import asyncio

import pytest
from fastapi import HTTPException

from lead_bridge import (
    resolve_lead_id,
    sync_existing_postgres_lead,
    sync_legacy_lead,
)

TENANT_ID = "a0000000-0000-4000-8000-000000000001"


def test_id_lead_malformato_rifiutato_prima_del_database():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(resolve_lead_id(None, None, TENANT_ID, "non-un-id"))
    assert exc.value.status_code == 400


def test_uuid_deve_appartenere_al_tenant():
    class Conn:
        async def fetchval(self, *_args):
            return None

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            resolve_lead_id(
                Conn(),
                None,
                TENANT_ID,
                "10000000-0000-4000-8000-000000000001",
            )
        )
    assert exc.value.status_code == 404


def test_object_id_mongo_viene_sincronizzato_in_uuid_postgres():
    mongo_id = "64b64c8f2f9b2d7a1c000001"
    pg_id = "10000000-0000-4000-8000-000000000001"

    class Conn:
        async def fetchval(self, *_args):
            return None

        async def fetchrow(self, sql, *args):
            assert "on conflict (legacy_mongo_id)" in sql.lower()
            assert args[0] == TENANT_ID
            assert args[-1] == mongo_id
            return {"id": pg_id}

    class Leads:
        async def find_one(self, query):
            assert str(query["_id"]) == mongo_id
            return {
                "nome": "Cliente legacy",
                "email": "legacy@example.test",
                "telefono": "+39000000000",
                "status": "qualificato",
                "config": {"mq": 80},
            }

    class Mongo:
        leads = Leads()

    result = asyncio.run(resolve_lead_id(Conn(), Mongo(), TENANT_ID, mongo_id))
    assert result == pg_id


def test_pipeline_aggiorna_il_mirror_postgres_esistente():
    mongo_id = "64b64c8f2f9b2d7a1c000001"

    class Conn:
        async def execute(self, sql, *args):
            assert "where legacy_mongo_id" in sql.lower()
            assert args[0] == "preventivo_preparazione"
            assert args[-2:] == (mongo_id, TENANT_ID)
            return "UPDATE 1"

    result = asyncio.run(
        sync_existing_postgres_lead(
            Conn(),
            TENANT_ID,
            {
                "_id": mongo_id,
                "status": "preventivo_preparazione",
                "timeline": [],
            },
        )
    )
    assert result is True


def test_preventivo_aggiorna_il_lead_legacy_usato_da_inbox_e_pipeline():
    mongo_id = "64b64c8f2f9b2d7a1c000001"
    pg_id = "10000000-0000-4000-8000-000000000001"

    class Conn:
        async def fetchrow(self, sql, *args):
            assert "from public.leads" in sql.lower()
            assert args == (pg_id, TENANT_ID)
            return {
                "legacy_mongo_id": mongo_id,
                "status": "preventivo_inviato",
                "prossima_azione": "Follow-up",
                "timeline": [{"tipo": "preventivo"}],
            }

    class Result:
        matched_count = 1

    class Leads:
        async def update_one(self, query, operation):
            assert str(query["_id"]) == mongo_id
            assert operation["$set"]["status"] == "preventivo_inviato"
            return Result()

    class Mongo:
        leads = Leads()

    result = asyncio.run(sync_legacy_lead(Conn(), Mongo(), TENANT_ID, pg_id))
    assert result is True
