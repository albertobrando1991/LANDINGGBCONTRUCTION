import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_architect_service as svc


def _job_with_geometry():
    return {
        "style_selected": "Moderno luxury",
        "priorities": ["open space"],
        "project_variant_selected": "premium_suite",
        "vision_analysis": {
            "confidence": 0.9,
            "detected_rooms": [
                {
                    "name": "Cucina",
                    "confidence": 0.9,
                    "approx_position": "nord-ovest",
                    "estimated_area_sqm": 12.5,
                    "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.25, "height": 0.2},
                    "evidence": "blocco cottura e lavello visibili",
                },
                {
                    "name": "Zona Living",
                    "confidence": 0.85,
                    "approx_position": "sud-ovest",
                    "estimated_area_sqm": 34.6,
                    "evidence": "divani e tavolo pranzo",
                },
            ],
            "detected_elements": {
                "doors": [
                    {"label": "porta cucina", "approx_position": "parete sud cucina", "evidence": "varco verso zona living"},
                    {"label": "porta camera", "approx_position": "disimpegno", "evidence": "porta camera da letto"},
                ],
                "windows": [
                    {"label": "finestra cucina", "approx_position": "parete nord della cucina", "evidence": "doppia anta"},
                ],
            },
        },
        "technical_floor_plan_json": {
            "rooms": [
                {"name": "Cucina", "surface_net_sqm": 12.4, "main_dimensions_cm": [320, 390], "relationships": ["Zona Living"]},
            ]
        },
        "optimized_floor_plan_json": {
            "rooms": [
                {
                    "existing_name": "Cucina",
                    "new_function": "cucina open space",
                    "furniture": [{"label": "isola cucina"}, {"label": "colonna forno"}],
                    "connections": ["Zona Living"],
                },
            ]
        },
    }


def test_room_geometry_brief_contains_room_specific_geometry():
    brief = json.loads(svc._room_geometry_brief(_job_with_geometry(), "Cucina"))

    assert brief["room_name"] == "Cucina"
    assert brief["bounding_box_normalized"] == {"x": 0.1, "y": 0.1, "width": 0.25, "height": 0.2}
    assert brief["surface_net_sqm"] == 12.4
    assert brief["main_dimensions_cm"] == [320, 390]
    assert brief["planned_function"] == "cucina open space"
    assert "isola cucina" in brief["planned_furniture"]
    # Solo le aperture attribuibili alla cucina, non quelle della camera.
    assert len(brief["doors"]) == 1
    assert len(brief["windows"]) == 1


def test_room_geometry_brief_is_valid_json_for_unknown_room():
    brief = json.loads(svc._room_geometry_brief({"vision_analysis": {}}, "Lavanderia"))
    assert brief == {"room_name": "Lavanderia"}


def test_room_prompt_includes_geometry_contract_and_plan_hierarchy():
    prompt = svc._room_prompt(_job_with_geometry(), "Cucina")

    assert "ROOM_GEOMETRY_CONTRACT" in prompt
    assert "APPROVED 2D floor plan" in prompt
    assert "single source of truth" in prompt
    assert "bounding_box_normalized" in prompt


def test_plan_details_for_prompt_always_emits_valid_json_within_budget(monkeypatch):
    job = _job_with_geometry()
    # Gonfia i blocchi pesanti ben oltre il budget.
    job["technical_floor_plan_json"]["padding"] = ["x" * 100] * 200
    job["optimized_floor_plan_json"]["padding"] = ["y" * 100] * 200
    monkeypatch.setattr(svc, "AI_PROMPT_PLAN_DETAILS_BUDGET", 6000)

    encoded = svc._plan_details_for_prompt(job, "defined")
    details = json.loads(encoded)

    assert "rooms" in details
    assert "render_contract" in details
    assert "technical_floor_plan_json" not in details
    assert "optimized_floor_plan_json" not in details


def test_fal_text_only_schema_rejects_reference_images(monkeypatch):
    monkeypatch.setattr(svc, "FAL_IMAGE_MODEL", "fal-ai/flux-pro")
    monkeypatch.setenv("FAL_KEY", "test-key")

    try:
        svc._fal_generate_image_sync("job1", "render-test", "prompt", "1536x1024", ["/api/ai-architect/files/outputs/x.png"])
    except RuntimeError as exc:
        assert "reference images" in str(exc)
    else:
        raise AssertionError("expected RuntimeError for text-only FAL schema with references")


def test_fidelity_gate_retries_with_corrective_notes(monkeypatch):
    calls = {"generate": [], "review": 0}

    async def fake_generate(job_id, name, prompt, size, references=None):
        calls["generate"].append((name, prompt))
        return f"/api/ai-architect/files/outputs/{name}.png"

    async def fake_review(subject, view, render_url, plan_url, geometry_brief=None):
        calls["review"] += 1
        if calls["review"] == 1:
            return {
                "fidelity_score": 0.3,
                "layout_violations": ["bagno dentro la cabina armadio"],
                "corrective_notes": "rimuovere i sanitari dalla cabina armadio",
            }
        return {"fidelity_score": 0.92, "layout_violations": []}

    monkeypatch.setattr(svc, "_generate_ai_image", fake_generate)
    monkeypatch.setattr(svc, "_render_fidelity_review", fake_review)
    monkeypatch.setattr(svc, "_reference_image_path", lambda url: Path("plan.png") if url else None)
    monkeypatch.setattr(svc, "AI_RENDER_FIDELITY_GATE", True)
    monkeypatch.setattr(svc, "AI_RENDER_FIDELITY_MIN_SCORE", 0.70)
    monkeypatch.setattr(svc, "AI_RENDER_FIDELITY_MAX_RETRIES", 1)

    async def noop_log(db, job_id, step, exc):
        return None

    monkeypatch.setattr(svc, "_log_non_blocking_error", noop_log)

    url, review = asyncio.run(
        svc._generate_render_with_fidelity_gate(
            None,
            "job1",
            name="render-1-cucina-ai",
            prompt="base prompt",
            size="1536x1024",
            references=["/api/ai-architect/files/outputs/plan.png"],
            plan_reference_url="/api/ai-architect/files/outputs/plan.png",
            subject="Cucina",
            view="interno",
        )
    )

    assert len(calls["generate"]) == 2
    retry_name, retry_prompt = calls["generate"][1]
    assert "fidelity-retry1" in retry_name
    assert "RENDER_FIDELITY_RETRY" in retry_prompt
    assert "bagno dentro la cabina armadio" in retry_prompt
    assert "rimuovere i sanitari dalla cabina armadio" in retry_prompt
    assert review["fidelity_score"] == 0.92
    assert url.endswith("fidelity-retry1.png")


def test_fidelity_gate_keeps_best_candidate_when_retry_is_worse(monkeypatch):
    scores = iter([0.5, 0.2])

    async def fake_generate(job_id, name, prompt, size, references=None):
        return f"/api/ai-architect/files/outputs/{name}.png"

    async def fake_review(subject, view, render_url, plan_url, geometry_brief=None):
        return {"fidelity_score": next(scores), "layout_violations": ["x"], "corrective_notes": "y"}

    monkeypatch.setattr(svc, "_generate_ai_image", fake_generate)
    monkeypatch.setattr(svc, "_render_fidelity_review", fake_review)
    monkeypatch.setattr(svc, "_reference_image_path", lambda url: Path("plan.png") if url else None)
    monkeypatch.setattr(svc, "AI_RENDER_FIDELITY_GATE", True)
    monkeypatch.setattr(svc, "AI_RENDER_FIDELITY_MIN_SCORE", 0.70)
    monkeypatch.setattr(svc, "AI_RENDER_FIDELITY_MAX_RETRIES", 1)

    url, review = asyncio.run(
        svc._generate_render_with_fidelity_gate(
            None,
            "job1",
            name="render-1-cucina-ai",
            prompt="base prompt",
            size="1536x1024",
            references=[],
            plan_reference_url="/api/ai-architect/files/outputs/plan.png",
            subject="Cucina",
            view="interno",
        )
    )

    assert review["fidelity_score"] == 0.5
    assert "fidelity-retry" not in url


def test_fidelity_gate_disabled_returns_first_image(monkeypatch):
    async def fake_generate(job_id, name, prompt, size, references=None):
        return "/api/ai-architect/files/outputs/render.png"

    monkeypatch.setattr(svc, "_generate_ai_image", fake_generate)
    monkeypatch.setattr(svc, "AI_RENDER_FIDELITY_GATE", False)

    url, review = asyncio.run(
        svc._generate_render_with_fidelity_gate(
            None,
            "job1",
            name="render-1-cucina-ai",
            prompt="p",
            size="1536x1024",
            references=[],
            plan_reference_url="/api/ai-architect/files/outputs/plan.png",
            subject="Cucina",
            view="interno",
        )
    )

    assert url == "/api/ai-architect/files/outputs/render.png"
    assert review is None
