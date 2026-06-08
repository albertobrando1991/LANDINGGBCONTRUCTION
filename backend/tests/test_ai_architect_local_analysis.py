import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from bson import ObjectId
from fastapi import HTTPException

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


def test_public_ai_architect_jobs_generate_two_room_renders(monkeypatch):
    monkeypatch.setattr(svc, "AI_RENDER_MAX_ROOMS_PUBLIC", 2)
    monkeypatch.setattr(svc, "AI_RENDER_MAX_ROOMS_STAFF", 4)
    job = {
        "usage_context": "public",
        "vision_analysis": {
            "detected_rooms": [
                {"name": "Soggiorno", "confidence": 0.9},
                {"name": "Cucina", "confidence": 0.9},
                {"name": "Camera", "confidence": 0.9},
                {"name": "Bagno", "confidence": 0.9},
            ]
        },
    }

    assert svc._room_names_for_generation(job) == ["Soggiorno", "Cucina"]


def test_staff_ai_architect_jobs_keep_staff_room_render_limit(monkeypatch):
    monkeypatch.setattr(svc, "AI_RENDER_MAX_ROOMS_PUBLIC", 2)
    monkeypatch.setattr(svc, "AI_RENDER_MAX_ROOMS_STAFF", 4)
    job = {
        "usage_context": "staff",
        "vision_analysis": {
            "detected_rooms": [
                {"name": "Soggiorno", "confidence": 0.9},
                {"name": "Cucina", "confidence": 0.9},
                {"name": "Camera", "confidence": 0.9},
                {"name": "Bagno", "confidence": 0.9},
            ]
        },
    }

    assert svc._room_names_for_generation(job) == ["Soggiorno", "Cucina", "Camera", "Bagno"]


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


def test_generativa_2d_enabled_by_default_but_runtime_gated():
    # Abilitati di default per produrre una vera redistribuzione/pulizia quando esiste un provider
    # immagini; la generazione resta comunque gated a runtime da provider + confidence + review staff,
    # e in mancanza ricade sulla tavola professionale deterministica garantita.
    assert svc.AI_ALLOW_GENERATIVE_2D_LAYOUTS is True
    assert svc.AI_ALLOW_GENERATIVE_DEFINED_CLEANUP is True
    assert svc.AI_GUARANTEED_PROFESSIONAL_2D is True


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


def test_synthetic_redistributed_2d_is_not_approvable_for_render():
    job = {"plan_type_selected": "existing_state", "plan_type_detected": "existing_state"}

    synthetic = {
        "output_type": "redistributed_2d_plan",
        "image_url": "/api/ai-architect/files/outputs/fake.svg",
        "json_content": {
            "generated_with": "deterministic_safe_plan",
            "approvable_for_render": True,
        },
    }
    generative = {
        "output_type": "redistributed_2d_plan",
        "image_url": "/api/ai-architect/files/outputs/fake.png",
        "json_content": {
            "generated_with": "generative_ai_image",
            "approvable_for_render": True,
        },
    }
    source_reference = {
        "output_type": "clean_2d_plan",
        "image_url": "/api/ai-architect/files/outputs/source.png",
        "json_content": {
            "approvable_for_render": False,
            "approval_blocker": "uploaded_reference_is_not_a_redistributed_layout",
        },
    }

    assert svc._output_approvable_for_render(synthetic, job) is False
    assert svc._output_approvable_for_render(source_reference, job) is False
    assert svc._output_approvable_for_render(generative, job) is True


def test_deterministic_vector_plan_is_approvable_for_render():
    """Garanzia di risultato: la tavola 2D professionale deterministica e approvabile."""
    job = {"plan_type_selected": "existing_state", "plan_type_detected": "existing_state"}
    deterministic = {
        "output_type": "redistributed_2d_plan",
        "image_url": "/api/ai-architect/files/outputs/tavola.png",
        "json_content": {
            "generated_with": "deterministic_vector_plan",
            "approvable_for_render": True,
            "approval_required_before_client": True,
        },
    }
    assert svc.AI_GUARANTEED_PROFESSIONAL_2D is True
    assert svc._output_approvable_for_render(deterministic, job) is True


def test_defined_project_reference_can_be_approvable_when_layout_locked():
    job = {"plan_type_selected": "defined_project", "plan_type_detected": "defined_project"}
    clean_reference = {
        "output_type": "clean_2d_plan",
        "image_url": "/api/ai-architect/files/outputs/source.png",
        "json_content": {
            "approvable_for_render": True,
            "approval_basis": "uploaded_defined_project_reference",
        },
    }

    assert svc._output_approvable_for_render(clean_reference, job) is True


def test_layout_correction_notes_are_hard_prompt_constraints():
    correction = "La cabina armadio deve avere accesso dalla camera da letto, non dal bagno."
    job = {
        "plan_type_selected": "existing_state",
        "plan_type_detected": "existing_state",
        "project_variant_selected": "premium_suite",
        "layout_correction_notes": correction,
        "vision_analysis": {
            "plan_type_detected": "existing_state",
            "confidence": 0.82,
            "detected_rooms": [
                {
                    "name": "Camera da letto",
                    "approx_position": "lato destro",
                    "confidence": 0.82,
                    "evidence": "Camera con accesso verso cabina armadio.",
                    "verification_required": True,
                },
                {
                    "name": "Cabina armadio",
                    "approx_position": "adiacente alla camera",
                    "confidence": 0.78,
                    "evidence": "Vano collegato alla camera.",
                    "verification_required": True,
                },
                {
                    "name": "Bagno",
                    "approx_position": "adiacente alla cabina",
                    "confidence": 0.8,
                    "evidence": "Sanitari visibili nel vano bagno.",
                    "verification_required": True,
                },
            ],
        },
    }

    details = svc._plan_details_json(job, "redistributed")
    prompt = svc._redistributed_2d_prompt({**job, "plan_details": details})
    topdown_prompt = svc._topdown_prompt({**job, "plan_details": details}, "redistributed")

    assert details["access_rules"]["staff_correction_notes"] == correction
    assert "accessi bagno-cabina armadio inventati" in " ".join(details["render_contract"]["must_not_add"])
    assert "STAFF_LAYOUT_CORRECTIONS" in prompt
    assert correction in prompt
    assert "never replace it with an invented bathroom-side access" in prompt
    assert "never move a cabina armadio access" in topdown_prompt


def test_layout_regeneration_payload_defaults_to_one_available():
    payload = svc._layout_regeneration_payload({})

    assert payload["layout_regeneration_limit"] == 1
    assert payload["layout_regeneration_count"] == 0
    assert payload["layout_regeneration_remaining"] == 1
    assert payload["layout_regeneration_available"] is True
    assert "possono esserci errori" in payload["layout_2d_warning"]


class _FakeJobsCollection:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, flt):
        if flt.get("_id") == self.doc["_id"]:
            return dict(self.doc)
        return None

    async def find_one_and_update(self, flt, update, return_document=None):
        if flt.get("_id") != self.doc["_id"]:
            return None
        if int(self.doc.get("layout_regeneration_count") or 0) >= svc.LAYOUT_REGENERATION_LIMIT:
            return None
        for key, value in update.get("$inc", {}).items():
            self.doc[key] = int(self.doc.get(key) or 0) + value
        self.doc.update(update.get("$set", {}))
        return dict(self.doc)


class _FakeRegenerationDB:
    def __init__(self, doc):
        self.ai_architect_jobs = _FakeJobsCollection(doc)


def test_reserve_concept_2d_regeneration_is_single_use():
    job_id = ObjectId()
    db = _FakeRegenerationDB({"_id": job_id})

    reserved = asyncio.run(svc.reserve_concept_2d_regeneration(db, str(job_id)))

    assert reserved["layout_regeneration_count"] == 1
    assert reserved["layout_regeneration_available"] is False
    with pytest.raises(HTTPException) as exc:
        asyncio.run(svc.reserve_concept_2d_regeneration(db, str(job_id)))
    assert exc.value.status_code == 409
