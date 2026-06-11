import asyncio
import sys
from pathlib import Path

from bson import ObjectId

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_architect_service as svc
import ai_credit_service


JOB_ID = "5f1d7f2e4b9c2a0011223344"


def _job():
    return {
        "_id": ObjectId(JOB_ID),
        "status": "completed",
        "style_selected": "Moderno luxury",
        "usage_context": "staff",
        "plan_type_selected": "defined_project",
        "vision_analysis": {
            "confidence": 0.9,
            "detected_rooms": [
                {
                    "name": "Cucina",
                    "confidence": 0.9,
                    "estimated_area_sqm": 12.5,
                    "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.25, "height": 0.2},
                    "evidence": "blocco cottura",
                }
            ],
        },
    }


class FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_args, **_kwargs):
        return self

    async def to_list(self, _limit):
        return list(self._docs)


def _match_value(actual, expected):
    if isinstance(expected, dict) and any(k.startswith("$") for k in expected):
        for op, operand in expected.items():
            if op == "$ne" and actual == operand:
                return False
            if op == "$nin" and actual in operand:
                return False
            if op == "$in" and actual not in operand:
                return False
            if op == "$exists" and (actual is not None) != bool(operand):
                return False
        return True
    return actual == expected


def _match_doc(doc, query):
    return all(_match_value(doc.get(k), v) for k, v in query.items())


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.inserted = []
        self.updates = []

    async def find_one(self, query):
        for doc in self.docs:
            if _match_doc(doc, query):
                return doc
        return None

    def find(self, query):
        matched = [doc for doc in self.docs if _match_doc(doc, query)]
        return FakeCursor(matched)

    async def insert_one(self, doc):
        doc = {"_id": ObjectId(), **doc}
        self.docs.append(doc)
        self.inserted.append(doc)
        return doc

    async def update_one(self, query, update):
        self.updates.append((query, update))
        return None


class FakeDB:
    def __init__(self, job, outputs, memories=None):
        self.ai_architect_jobs = FakeCollection([job])
        self.ai_architect_outputs = FakeCollection(outputs)
        self.ai_architect_errors = FakeCollection()
        self.ai_architect_refinement_memories = FakeCollection(memories or [])


def test_normalize_region_clamps_and_rejects_tiny():
    region = svc._normalize_region({"x": -0.2, "y": 0.5, "width": 0.9, "height": 0.3})
    assert region["x"] == 0.0
    # width viene clampata cosi da non sforare il bordo destro.
    assert region["x"] + region["width"] <= 1.0
    assert svc._normalize_region({"x": 0.4, "y": 0.4, "width": 0.01, "height": 0.01}) is None
    assert svc._normalize_region(None) is None
    assert svc._normalize_region({"x": "nan"}) is None


def test_refine_prompt_includes_instruction_and_region():
    output = {"output_type": "topdown_3d_plan", "image_url": "/x.png"}
    region = {"x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
    prompt = svc._refine_prompt(_job(), output, "togli la finestra dal bagno", region)
    assert "togli la finestra dal bagno" in prompt
    assert "ONLY inside the selected area" in prompt
    assert "PLAN_DETAILS_JSON" in prompt


def test_refine_prompt_room_includes_geometry_contract():
    output = {"output_type": "room_render", "room_name": "Cucina", "image_url": "/x.png"}
    prompt = svc._refine_prompt(_job(), output, "isola al centro", None)
    assert "ROOM_GEOMETRY_CONTRACT" in prompt
    assert "isola al centro" in prompt
    # Senza area selezionata non deve comparire la clausola di edit localizzato.
    assert "ONLY inside the selected area" not in prompt


def test_build_edit_mask_png_creates_transparent_box(tmp_path, monkeypatch):
    from PIL import Image

    monkeypatch.setattr(svc, "OUTPUT_DIR", tmp_path)
    base = tmp_path / "base.png"
    Image.new("RGB", (200, 100), (255, 255, 255)).save(base)

    region = {"x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5}
    mask_path = svc._build_edit_mask_png(base, region, JOB_ID, "refine-test")
    assert mask_path is not None and mask_path.exists()

    with Image.open(mask_path) as mask:
        assert mask.size == (200, 100)
        alpha = mask.convert("RGBA").getchannel("A")
        # Centro selezionato = trasparente (zona da rigenerare); angolo = opaco.
        assert alpha.getpixel((100, 50)) == 0
        assert alpha.getpixel((2, 2)) == 255


def test_refine_output_adds_versioned_output_and_charges(monkeypatch):
    output_id = ObjectId()
    output = {
        "_id": output_id,
        "job_id": JOB_ID,
        "output_type": "room_render",
        "room_name": "Cucina",
        "image_url": "/api/ai-architect/files/outputs/cucina.png",
    }
    db = FakeDB(_job(), [output])

    async def fake_generate(*_args, **_kwargs):
        return "/api/ai-architect/files/outputs/cucina-refined.png", {"fidelity_score": 0.9}

    charges = []

    async def fake_charge(_db, **kwargs):
        charges.append(kwargs)
        return {"ok": True}

    async def fake_classify(*_args, **_kwargs):
        return svc._normalize_refinement_classification(
            {
                "learnable": True,
                "category": "distribution_error",
                "subcategory": "kitchen_placement",
                "severity": "high",
                "affected_elements": ["kitchen"],
                "extracted_rule": "Keep the kitchen where the approved plan places it.",
                "confidence": 0.9,
            },
            "x",
        )

    monkeypatch.setattr(svc, "_refine_generate", fake_generate)
    monkeypatch.setattr(svc, "_classify_refinement_signal", fake_classify)
    monkeypatch.setattr(svc, "_reference_image_path", lambda url: Path("x.png") if url else None)
    monkeypatch.setattr(svc, "_approved_plan_reference_url", lambda *_a, **_k: "/plan.png")
    monkeypatch.setattr(svc, "_build_edit_mask_png", lambda *_a, **_k: None)
    monkeypatch.setattr(ai_credit_service, "charge_credits", fake_charge)

    asyncio.run(
        svc.refine_output(
            db,
            JOB_ID,
            str(output_id),
            instruction="la cucina non deve stare li",
            region=None,
            reviewer="Tester",
            previous_status="completed",
        )
    )

    new_outputs = [d for d in db.ai_architect_outputs.inserted if d["output_type"] == "room_render"]
    assert len(new_outputs) == 1
    refinement = new_outputs[0]["json_content"]["refinement"]
    assert refinement["instruction"] == "la cucina non deve stare li"
    assert refinement["revision"] == 1
    assert refinement["parent_output_id"] == str(output_id)
    assert new_outputs[0]["image_url"].endswith("cucina-refined.png")

    # Errore strutturale -> memoria forte persistita con regola riusabile.
    memories = db.ai_architect_refinement_memories.inserted
    assert len(memories) == 1
    assert memories[0]["strength"] == "strong"
    assert memories[0]["category"] == "distribution_error"
    assert memories[0]["extracted_rule"]
    assert memories[0]["output_id_before"] == str(output_id)

    assert len(charges) == 1
    assert charges[0]["action_key"] == "ai_architect_regen_room_render"

    # Lo stato del job viene ripristinato e il flag refine azzerato.
    last_update = db.ai_architect_jobs.updates[-1][1]["$set"]
    assert last_update["status"] == "completed"
    assert last_update["refine_in_progress"] is False


def test_refine_output_rejects_non_refinable_type(monkeypatch):
    output_id = ObjectId()
    output = {
        "_id": output_id,
        "job_id": JOB_ID,
        "output_type": "analysis",
        "image_url": "/x.png",
    }
    db = FakeDB(_job(), [output])

    called = {"generate": False}

    async def fake_generate(*_args, **_kwargs):
        called["generate"] = True
        return "/x.png", None

    monkeypatch.setattr(svc, "_refine_generate", fake_generate)

    asyncio.run(
        svc.refine_output(db, JOB_ID, str(output_id), instruction="qualcosa", previous_status="completed")
    )

    assert called["generate"] is False
    assert not [d for d in db.ai_architect_outputs.inserted if d.get("output_type") == "analysis"]
    # Errore loggato e stato ripristinato.
    assert db.ai_architect_errors.inserted
    assert db.ai_architect_jobs.updates[-1][1]["$set"]["status"] == "completed"


def test_action_credits_known_and_unknown():
    assert ai_credit_service.action_credits("ai_architect_regen_room_render") == 450
    try:
        ai_credit_service.action_credits("does_not_exist")
    except ValueError as exc:
        assert "sconosciuta" in str(exc)
    else:
        raise AssertionError("expected ValueError for unknown action key")


def test_keyword_classify_geometry_vs_aesthetic():
    # Errore strutturale (apertura) -> learnable + structural.
    opening = svc._normalize_refinement_classification(
        svc._refinement_keyword_classify("togli la finestra dal bagno"), "x"
    )
    assert opening["category"] == "opening_error"
    assert opening["structural"] is True
    assert opening["learnable"] is True

    # Preferenza estetica -> non strutturale.
    light = svc._normalize_refinement_classification(
        svc._refinement_keyword_classify("rendi piu luminoso"), "x"
    )
    assert light["structural"] is False
    assert light["category"] == "lighting_preference"


def test_normalize_classification_rejects_unknown_category():
    result = svc._normalize_refinement_classification(
        {"learnable": True, "category": "totally_unknown", "confidence": 2.0}, "x"
    )
    assert result["category"] == "other"
    assert result["learnable"] is False  # 'other' non e mai learnable
    assert 0.0 <= result["confidence"] <= 1.0


def test_learned_constraints_block_separates_strong_and_weak():
    memories = [
        {"strength": "strong", "extracted_rule": "Do not add bathroom windows absent from the plan."},
        {"strength": "weak", "extracted_rule": "Prefer warm modern lighting."},
    ]
    block = svc._learned_constraints_block(memories)
    assert "LEARNED_CORRECTION_MEMORY" in block
    assert "hard constraints" in block
    assert "Do not add bathroom windows" in block
    assert "LEARNED_STYLE_PREFERENCES" in block
    assert "warm modern lighting" in block
    assert svc._learned_constraints_block([]) == ""


def test_persist_refinement_memory_strength_by_category(monkeypatch):
    job = _job()
    output = {"_id": ObjectId(), "output_type": "room_render", "room_name": "Bagno"}
    db = FakeDB(job, [])

    strong_class = svc._normalize_refinement_classification(
        {
            "learnable": True,
            "category": "opening_error",
            "extracted_rule": "No bathroom window unless in PLAN_DETAILS_JSON.",
            "confidence": 0.8,
        },
        "x",
    )
    doc = asyncio.run(
        svc._persist_refinement_memory(
            db,
            job,
            output=output,
            refined_output_id="after1",
            instruction="togli la finestra dal bagno",
            region=None,
            classification=strong_class,
            fidelity_review={"fidelity_score": 0.9},
            reviewer="Tester",
        )
    )
    assert doc["strength"] == "strong"
    assert doc["accepted_by_staff"] is True
    # Confidenza = media tra classificazione e fidelity score.
    assert abs(doc["confidence"] - 0.85) < 1e-6

    weak_class = svc._normalize_refinement_classification(
        {"learnable": True, "category": "style_preference", "extracted_rule": "Prefer minimal style.", "confidence": 0.9},
        "x",
    )
    weak_doc = asyncio.run(
        svc._persist_refinement_memory(
            db,
            job,
            output=output,
            refined_output_id="after2",
            instruction="stile piu minimal",
            region=None,
            classification=weak_class,
            fidelity_review=None,
            reviewer="Tester",
        )
    )
    assert weak_doc["strength"] == "weak"


def test_retrieve_refinement_memories_ranks_strong_and_filters_weak():
    job = _job()  # account default, style "moderno luxury", room "cucina"
    account = ai_credit_service.ACCOUNT_ID
    memories = [
        {
            "account_id": account,
            "enabled": True,
            "learnable": True,
            "strength": "strong",
            "output_type": "room_render",
            "room_name": "Bagno",
            "category": "opening_error",
            "extracted_rule": "No bathroom window unless present in the plan.",
            "confidence": 0.8,
            "created_at": "2026-01-01",
        },
        {
            "account_id": account,
            "enabled": True,
            "learnable": True,
            "strength": "weak",
            "output_type": "room_render",
            "room_name": "Cucina",
            "style": "moderno luxury",
            "category": "style_preference",
            "extracted_rule": "Prefer warm modern lighting.",
            "confidence": 0.5,
            "created_at": "2026-01-02",
        },
        {
            "account_id": account,
            "enabled": True,
            "learnable": True,
            "strength": "weak",
            "output_type": "room_render",
            "room_name": "Taverna",
            "style": "industriale",
            "category": "style_preference",
            "extracted_rule": "Use exposed concrete.",
            "confidence": 0.5,
            "created_at": "2026-01-03",
        },
        {
            "account_id": account,
            "enabled": False,  # disattivata: esclusa
            "learnable": True,
            "strength": "strong",
            "output_type": "room_render",
            "category": "wall_error",
            "extracted_rule": "Disabled rule.",
            "confidence": 0.9,
            "created_at": "2026-01-04",
        },
    ]
    db = FakeDB(job, [], memories=memories)
    result = asyncio.run(svc._retrieve_refinement_memories(db, job, output_type="room_render"))
    rules = [m["extracted_rule"] for m in result]

    # La regola forte (cross-progetto) c'e; la preferenza dello stile/ambiente corrente c'e;
    # la preferenza di un altro stile/ambiente e la regola disattivata NON ci sono.
    assert "No bathroom window unless present in the plan." in rules
    assert "Prefer warm modern lighting." in rules
    assert "Use exposed concrete." not in rules
    assert "Disabled rule." not in rules
    # La regola forte precede le preferenze deboli.
    assert rules.index("No bathroom window unless present in the plan.") < rules.index(
        "Prefer warm modern lighting."
    )
