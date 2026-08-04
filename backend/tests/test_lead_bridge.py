import asyncio

import pytest
from fastapi import HTTPException

from lead_bridge import resolve_lead_id

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
