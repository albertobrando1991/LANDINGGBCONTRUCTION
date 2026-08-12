import asyncio
from datetime import datetime

import google_calendar_service as calendar


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _configure(monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_CALENDAR_ID", "gbconstructionsrls@gmail.com")
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_CALENDAR_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GOOGLE_CALENDAR_REFRESH_TOKEN", "refresh-token")
    monkeypatch.setenv("GOOGLE_CALENDAR_TIMEZONE", "Europe/Rome")


def _slot(**overrides):
    value = {
        "_id": "68abc123def4567890123456",
        "date": "2026-08-20",
        "start": "09:00",
        "end": "10:00",
        "status": "free",
        "tecnico": "Giovanni",
    }
    value.update(overrides)
    return value


def test_status_non_espone_segreti(monkeypatch):
    _configure(monkeypatch)

    result = calendar.status()

    assert result == {
        "enabled": True,
        "configured": True,
        "connected": False,
        "calendar_id": "gbconstructionsrls@gmail.com",
        "timezone": "Europe/Rome",
        "missing": [],
    }
    assert "client-secret" not in str(result)
    assert "refresh-token" not in str(result)


def test_connection_status_verifica_davvero_google(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(calendar, "_verify_connection_sync", lambda: None)

    result = asyncio.run(calendar.connection_status())

    assert result["configured"] is True
    assert result["connected"] is True


def test_disabilitato_non_filtra_gli_slot(monkeypatch):
    monkeypatch.setenv("GOOGLE_CALENDAR_ENABLED", "false")
    slots = [_slot()]

    assert asyncio.run(calendar.filter_available_slots(slots)) == slots


def test_filtra_slot_sovrapposto_a_impegno_google(monkeypatch):
    _configure(monkeypatch)
    slots = [_slot(), _slot(_id="68abc123def4567890123457", start="11:00", end="12:00")]

    def fake_free_busy(_slots):
        return [
            (
                datetime.fromisoformat("2026-08-20T08:30:00+02:00"),
                datetime.fromisoformat("2026-08-20T09:30:00+02:00"),
            )
        ]

    monkeypatch.setattr(calendar, "_free_busy_sync", fake_free_busy)

    result = asyncio.run(calendar.filter_available_slots(slots))

    assert [item["start"] for item in result] == ["11:00"]


def test_require_available_blocca_sovrapposizione(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(
        calendar,
        "_free_busy_sync",
        lambda _slots: [
            (
                datetime.fromisoformat("2026-08-20T09:30:00+02:00"),
                datetime.fromisoformat("2026-08-20T10:30:00+02:00"),
            )
        ],
    )

    try:
        asyncio.run(calendar.require_available(_slot()))
    except calendar.GoogleCalendarConflict as exc:
        assert "gia occupata" in str(exc)
    else:
        raise AssertionError("Conflitto Google Calendar non rilevato")


def test_evento_libero_e_trasparente_e_privo_di_dati_cliente(monkeypatch):
    _configure(monkeypatch)

    body = calendar._event_body(_slot())

    assert body["transparency"] == "transparent"
    assert body["visibility"] == "private"
    assert "Telefono" not in body["description"]
    assert body["extendedProperties"]["private"]["source"] == "gbconstruction-crm"


def test_evento_prenotato_e_privato_con_indirizzo(monkeypatch):
    _configure(monkeypatch)
    slot = _slot(
        status="booked",
        lead_id="68abc123def4567890123000",
        booked_name="Mario Rossi",
        booked_phone="3331234567",
        booked_email="mario@example.com",
    )

    body = calendar._event_body(
        slot,
        {"nome": "Mario Rossi", "indirizzo": "Via Roma 1, Napoli"},
    )

    assert body["transparency"] == "opaque"
    assert body["visibility"] == "private"
    assert body["summary"] == "Sopralluogo - Mario Rossi"
    assert body["location"] == "Via Roma 1, Napoli"
    assert body["extendedProperties"]["private"]["lead_id"] == slot["lead_id"]


def test_upsert_crea_solo_se_patch_non_trova_evento(monkeypatch):
    _configure(monkeypatch)
    calls = []

    def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if method == "PATCH" and len(calls) == 1:
            return FakeResponse(404, {"error": {"message": "Not found"}})
        return FakeResponse(
            200,
            {
                "id": "gbcsopralluogo68abc123def4567890123456",
                "htmlLink": "https://calendar.google.com/event?eid=test",
            },
        )

    monkeypatch.setattr(calendar, "_api_request", fake_request)

    result = calendar._upsert_event_sync(_slot())

    assert [call[0] for call in calls] == ["PATCH", "POST"]
    assert "id" not in calls[0][2]["json_body"]
    assert calls[1][2]["json_body"]["id"].startswith("gbcsopralluogo")
    assert calls[1][2]["params"] == {"sendUpdates": "none"}
    assert result["event_id"].startswith("gbcsopralluogo")
    assert result["html_link"].startswith("https://calendar.google.com/")
