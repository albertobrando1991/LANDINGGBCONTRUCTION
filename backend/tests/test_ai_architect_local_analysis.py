import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_architect_service as svc


def test_fallback_analysis_returns_professional_safe_delivery():
    analysis = svc._fallback_analysis_json(
        {
            "plan_type_selected": "auto",
            "project_goal": "Ristrutturazione completa",
            "priorities": ["open space", "bagno aggiuntivo"],
            "sqm": 95,
            "uploaded_file_path": "missing.pdf",
            "original_filename": "planimetria.pdf",
        },
        "provider unavailable",
    )

    assert analysis["model_provider"] == "professional-safe-mode"
    assert analysis["is_fallback"] is False
    assert analysis["confidence"] >= svc.VISION_MIN_ACCEPTABLE_CONFIDENCE
    assert len(analysis["detected_rooms"]) >= svc.VISION_MIN_ROOMS
    assert svc._professional_analysis_issues(analysis) == []


def test_local_vision_does_not_pass_professional_gate_when_advanced_vision_is_required():
    analysis = svc._local_vision_analysis_json(
        {
            "plan_type_selected": "auto",
            "project_goal": "Ristrutturazione completa",
            "priorities": ["open space", "bagno aggiuntivo"],
            "sqm": 95,
            "uploaded_file_path": "missing.pdf",
            "original_filename": "planimetria.pdf",
        },
        "provider unavailable",
    )

    assert analysis["model_provider"] == "local-vision"
    assert analysis["is_fallback"] is False
    assert "analisi non prodotta da provider AI vision avanzato" in svc._professional_analysis_issues(analysis)


def test_local_vision_preview_is_structured_when_explicitly_used():
    analysis = svc._local_vision_analysis_json(
        {
            "plan_type_selected": "auto",
            "project_goal": "Ristrutturazione completa",
            "priorities": ["open space", "bagno aggiuntivo"],
            "sqm": 95,
            "uploaded_file_path": "missing.pdf",
            "original_filename": "planimetria.pdf",
        },
        "provider unavailable",
    )

    assert analysis["model_provider"] == "local-vision"
    assert analysis["is_fallback"] is False
    assert len(analysis["detected_rooms"]) >= 5
    assert all(room.get("bounding_box") for room in analysis["detected_rooms"])


def test_anthropic_provider_passes_professional_gate():
    analysis = svc._safe_mode_analysis_json(
        {
            "plan_type_selected": "auto",
            "project_goal": "Ristrutturazione completa",
            "priorities": ["open space"],
            "sqm": 80,
            "uploaded_file_path": "missing.pdf",
            "original_filename": "planimetria.pdf",
        },
        "test",
    )
    analysis["model_provider"] = "anthropic"
    analysis["model_name"] = "claude-test"

    assert svc._professional_analysis_issues(analysis) == []


def test_default_ai_routing_specializes_models_by_task():
    assert svc.AI_VISION_PROVIDER_CHAIN[:2] == ["claude_direct", "openrouter"]
    assert "openai_direct" not in svc.AI_VISION_PROVIDER_CHAIN
    assert svc.AI_TEXT_PROVIDER_CHAIN[0] == "claude_direct"


def test_client_text_cleanup_removes_markdown_artifacts():
    text = svc._clean_client_text("## Titolo\n\n**Sintesi:** valore\n- punto uno")

    assert "##" not in text
    assert "**" not in text
    assert "Titolo" in text
    assert "Sintesi:" in text


def test_fal_gpt_image_2_schema_helpers():
    assert svc._fal_image_size("1536x1024") == "landscape_4_3"
    assert svc._fal_image_size("1024x1536") == "portrait_4_3"
    assert svc._fal_image_size("1024x1024") == "square_hd"


def test_plan_details_json_contains_render_contract():
    analysis = svc._safe_mode_analysis_json(
        {
            "plan_type_selected": "defined_project",
            "project_goal": "Ristrutturazione completa",
            "priorities": ["open space"],
            "sqm": 80,
            "uploaded_file_path": "missing.pdf",
            "original_filename": "planimetria.pdf",
        },
        "test",
    )
    details = svc._plan_details_json({"vision_analysis": analysis, "priorities": ["open space"]}, "defined")

    assert details["schema"] == "gb-ai-architect-plan-details-v1"
    assert details["rooms"]
    assert "stanze nuove non presenti nel JSON" in details["render_contract"]["must_not_add"]


def test_generativa_2d_disabled_by_default_for_professional_safety():
    assert svc.AI_ALLOW_GENERATIVE_2D_LAYOUTS is False
    assert svc.AI_ALLOW_GENERATIVE_DEFINED_CLEANUP is False


def test_redistributed_safe_plan_does_not_stretch_detected_room():
    job = {
        "style_selected": "Moderno luxury",
        "vision_analysis": {
            "detected_rooms": [
                {
                    "name": "Zona living",
                    "confidence": 0.9,
                    "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2},
                }
            ]
        },
    }

    clean = svc._room_shapes_from_analysis(job, "clean")
    redistributed = svc._room_shapes_from_analysis(job, "redistributed")

    assert redistributed[0][3] == clean[0][3]


def test_redistributed_2d_prompt_rejects_known_hallucinations():
    analysis = svc._safe_mode_analysis_json(
        {
            "plan_type_selected": "existing_state",
            "project_goal": "Ristrutturazione completa",
            "priorities": ["open space"],
            "sqm": 80,
            "uploaded_file_path": "missing.pdf",
            "original_filename": "planimetria.pdf",
        },
        "test",
    )
    job = {
        "plan_type_selected": "existing_state",
        "plan_type_detected": "existing_state",
        "vision_analysis": analysis,
        "priorities": ["open space"],
        "style_selected": "Moderno luxury",
        "project_goal": "Ristrutturazione completa",
    }

    prompt = svc._redistributed_2d_prompt(job)

    assert "no balconies/terraces unless clearly visible" in prompt
    assert "no kitchen cabinets" in prompt
    assert "do not label any wall as load-bearing" in prompt


def test_defined_project_contract_locks_uploaded_layout():
    analysis = svc._safe_mode_analysis_json(
        {
            "plan_type_selected": "defined_project",
            "project_goal": "Ristrutturazione completa",
            "priorities": ["render professionali"],
            "sqm": 80,
            "uploaded_file_path": "missing.pdf",
            "original_filename": "stato-di-progetto.pdf",
        },
        "test",
    )
    job = {
        "plan_type_selected": "defined_project",
        "plan_type_detected": "defined_project",
        "vision_analysis": analysis,
        "priorities": ["render professionali"],
        "style_selected": "Moderno luxury",
        "project_goal": "Ristrutturazione completa",
    }

    details = svc._plan_details_json(job, "defined")
    proposal = svc._proposal_json("defined", job)
    topdown_prompt = svc._topdown_prompt(job, "defined")

    assert details["layout_lock"] == "preserve_uploaded_plan_exactly"
    assert proposal["layout_locked"] is True
    assert any(
        "planimetria allegata mantenuta identica" in item
        for item in details["render_contract"]["must_preserve"]
    )
    assert "spostamento creativo di muri, aperture, bagni, cucina o accessi" in details["render_contract"]["must_not_add"]
    assert "preserve it exactly" in topdown_prompt
