from datetime import datetime, timezone

import pytest

from report_service import build_sales_report


NOW = datetime(2026, 8, 11, 12, tzinfo=timezone.utc)


def lead(status, created_at="2026-08-01T10:00:00+00:00", **overrides):
    payload = {
        "nome": "Cliente demo",
        "citta": "Napoli",
        "tipo_immobile": "appartamento",
        "livello": "premium",
        "status": status,
        "range_basso": 80_000,
        "range_alto": 100_000,
        "created_at": created_at,
        "status_changed_at": created_at,
    }
    payload.update(overrides)
    return payload


def test_funnel_is_cumulative_after_a_lead_advances():
    report = build_sales_report(
        [
            lead("nuovo"),
            lead("qualificato"),
            lead("sopralluogo_fatto"),
            lead("preventivo_inviato"),
            lead("in_trattativa"),
            lead("chiuso_perso"),
            lead("chiuso_vinto"),
        ],
        now=NOW,
    )

    assert report["kpi"] == {
        "lead_ricevuti": 7,
        "lead_qualificati": 6,
        "sopralluoghi": 5,
        "preventivi": 4,
        "chiusi_vinti": 1,
        "chiusi_persi": 1,
        "conversione": 14.3,
        "valore_pipeline": 450_000,
        "valore_chiuso": 90_000,
    }
    assert [item["value"] for item in report["funnel"]] == [7, 6, 5, 4, 1]


def test_period_filter_excludes_old_and_undated_leads_and_fills_timeline_gaps():
    report = build_sales_report(
        [
            lead("nuovo", "2026-08-10T09:00:00Z"),
            lead("qualificato", "2026-07-20T09:00:00+00:00"),
            lead("chiuso_vinto", "2026-06-01T09:00:00+00:00"),
            lead("nuovo", "data-non-valida"),
        ],
        period="30d",
        now=NOW,
    )

    assert report["kpi"]["lead_ricevuti"] == 2
    assert report["meta"]["period_label"] == "Ultimi 30 giorni"
    assert report["meta"]["timeline_granularity"] == "day"
    assert report["timeline"][0]["data"] == "2026-07-12"
    assert report["timeline"][-1]["data"] == "2026-08-11"
    assert sum(point["lead"] for point in report["timeline"]) == 2


def test_report_normalizes_dimensions_and_uses_midpoint_values_safely():
    report = build_sales_report(
        [
            lead("chiuso_perso", citta="  NAPOLI  ", nome=None),
            lead("nuovo", citta="napoli", range_basso="non valido", range_alto=50_000),
            lead(
                "nuovo",
                citta="",
                tipo_immobile="-",
                livello="premium",
                range_basso=None,
                range_alto=float("nan"),
            ),
        ],
        now=NOW,
    )

    assert report["geografia"] == [
        {"citta": "Napoli", "lead": 2, "percentuale": 100.0},
    ]
    assert report["copertura_geografica"] == {
        "segnalati": 2,
        "non_segnalati": 1,
        "copertura_percentuale": 66.7,
    }
    assert report["distribuzione"] == [
        {"name": "Premium", "value": 2},
        {"name": "Da definire", "value": 1},
    ]
    assert report["kpi"]["valore_pipeline"] == 50_000
    assert report["persi"][0]["nome"] == "Lead senza nome"
    assert report["persi"][0]["range"] == 90_000


def test_geography_excludes_missing_placeholders_and_generic_areas():
    report = build_sales_report(
        [
            lead("nuovo", citta="Casalnuovo di Napoli"),
            lead("nuovo", citta=""),
            lead("nuovo", citta=None),
            lead("nuovo", citta="Altro"),
            lead("nuovo", citta="Non specificata"),
            lead("nuovo", citta="Napoli e provincia"),
            lead("nuovo", citta="Provincia di Caserta"),
            lead("nuovo", citta="Campania"),
        ],
        now=NOW,
    )

    assert report["geografia"] == [
        {
            "citta": "Casalnuovo di Napoli",
            "lead": 1,
            "percentuale": 100.0,
        }
    ]
    assert report["copertura_geografica"] == {
        "segnalati": 1,
        "non_segnalati": 7,
        "copertura_percentuale": 12.5,
    }


def test_report_does_not_truncate_histories_over_one_thousand_leads():
    report = build_sales_report(
        [lead("nuovo", nome=f"Lead {index}") for index in range(1_005)],
        now=NOW,
    )

    assert report["kpi"]["lead_ricevuti"] == 1_005


def test_invalid_period_is_rejected():
    with pytest.raises(ValueError, match="Periodo report non supportato"):
        build_sales_report([], period="7d", now=NOW)
