from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from document_id import ObjectId
import server


def test_delete_cantiere_scollega_il_lead_associato(monkeypatch):
    cantiere_id = str(ObjectId())
    lead_id = str(ObjectId())
    cantiere_oid = server.object_id_or_400(cantiere_id)
    lead_oid = server.object_id_or_400(lead_id)
    cantieri = SimpleNamespace(
        find_one_and_delete=AsyncMock(
            return_value={
                "_id": cantiere_oid,
                "lead_id": lead_id,
                "cliente": "Cliente Demo",
            }
        )
    )
    leads = SimpleNamespace(update_one=AsyncMock())
    monkeypatch.setattr(server, "db", SimpleNamespace(cantieri=cantieri, leads=leads))

    result = asyncio.run(
        server.delete_cantiere(
            cantiere_id,
            {"role": "admin", "name": "Admin GB"},
        )
    )

    assert result == {"ok": True, "deleted": cantiere_id}
    cantieri.find_one_and_delete.assert_awaited_once_with({"_id": cantiere_oid})
    lead_filter, lead_update = leads.update_one.await_args.args
    assert lead_filter == {
        "_id": lead_oid,
        "cantiere_id": cantiere_id,
    }
    assert lead_update["$unset"] == {"cantiere_id": ""}
    assert "Cantiere eliminato da Admin GB" in (
        lead_update["$push"]["timeline"]["$each"][0]["testo"]
    )


def test_delete_cantiere_inesistente_restituisce_404(monkeypatch):
    cantieri = SimpleNamespace(
        find_one_and_delete=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        server,
        "db",
        SimpleNamespace(cantieri=cantieri, leads=SimpleNamespace()),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            server.delete_cantiere(
                str(ObjectId()),
                {"role": "admin", "name": "Admin GB"},
            )
        )

    assert exc.value.status_code == 404
    cantieri.find_one_and_delete.assert_awaited_once()
