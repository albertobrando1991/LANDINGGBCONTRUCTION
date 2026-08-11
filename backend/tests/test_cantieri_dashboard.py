from __future__ import annotations

import asyncio
from types import SimpleNamespace

from bson import ObjectId

import server


class _LeadCursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, _limit):
        return self.rows


def test_build_cantiere_denormalizza_il_telefono_del_lead():
    lead_id = str(ObjectId())
    body = server.CantiereCreate(
        lead_id=lead_id,
        cliente="",
        indirizzo="",
    )
    doc = server._build_cantiere_doc(
        body,
        {
            "_id": ObjectId(lead_id),
            "nome": "Cliente Demo",
            "telefono": "+39 333 1234567",
        },
        {"name": "Admin GB"},
    )

    assert doc["cliente"] == "Cliente Demo"
    assert doc["telefono"] == "+39 333 1234567"


def test_hydrate_cantiere_telefono_risolve_i_documenti_esistenti(monkeypatch):
    lead_oid = ObjectId()
    docs = [
        {"_id": ObjectId(), "lead_id": str(lead_oid), "cliente": "Demo"},
        {"_id": ObjectId(), "lead_id": None, "cliente": "Manuale"},
    ]
    leads = SimpleNamespace(
        find=lambda *_args, **_kwargs: _LeadCursor(
            [{"_id": lead_oid, "telefono": "3331234567"}]
        )
    )
    monkeypatch.setattr(server, "db", SimpleNamespace(leads=leads))

    result = asyncio.run(server._hydrate_cantiere_telefoni(docs))

    assert result[0]["telefono"] == "3331234567"
    assert "telefono" not in result[1]
