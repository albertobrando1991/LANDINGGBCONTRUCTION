import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.floorplan_automation import (  # noqa: E402
    build_floor_plan_automation_contract,
    normalize_project_variant,
)
from engines.furniture_library import furniture_library_payload  # noqa: E402


def _job(project_variant_selected="family", measurement_notes="Quote visibili 446 cm, 374 cm, 235 cm."):
    return {
        "project_variant_selected": project_variant_selected,
        "uploaded_file_path": "uploads/planimetria.pdf",
        "original_filename": "planimetria.pdf",
        "file_type": "pdf",
        "vision_analysis": {
            "confidence": 0.82,
            "measurement_notes": measurement_notes,
            "detected_rooms": [
                {
                    "name": "Soggiorno",
                    "approx_position": "sud",
                    "estimated_area_sqm": 30,
                    "confidence": 0.86,
                    "verification_required": False,
                },
                {
                    "name": "Camera matrimoniale",
                    "approx_position": "est",
                    "estimated_area_sqm": 16,
                    "confidence": 0.82,
                    "verification_required": True,
                },
                {
                    "name": "Bagno",
                    "approx_position": "nord",
                    "estimated_area_sqm": 6,
                    "confidence": 0.8,
                    "verification_required": True,
                },
            ],
            "detected_elements": {
                "windows": [{"label": "finestra", "approx_position": "sud", "confidence": 0.82}],
                "doors": [{"label": "porta ingresso", "approx_position": "ovest", "confidence": 0.84}],
                "bathrooms": [{"label": "bagno", "approx_position": "nord", "confidence": 0.81}],
                "kitchen_zones": [{"label": "cucina", "approx_position": "sud-ovest", "confidence": 0.78}],
                "balconies": [{"label": "balcone", "approx_position": "sud", "confidence": 0.78}],
                "structural_constraints_uncertain": [{"label": "muro spesso", "approx_position": "centro", "confidence": 0.7}],
            },
        },
    }


def test_contract_generates_only_client_selected_variant():
    contract = build_floor_plan_automation_contract(_job("family"))

    assert contract["schema"] == "gb-floor-plan-automation-contract-v1"
    assert contract["variant_generation"]["mode"] == "single_client_selected_variant"
    assert contract["variant_generation"]["generated_variant_count"] == 1
    assert contract["variant_generation"]["selected_variant"]["id"] == "family"
    assert contract["recommended_variant"] == "family"
    assert all(item["id"] != "family" for item in contract["variant_generation"]["not_generated_variants"])


def test_contract_uses_professional_parametric_furniture_library():
    contract = build_floor_plan_automation_contract(_job("premium_suite"))
    library = contract["furniture_library"]

    assert library["schema"] == "gb-parametric-furniture-library-v1"
    assert library["coverage"]["items"] >= 35
    assert contract["furniture_placement"]["library_schema"] == library["schema"]
    assert "kitchen" in library["categories"]
    assert "bathroom" in library["categories"]
    assert "balcony" in library["categories"]


def test_furniture_library_blocks_kitchen_in_bathroom_and_sanitary_in_kitchen():
    library = furniture_library_payload()

    kitchen = library["categories"]["kitchen"]["linear_kitchen_base"]
    wc = library["categories"]["bathroom"]["wc"]
    balcony_table = library["categories"]["balcony"]["bistro_table"]

    assert "bagno" in kitchen["forbidden_rooms"]
    assert "cucina" in wc["forbidden_rooms"]
    assert balcony_table["placement_prerequisite"] == "balcony_detected"
    assert library["general_clearances_cm"]["main_circulation_min"] >= 90
    assert "reject kitchen modules inside bathrooms" in " ".join(library["solver_rules"]["mep"])


def test_qualitative_plan_keeps_solver_waiting_for_metric_calibration():
    contract = build_floor_plan_automation_contract(_job(measurement_notes="Scala non leggibile, quote assenti."))

    assert contract["calibration"]["method"] == "qualitative_only"
    assert contract["pipeline_gate"]["status"] == "continue_with_warnings"
    assert contract["furniture_placement"]["metric_solver_status"] == "waiting_for_metric_calibration"
    assert contract["clash_detection"]["result"] == "pending_metric_model"


def test_unknown_variant_falls_back_to_safe_default():
    assert normalize_project_variant("invented") == "premium_suite"
