import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_architect_service as svc  # noqa: E402
from engines.floorplan_json_pipeline import (  # noqa: E402
    build_optimized_floor_plan_json,
    build_technical_floor_plan_json,
    technical_extraction_prompt,
)


def _job():
    return {
        "plan_type_selected": "existing_state",
        "project_variant_selected": "premium_suite",
        "style_selected": "Moderno luxury",
        "project_goal": "Ristrutturazione completa",
        "priorities": ["open space", "bagno aggiuntivo"],
        "original_filename": "planimetria.pdf",
        "file_type": "pdf",
        "vision_analysis": {
            "plan_type_detected": "existing_state",
            "confidence": 0.83,
            "measurement_notes": "Quote visibili parziali, scala da verificare.",
            "detected_rooms": [
                {
                    "name": "Soggiorno",
                    "approx_position": "sud",
                    "confidence": 0.86,
                    "evidence": "Ambiente principale con apertura esterna leggibile",
                    "estimated_area_sqm": 28,
                    "verification_required": False,
                    "bounding_box": {"x": 0.08, "y": 0.08, "width": 0.38, "height": 0.32},
                },
                {
                    "name": "Bagno",
                    "approx_position": "nord",
                    "confidence": 0.8,
                    "evidence": "Sanitari visibili",
                    "estimated_area_sqm": 6,
                    "verification_required": True,
                },
            ],
            "detected_elements": {
                "external_walls": [{"label": "perimetro", "approx_position": "esterno", "confidence": 0.86, "evidence": "linea perimetrale"}],
                "doors": [{"label": "porta", "approx_position": "centro", "confidence": 0.78, "evidence": "arco porta"}],
                "windows": [{"label": "finestra", "approx_position": "sud", "confidence": 0.81, "evidence": "apertura esterna"}],
                "bathrooms": [{"label": "bagno", "approx_position": "nord", "confidence": 0.8, "evidence": "sanitari"}],
                "kitchen_zones": [{"label": "cucina", "approx_position": "ovest", "confidence": 0.75, "evidence": "blocco cucina"}],
                "balconies": [{"label": "balcone", "approx_position": "sud", "confidence": 0.79, "evidence": "spazio esterno retinato"}],
            },
        },
    }


def test_technical_extraction_prompt_matches_image_first_contract():
    prompt = technical_extraction_prompt(_job())

    assert "JSON tecnico completo" in prompt
    assert "centimetri" in prompt
    assert "Non inventare dati" in prompt
    assert "sopralluogo" in prompt


def test_build_technical_floor_plan_json_from_vision_analysis():
    technical = build_technical_floor_plan_json(_job())

    assert technical["schema"] == "gb-technical-floor-plan-json-v1"
    assert technical["unit"] == "cm"
    assert technical["rooms"][0]["name"] == "Soggiorno"
    assert technical["walls"]
    assert technical["doors"]
    assert technical["windows"]
    assert technical["balconies"]
    assert "spessori murari certi" in technical["missing_data"]


def test_build_optimized_floor_plan_json_uses_only_selected_variant():
    technical = build_technical_floor_plan_json(_job())
    optimized = build_optimized_floor_plan_json(_job(), technical)

    assert optimized["schema"] == "gb-optimized-floor-plan-json-v1"
    assert optimized["metadata"]["selected_variant"]["id"] == "premium_suite"
    assert "Generate a professional colored 2D" in optimized["visual_prompt"]
    assert "Do not invent rooms" in optimized["visual_prompt"]
    assert optimized["walls_to_demolish"] == []


def test_plan_vision_analysis_accepts_richer_detected_elements_and_technical_json():
    analysis = svc.PlanVisionAnalysis.model_validate(
        {
            "plan_type_detected": "existing_state",
            "confidence": 0.82,
            "detected_rooms": [],
            "detected_elements": {
                "balconies": [{"label": "balcone", "approx_position": "sud", "confidence": 0.8, "evidence": "visibile"}],
                "furniture": [{"label": "armadio", "approx_position": "camera", "confidence": 0.7, "evidence": "simbolo arredo"}],
                "sanitary": [{"label": "wc", "approx_position": "bagno", "confidence": 0.78, "evidence": "simbolo sanitario"}],
            },
            "architectural_analysis": {},
            "recommended_action": "redistribute",
            "measurement_notes": "Scala da verificare.",
            "dynamic_disclaimer": "Da validare con tecnico.",
            "technical_floor_plan_json": {"schema": "gb-technical-floor-plan-json-v1", "unit": "cm"},
        }
    ).model_dump(mode="json")

    assert analysis["technical_floor_plan_json"]["unit"] == "cm"
    assert analysis["detected_elements"]["balconies"][0]["label"] == "balcone"
