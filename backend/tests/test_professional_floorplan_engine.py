import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.professional_floorplan import (  # noqa: E402
    build_professional_floorplan_package,
    professional_2d_prompt_addendum,
    professional_advice_text,
    render_prompt_addendum,
)


def _job(plan_type_selected="existing_state", recommended_action="redistribute"):
    return {
        "plan_type_selected": plan_type_selected,
        "style_selected": "Moderno luxury",
        "project_goal": "Nuova distribuzione degli spazi",
        "priorities": ["piu luce", "open space", "bagno aggiuntivo"],
        "sqm": 95,
        "vision_analysis": {
            "plan_type_detected": "defined_project" if plan_type_selected == "defined_project" else "existing_state",
            "confidence": 0.82,
            "recommended_action": recommended_action,
            "measurement_notes": "Scala grafica non leggibile con certezza.",
            "detected_rooms": [
                {
                    "name": "soggiorno",
                    "approx_position": "sud",
                    "confidence": 0.86,
                    "evidence": "ambiente principale con apertura esterna visibile",
                    "estimated_area_sqm": 28,
                    "verification_required": False,
                    "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.38, "height": 0.28},
                },
                {
                    "name": "corridoio",
                    "approx_position": "centro",
                    "confidence": 0.74,
                    "evidence": "fascia di distribuzione centrale",
                    "verification_required": True,
                },
                {
                    "name": "bagno",
                    "approx_position": "nord",
                    "confidence": 0.8,
                    "evidence": "sanitari riconoscibili",
                    "verification_required": True,
                },
            ],
            "detected_elements": {
                "windows": [{"label": "finestra", "approx_position": "sud", "confidence": 0.8, "evidence": "apertura esterna"}],
                "bathrooms": [{"label": "bagno", "approx_position": "nord", "confidence": 0.8, "evidence": "sanitari"}],
                "kitchen_zones": [{"label": "cucina", "approx_position": "est", "confidence": 0.7, "evidence": "blocco cucina"}],
                "corridors": [{"label": "corridoio", "approx_position": "centro", "confidence": 0.72, "evidence": "passaggio"}],
                "structural_constraints_uncertain": [{"label": "muro spesso", "approx_position": "ovest", "confidence": 0.7, "evidence": "spessore maggiore"}],
            },
        },
    }


def test_existing_state_builds_optimized_professional_package():
    package = build_professional_floorplan_package(_job())

    assert package["schema"] == "gb-professional-floorplan-v1"
    assert package["mode"] == "optimized_existing_state"
    assert package["floorplan_2d"]["approval_checklist"]
    assert package["optimization_strategy"]
    assert any(item["category"] == "plumbing" for item in package["technical_findings"])
    assert "stanze" in " ".join(package["render_contract"]["must_not_add"])


def test_defined_project_locks_cleanup_mode():
    package = build_professional_floorplan_package(
        _job(plan_type_selected="defined_project", recommended_action="keep_layout")
    )

    assert package["mode"] == "clean_defined_project"
    assert package["render_contract"]["reference_type"] == "clean_2d_plan"
    assert "Nessuna redistribuzione automatica" in package["floorplan_2d"]["change_summary"]


def test_prompt_addenda_are_conservative_and_nonempty():
    package = build_professional_floorplan_package(_job())

    assert "PROFESSIONAL_2D_BRIEF" in professional_2d_prompt_addendum(package)
    assert "Must not add" in render_prompt_addendum(package)
    advice = professional_advice_text(
        package,
        style="Moderno luxury",
        goal="Nuova distribuzione degli spazi",
        priorities="piu luce, open space",
    )
    assert "da validare con tecnico abilitato" in advice.lower()
