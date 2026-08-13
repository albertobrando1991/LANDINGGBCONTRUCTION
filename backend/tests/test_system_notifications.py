from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from document_store import ReturnDocument
import system_notifications

TENANT_ID = "a0000000-0000-4000-8000-000000000001"


class _Cursor:
    def __init__(self, documents, query):
        self.documents = documents
        self.query = query

    async def to_list(self, length=None):
        rows = [
            dict(item)
            for item in self.documents
            if all(item.get(key) == value for key, value in self.query.items())
        ]
        return rows if length is None else rows[:length]


class _Collection:
    def __init__(self, documents=None):
        self.documents = [dict(item) for item in (documents or [])]

    def find(self, query=None):
        return _Cursor(self.documents, query or {})

    async def find_one(self, query):
        return next(
            (
                dict(item)
                for item in self.documents
                if item.get("_id") == query.get("_id")
            ),
            None,
        )

    async def find_one_and_update(
        self, query, update, *, upsert=False, return_document=ReturnDocument.BEFORE
    ):
        existing = next(
            (item for item in self.documents if item.get("_id") == query.get("_id")),
            None,
        )
        before = dict(existing) if existing else None
        if existing is None:
            if not upsert:
                return None
            existing = {"_id": query["_id"]}
            self.documents.append(existing)
        for key, value in update.get("$set", {}).items():
            existing[key] = value
        if before is None:
            for key, value in update.get("$setOnInsert", {}).items():
                existing[key] = value
        for key, value in update.get("$addToSet", {}).items():
            incoming = value.get("$each", []) if isinstance(value, dict) else [value]
            target = existing.setdefault(key, [])
            target.extend(item for item in incoming if item not in target)
        return dict(existing) if return_document == ReturnDocument.AFTER else before

    async def update_one(self, query, update):
        existing = next(
            item for item in self.documents if item.get("_id") == query["_id"]
        )
        existing.update(update.get("$set", {}))


class _Database:
    def __init__(self, *, leads, slots, sites):
        self.leads = _Collection(leads)
        self.sopralluogo_slots = _Collection(slots)
        self.cantieri = _Collection(sites)
        self.system_notification_states = _Collection()


class _Connection:
    def __init__(self, quote_rows, payment_rows):
        self.quote_rows = quote_rows
        self.payment_rows = payment_rows
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        if "from public.preventivi" in sql:
            return self.quote_rows
        if "from public.incassi" in sql:
            return self.payment_rows
        raise AssertionError(f"Query inattesa: {sql}")


def test_notifiche_reali_collegate_e_stato_letto_persistente():
    now = datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc)
    db = _Database(
        leads=[
            {
                "_id": "64b4e3f04bd0c2c5a2a10001",
                "status": "nuovo",
                "nome": "Lead Meta",
                "citta": "Napoli",
                "origine": "meta_ads",
                "meta": {"created_time": (now - timedelta(minutes=35)).isoformat()},
            },
            {
                "_id": "64b4e3f04bd0c2c5a2a10002",
                "status": "nuovo",
                "nome": "Lead Landing",
                "created_at": (now - timedelta(minutes=5)).isoformat(),
            },
        ],
        slots=[
            {
                "_id": "64b4e3f04bd0c2c5a2a10003",
                "status": "booked",
                "date": "2026-08-13",
                "start": "15:30",
                "booked_name": "Cliente Sopralluogo",
                "created_at": (now - timedelta(days=1)).isoformat(),
            }
        ],
        sites=[
            {
                "_id": "64b4e3f04bd0c2c5a2a10004",
                "stato": "attivo",
                "cliente": "Cantiere Verdi",
                "criticita": "Materiale non consegnato",
                "updated_at": (now - timedelta(hours=2)).isoformat(),
            }
        ],
    )
    conn = _Connection(
        quote_rows=[
            {
                "id": UUID("20000000-0000-4000-8000-000000000001"),
                "computo_id": UUID("30000000-0000-4000-8000-000000000001"),
                "numero": "PREV-2026-001",
                "cliente": "Cliente Preventivo",
                "inviato_at": now - timedelta(days=8),
                "created_at": now - timedelta(days=9),
            }
        ],
        payment_rows=[
            {
                "id": UUID("40000000-0000-4000-8000-000000000001"),
                "cantiere_id": UUID("50000000-0000-4000-8000-000000000001"),
                "descrizione": "Rata 1",
                "importo": Decimal("10000"),
                "pagato": Decimal("2500"),
                "data_prevista": date(2026, 8, 11),
                "stato": "parziale",
                "cliente": "Cliente Pagamento",
            }
        ],
    )
    user = {"id": "user-1", "role": "admin", "email": "admin@example.com"}

    first = asyncio.run(
        system_notifications.collect_notifications(db, conn, TENANT_ID, user, now=now)
    )

    assert first["unread_count"] == 6
    assert {item["kind"] for item in first["items"]} == {
        "lead_sla",
        "new_lead",
        "appointment",
        "site_criticality",
        "quote_waiting",
        "payment_due",
    }
    assert all(item["href"].startswith("/dashboard/") for item in first["items"])
    assert first["items"][0]["severity"] == "urgent"

    read_id = first["items"][0]["id"]
    assert (
        asyncio.run(system_notifications.mark_notifications_read(db, user, [read_id]))
        == 1
    )
    second = asyncio.run(
        system_notifications.collect_notifications(db, conn, TENANT_ID, user, now=now)
    )
    assert second["unread_count"] == 5
    assert (
        next(item for item in second["items"] if item["id"] == read_id)["read"] is True
    )


def test_ruoli_non_economici_non_ricevono_incassi():
    now = datetime(2026, 8, 13, 10, 0, tzinfo=timezone.utc)
    db = _Database(leads=[], slots=[], sites=[])
    conn = _Connection(quote_rows=[], payment_rows=[{"id": "mai-letto"}])

    payload = asyncio.run(
        system_notifications.collect_notifications(
            db,
            conn,
            TENANT_ID,
            {"id": "staff-1", "role": "staff"},
            now=now,
        )
    )

    assert payload["items"] == []
    assert len(conn.calls) == 1


def test_id_non_valido_non_viene_salvato():
    db = _Database(leads=[], slots=[], sites=[])
    marked = asyncio.run(
        system_notifications.mark_notifications_read(
            db,
            {"id": "user-1"},
            ["../../qualcosa", "non-valido"],
        )
    )
    assert marked == 0
    assert db.system_notification_states.documents == []
