from datetime import datetime, timezone

import server


def test_serialize_lead_espone_la_data_di_arrivo_legacy():
    lead = server._serialize_lead(
        {"_id": "lead-1", "created_at": "2026-08-13T08:00:00+00:00"}
    )

    assert lead["id"] == "lead-1"
    assert lead["data_arrivo"] == "2026-08-13T08:00:00+00:00"


def test_data_meta_prevale_sul_fallback_created_at():
    lead = server._serialize_lead(
        {
            "_id": "lead-meta",
            "lead_created_at": "2026-08-13T09:30:00+00:00",
            "created_at": "2026-08-13T09:31:00+00:00",
        }
    )

    assert lead["data_arrivo"] == "2026-08-13T09:30:00+00:00"


def test_ordinamento_per_arrivo_e_indipendente_dallo_stato():
    leads = [
        {
            "id": "vecchio-spostato-ora",
            "created_at": "2026-08-12T10:00:00+00:00",
            "status_changed_at": "2026-08-13T12:00:00+00:00",
        },
        {
            "id": "nuovo",
            "created_at": "2026-08-13T11:00:00+00:00",
            "status_changed_at": "2026-08-13T11:00:00+00:00",
        },
        {
            "id": "intermedio",
            "created_at": "2026-08-13T09:00:00Z",
            "status_changed_at": "2026-08-13T09:00:00Z",
        },
    ]

    ordered = server._sort_leads_by_arrival(leads)

    assert [lead["id"] for lead in ordered] == [
        "nuovo",
        "intermedio",
        "vecchio-spostato-ora",
    ]
    assert server._lead_arrival_sort_key(ordered[0])[0] == datetime(
        2026, 8, 13, 11, tzinfo=timezone.utc
    )
