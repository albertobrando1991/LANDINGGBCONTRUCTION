import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_architect_service as svc


def _job(**overrides):
    job = {
        "sqm": 95,
        "budget": "",
        "priorities": ["bagno aggiuntivo"],
        "plan_type_selected": "existing_state",
        "plan_type_detected": "existing_state",
        "vision_analysis": {
            "confidence": 0.72,
            "detected_rooms": [
                {"name": "Cucina", "confidence": 0.7},
                {"name": "Zona Living", "confidence": 0.65},
                {"name": "Camera da letto", "confidence": 0.6},
                {"name": "Bagno", "confidence": 0.55},
            ],
        },
        "technical_floor_plan_json": {"calibration": {"scale_declared": False}},
    }
    job.update(overrides)
    return job


def test_build_predictive_config_deduces_rooms_and_redistribution():
    cfg = svc.build_predictive_config_from_ai_job(_job())
    assert cfg["mq"] == 95.0
    assert cfg["bagni"] >= 2  # bagno rilevato + bagno aggiuntivo richiesto
    assert cfg["camere"] >= 1
    assert cfg["redistribuzione"] is True  # stato di fatto -> redistribuzione
    assert cfg["livello"] == "premium"  # nessun segnale budget luxury


def test_legacy_config_alias_still_works():
    assert svc._gb_estimate_config is svc.build_predictive_config_from_ai_job
    cfg = svc._gb_estimate_config(_job())
    assert cfg["livello"] in {"premium", "luxury"}


def test_estimate_quality_marks_ai_origin_and_reliability():
    quality = svc._estimate_quality_for_job(_job())
    assert quality["source"] == "estimated_from_ai"
    assert quality["is_quoted"] is True  # mq dichiarati
    assert quality["reliable"] is True  # confidence >= soglia
    assert quality["basis"] == "ai_floorplan_quoted"


def test_estimate_quality_unverified_on_low_confidence_without_quotes():
    job = _job(sqm=None, vision_analysis={"confidence": 0.4, "detected_rooms": []})
    quality = svc._estimate_quality_for_job(job)
    assert quality["source"] == "estimated_from_ai"
    assert quality["reliable"] is False
    assert quality["basis"] == "ai_floorplan_unverified"


def test_gb_estimate_produces_three_ordered_packages():
    estimate = svc._gb_estimate(_job())
    pacchetti = estimate["pacchetti"]
    assert set(pacchetti) >= {"essenziale", "premium", "luxury"}
    ess = pacchetti["essenziale"]["range_basso"]
    prem = pacchetti["premium"]["range_basso"]
    lux = pacchetti["luxury"]["range_basso"]
    assert ess < prem < lux  # ordinamento di fascia garantito


def test_pricing_context_includes_categories_alerts_and_recommendation():
    estimate = svc._gb_estimate(_job())
    ctx = svc._gb_pricing_context(estimate, "premium")
    assert set(ctx) == {"pacchetti", "pacchetto_consigliato", "alerts"}
    assert ctx["pacchetto_consigliato"] == "premium"
    premium = ctx["pacchetti"]["premium"]
    assert premium["n_voci"] and premium["n_voci"] > 0
    assert premium["categorie"] and len(premium["categorie"]) > 0
    assert "range_basso_eur" in premium and "costo_mq_eur" in premium


def test_pricing_context_recommended_falls_back_to_premium():
    estimate = svc._gb_estimate(_job())
    ctx = svc._gb_pricing_context(estimate, "inesistente")
    assert ctx["pacchetto_consigliato"] == "premium"


def test_pricing_context_none_without_estimate():
    assert svc._gb_pricing_context(None) is None


class _FakeColl:
    def __init__(self):
        self.set = {}

    async def update_one(self, flt, update):
        self.set.update(update.get("$set", {}))


class _FakeDB:
    def __init__(self):
        self.ai_architect_jobs = _FakeColl()
        self.ai_architect_errors = _FakeColl()


def test_persist_bridge_writes_estimate_and_metadata_onto_job():
    db = _FakeDB()
    job = _job()
    estimate = asyncio.run(
        svc.persist_gb_estimate_for_ai_job(db, "0123456789abcdef01234567", job)
    )
    assert estimate and estimate.get("pacchetti")
    # Persistito sul documento job (in-memory) e nel "db"
    for key in ("estimate", "estimate_config", "estimate_source", "estimate_confidence", "estimate_generated_at"):
        assert key in job
        assert key in db.ai_architect_jobs.set
    assert job["estimate_source"] == "estimated_from_ai"
