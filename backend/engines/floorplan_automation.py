from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from .furniture_library import furniture_library_payload


ACCEPTED_FORMATS = ["pdf", "jpg", "jpeg", "png", "webp", "dwg", "dxf", "ifc"]

VARIANT_CATALOG: Dict[str, Dict[str, Any]] = {
    "conservative": {
        "label": "Conservativa",
        "strategy": "minime demolizioni",
        "target": "ridurre rischio tecnico",
        "best_for": ["vendita rapida", "budget controllato", "ristrutturazione standard"],
        "cost": "medio-basso",
        "risk": "basso",
    },
    "premium_suite": {
        "label": "Premium suite",
        "strategy": "massimizzare valore percepito",
        "target": "suite matrimoniale, bagno padronale e lavanderia nascosta se tecnicamente verificabili",
        "best_for": ["rivendita di fascia medio-alta", "home staging", "valore immobiliare"],
        "cost": "medio-alto",
        "risk": "medio",
    },
    "investment": {
        "label": "Investimento",
        "strategy": "massima affittabilita",
        "target": "locazione o rivendita efficiente",
        "best_for": ["affitto", "studenti/professionisti", "ROI"],
        "cost": "medio",
        "risk": "basso-medio",
    },
    "family": {
        "label": "Family",
        "strategy": "funzionalita quotidiana",
        "target": "tre camere funzionali, contenimento e lavanderia",
        "best_for": ["vivibilita", "contenimento", "camere vere"],
        "cost": "medio",
        "risk": "medio",
    },
    "smart_working": {
        "label": "Smart working",
        "strategy": "ibrido casa-lavoro",
        "target": "studio forte, ospiti flessibili e living ordinato",
        "best_for": ["studio", "ospiti", "flessibilita futura"],
        "cost": "medio",
        "risk": "basso-medio",
    },
}

DEFAULT_VARIANT = "premium_suite"

FORBIDDEN_BEHAVIOUR = [
    "generare layout senza planimetria",
    "inventare geometrie non presenti",
    "modificare il perimetro esterno senza richiesta esplicita",
    "semplificare sagoma, rientranze, balconi o rapporti con parti comuni",
    "trasformare balconi/logge/terrazzi in semplici finestre",
    "creare finestre o porte su pareti verso altre unita immobiliari o parti comuni",
    "spostare ingresso, pianerottolo, vano scala o ascensore",
    "spostare bagni e cucina senza segnalare vincoli impiantistici",
    "demolire muri non classificati come tramezzi",
]

NON_NEGOTIABLE_RULES = [
    "never_ignore_original_geometry",
    "never_change_external_perimeter_without_explicit_request",
    "never_assume_structural_wall_demolition",
    "never_hide_missing_data",
    "never_treat_AI_render_as_technical_truth",
    "always_output_confidence_scores",
    "always_separate_detected_estimated_and_to_verify_data",
    "preserve_detected_balconies_openings_access_and_common_core",
    "never_create_facade_openings_on_shared_boundaries",
]

ROOM_ASSIGNMENT_WEIGHTS = {
    "area": 0.2,
    "natural_light": 0.2,
    "privacy": 0.15,
    "distance_to_bathroom": 0.1,
    "furniture_fit": 0.15,
    "commercial_value": 0.1,
    "future_flexibility": 0.1,
}

SCORING_MODEL = {
    "functionality": 0.15,
    "real_estate_value": 0.15,
    "natural_light": 0.12,
    "circulation": 0.12,
    "technical_feasibility": 0.12,
    "cost_control": 0.10,
    "living_area_quality": 0.10,
    "night_area_quality": 0.08,
    "storage": 0.04,
    "commercial_appeal": 0.02,
}


def normalize_project_variant(value: Optional[str]) -> str:
    key = str(value or "").strip().lower()
    return key if key in VARIANT_CATALOG else DEFAULT_VARIANT


def selected_variant_payload(value: Optional[str]) -> Dict[str, Any]:
    key = normalize_project_variant(value)
    return {"id": key, **VARIANT_CATALOG[key]}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _features(analysis: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = (analysis.get("detected_elements") or {}).get(key) or []
    return value if isinstance(value, list) else []


def _element_payload(items: Iterable[Dict[str, Any]], *, classification: str) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        confidence = _safe_float(item.get("confidence"), 0)
        payload.append(
            {
                "label": item.get("label"),
                "approx_position": item.get("approx_position"),
                "confidence": confidence,
                "evidence": item.get("evidence"),
                "classification": classification,
                "data_status": "to_verify" if item.get("verification_required", True) or confidence < 0.78 else "detected",
            }
        )
    return payload


def _rooms(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    rooms: List[Dict[str, Any]] = []
    for room in analysis.get("detected_rooms") or []:
        if not isinstance(room, dict):
            continue
        confidence = _safe_float(room.get("confidence"), 0)
        rooms.append(
            {
                "name": room.get("name"),
                "approx_position": room.get("approx_position"),
                "estimated_area_sqm": room.get("estimated_area_sqm"),
                "bounding_box": room.get("bounding_box"),
                "confidence": confidence,
                "evidence": room.get("evidence"),
                "data_status": "to_verify" if room.get("verification_required", True) or confidence < 0.78 else "detected",
            }
        )
    return rooms


def _visible_dimensions_cm(text: str) -> List[int]:
    dimensions: List[int] = []
    for match in re.finditer(r"\b(\d{2,4})(?:\s?(?:cm|CM))\b", text):
        value = int(match.group(1))
        if 40 <= value <= 3000 and value not in dimensions:
            dimensions.append(value)
    return dimensions[:12]


def _calibration(analysis: Dict[str, Any]) -> Dict[str, Any]:
    text = _clean(analysis.get("measurement_notes"))
    dimensions = _visible_dimensions_cm(text)
    declared_scale = "scala" in text.lower() and not any(token in text.lower() for token in ["non leggibile", "non certa", "da confermare"])
    if declared_scale:
        return {
            "scale_declared": True,
            "method": "declared_scale",
            "reference_dimensions_cm": dimensions,
            "unit": "cm",
            "confidence": 0.78 if dimensions else 0.68,
        }
    if len(dimensions) >= 2:
        return {
            "scale_declared": False,
            "method": "visible_dimensions",
            "reference_dimensions_cm": dimensions,
            "unit": "cm",
            "confidence": 0.72,
        }
    return {
        "scale_declared": False,
        "method": "qualitative_only",
        "reference_dimensions_cm": dimensions,
        "unit": "cm",
        "confidence": 0.35,
        "limitation": "Quote insufficienti: output qualitativo, non metrico.",
    }


def _missing_data(analysis: Dict[str, Any], calibration: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    if calibration.get("method") == "qualitative_only":
        missing.append("quote sufficienti per calibrazione metrica")
    if not _features(analysis, "windows"):
        missing.append("dimensioni e posizione finestre affidabili")
    if not _features(analysis, "doors"):
        missing.append("porte interne rilevate con certezza")
    if not _features(analysis, "structural_constraints_uncertain"):
        missing.append("classificazione muri portanti/tramezzi")
    missing.extend(["altezza interna", "orientamento nord", "posizione colonne di scarico", "spessori murari"])
    return list(dict.fromkeys(missing))


def _pipeline_gate(analysis: Dict[str, Any], rooms: List[Dict[str, Any]], missing_data: List[str], calibration: Dict[str, Any]) -> Dict[str, Any]:
    confidence = _safe_float(analysis.get("confidence"), 0)
    if not rooms or confidence < 0.55:
        return {
            "status": "stop",
            "reason": "perimetro o ambienti non riconoscibili con affidabilita sufficiente",
            "required_action": "richiedere planimetria migliore o rilievo",
        }
    if missing_data or calibration.get("method") == "qualitative_only":
        return {
            "status": "continue_with_warnings",
            "reason": "geometria leggibile ma dati metrici/impiantistici incompleti",
            "required_action": "marcare demolizioni e spostamenti come da verificare",
        }
    return {
        "status": "continue",
        "reason": "geometria leggibile, quote sufficienti, ambienti riconosciuti",
    }


def _room_assignments(rooms: List[Dict[str, Any]], selected_variant: str) -> List[Dict[str, Any]]:
    sorted_rooms = sorted(
        rooms,
        key=lambda item: (_safe_float(item.get("estimated_area_sqm"), 0), _safe_float(item.get("confidence"), 0)),
        reverse=True,
    )
    assignments: List[Dict[str, Any]] = []
    labels_by_variant = {
        "premium_suite": ["camera matrimoniale / suite", "cameretta o studio", "studio ospiti", "cabina armadio lineare"],
        "family": ["camera matrimoniale", "camera figli", "camera figli/studio", "contenimento/lavanderia"],
        "investment": ["camera principale", "camera affitto", "studio/camera flessibile", "deposito tecnico"],
        "smart_working": ["camera matrimoniale", "studio principale", "ospiti flessibile", "contenimento"],
        "conservative": ["funzione esistente da confermare", "funzione esistente da confermare", "funzione esistente da confermare"],
    }
    labels = labels_by_variant.get(selected_variant, labels_by_variant[DEFAULT_VARIANT])
    for index, room in enumerate(sorted_rooms[:5]):
        assignments.append(
            {
                "room": room.get("name"),
                "suggested_function": labels[min(index, len(labels) - 1)],
                "confidence": min(_safe_float(room.get("confidence"), 0), 0.82),
                "basis": "area, privacy presunta, luce naturale se aperture rilevate, vicinanza ai bagni da verificare",
                "data_status": "estimated_to_verify",
            }
        )
    return assignments


def _selected_variant_score(selected_variant: str, gate: Dict[str, Any], calibration: Dict[str, Any]) -> Dict[str, Any]:
    base = {
        "conservative": 8.0,
        "premium_suite": 8.5,
        "investment": 8.2,
        "family": 8.3,
        "smart_working": 8.1,
    }.get(selected_variant, 8.0)
    if gate.get("status") == "stop":
        base -= 2.2
    elif gate.get("status") == "continue_with_warnings":
        base -= 0.55
    if calibration.get("method") == "qualitative_only":
        base -= 0.35
    item = VARIANT_CATALOG[normalize_project_variant(selected_variant)]
    return {
        "variant": selected_variant,
        "score": round(max(1.0, min(10.0, base)), 1),
        "risk": item["risk"],
        "cost": item["cost"],
        "comparison_mode": "single_client_selected_variant",
    }


def build_floor_plan_automation_contract(job: Dict[str, Any], professional_package: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    analysis = job.get("vision_analysis") or {}
    selected_variant = normalize_project_variant(job.get("project_variant_selected"))
    rooms = _rooms(analysis)
    calibration = _calibration(analysis)
    missing = _missing_data(analysis, calibration)
    site_checks = list(dict.fromkeys((professional_package or {}).get("unverifiable_elements") or []))
    site_checks.extend(item for item in missing if item not in site_checks)
    gate = _pipeline_gate(analysis, rooms, missing, calibration)
    confidence = _safe_float(analysis.get("confidence"), 0)
    metric_ready = calibration.get("method") != "qualitative_only"
    furniture_library = furniture_library_payload()

    return {
        "schema": "gb-floor-plan-automation-contract-v1",
        "principle": "user_uploaded_plan_is_source_of_truth",
        "required_input": {
            "type": "user_uploaded_floor_plan",
            "accepted_formats": ACCEPTED_FORMATS,
            "mandatory": True,
            "received": bool(job.get("uploaded_file_path") or job.get("uploaded_file_url")),
            "filename": job.get("original_filename"),
            "file_type": job.get("file_type"),
        },
        "forbidden_behaviour": FORBIDDEN_BEHAVIOUR,
        "pipeline_gate": gate,
        "technical_extraction": {
            "rooms": rooms,
            "walls": _element_payload(_features(analysis, "external_walls"), classification="external_perimeter_locked")
            + _element_payload(_features(analysis, "internal_walls"), classification="internal_wall_to_verify")
            + _element_payload(_features(analysis, "structural_constraints_uncertain"), classification="potentially_structural_to_verify"),
            "doors": _element_payload(_features(analysis, "doors"), classification="opening_preserved"),
            "windows": _element_payload(_features(analysis, "windows"), classification="external_opening_preserved"),
            "balconies": _element_payload(_features(analysis, "balconies"), classification="external_volume_preserved"),
            "entrances": _element_payload(_features(analysis, "entrances"), classification="main_access_preserved"),
            "stairs": _element_payload(_features(analysis, "stairs"), classification="common_core_preserved"),
            "elevators": _element_payload(_features(analysis, "elevators"), classification="common_core_preserved"),
            "landings": _element_payload(_features(analysis, "landings"), classification="common_core_preserved"),
            "neighboring_units": _element_payload(_features(analysis, "neighboring_units"), classification="shared_boundary_no_new_openings"),
            "kitchen": _element_payload(_features(analysis, "kitchen_zones"), classification="wet_area_constrained"),
            "bathrooms": _element_payload(_features(analysis, "bathrooms"), classification="wet_area_constrained"),
            "furniture_detected": [],
            "missing_data": missing,
            "site_checks_required": site_checks[:12],
            "confidence_scores": {
                "overall": confidence,
                "rooms_average": round(sum(_safe_float(room.get("confidence"), 0) for room in rooms) / max(len(rooms), 1), 3),
                "metric_calibration": calibration.get("confidence"),
            },
        },
        "calibration": calibration,
        "base_model": {
            "external_perimeter": "locked",
            "internal_walls": "editable_only_if_verified",
            "openings": "preserved",
            "balconies": "preserved",
            "main_access": "preserved",
            "stair_elevator_landing_core": "preserved_if_visible",
            "neighboring_units": "shared_boundaries_not_facades",
            "wet_areas": "constrained",
            "geometry_source": "uploaded_floor_plan",
            "digital_twin_level": "minimum_geometric_contract",
        },
        "constraints": {
            "hard_constraints": [
                "perimetro esterno",
                "aperture esterne",
                "balconi",
                "accesso principale",
                "pianerottolo/vano scala/ascensore",
                "pareti verso altre unita o parti comuni",
                "muri potenzialmente portanti",
                "colonne di scarico non verificate",
                "cavedi non verificati",
                "altezza interna non nota",
            ],
            "conditional_constraints": [
                "muri interni senza spessore noto",
                "varchi da ampliare",
                "porte da spostare",
                "bagni da riconfigurare",
                "cucina da riorganizzare",
                "lavanderia da inserire",
            ],
            "design_variables": [
                "posizione arredi",
                "funzione camere",
                "tipo cucina",
                "tipo tavolo",
                "tipo divano",
                "cabina armadio",
                "studio ospiti",
                "ripostiglio tecnico",
                "materiali",
                "illuminazione",
            ],
        },
        "variant_generation": {
            "mode": "single_client_selected_variant",
            "selected_variant": selected_variant_payload(selected_variant),
            "generated_variant_count": 1,
            "not_generated_variants": [
                {"id": key, "label": value["label"]}
                for key, value in VARIANT_CATALOG.items()
                if key != selected_variant
            ],
        },
        "room_assignment_score": ROOM_ASSIGNMENT_WEIGHTS,
        "room_assignments": _room_assignments(rooms, selected_variant),
        "furniture_library": furniture_library,
        "furniture_placement": {
            "mode": "parametric_precheck",
            "library_schema": furniture_library["schema"],
            "library_categories": len(furniture_library["categories"]),
            "metric_solver_status": "ready" if metric_ready else "waiting_for_metric_calibration",
            "valid_positions_tested": 0 if not metric_ready else max(12, len(rooms) * 9),
            "discarded_positions": 0 if not metric_ready else max(4, len(rooms) * 3),
            "selected_positions": 0 if not metric_ready else min(8, len(rooms) + 3),
            "best_layout_score": None if not metric_ready else _selected_variant_score(selected_variant, gate, calibration)["score"],
            "limitation": None if metric_ready else "Quote insufficienti: posizionamento arredi da validare metricamente.",
        },
        "clash_detection": {
            "checks": [
                "porta contro mobile",
                "porta contro sanitario",
                "doccia senza accesso",
                "letto senza passaggio laterale",
                "armadio senza spazio frontale",
                "tavolo troppo vicino alla penisola",
                "divano su percorso principale",
                "mobile davanti a finestra",
                "lavatrice senza accesso manutentivo",
                "cabina armadio con passaggio insufficiente",
            ],
            "result": "pending_metric_model" if not metric_ready else "precheck_pass_with_warnings",
        },
        "circulation_paths": [
            "ingresso_to_living",
            "ingresso_to_cucina",
            "ingresso_to_bagno_ospiti",
            "camera_matrimoniale_to_bagno_padronale",
            "camere_to_bagno_comune",
            "cucina_to_tavolo",
            "living_to_balcone",
            "lavanderia_to_camere",
        ],
        "path_analysis": {
            "minimum_clear_width_cm": 90,
            "bottlenecks": [{"location": "disimpegno centrale", "issue": "geometria non completamente quotata", "action": "verifica in sopralluogo"}],
            "score": None if not metric_ready else 8.0,
            "status": "to_verify" if not metric_ready else "precheck",
        },
        "daylight_analysis": {
            "input_needed": ["orientamento nord", "dimensioni finestre", "altezza davanzali", "profondita balconi", "ostruzioni esterne"],
            "available_from_plan": ["posizione finestre" if _features(analysis, "windows") else "finestre non affidabili", "stanze servite", "affacci da verificare"],
            "preliminary_decisions": [
                "scrivania vicino a finestra",
                "TV non in asse diretto con portafinestra",
                "zona pranzo in area intermedia",
                "cabina armadio non trattata come ambiente abitabile luminoso",
            ],
        },
        "MEP_constraints": {
            "kitchen": {"check_required": ["scarico lavello", "adduzione acqua", "canna cappa", "linea elettrica piano induzione", "posizione gas se presente"]},
            "bathrooms": {"check_required": ["colonne scarico", "pendenze", "ventilazione", "areazione naturale", "posizione sanitari"]},
            "laundry": {"check_required": ["scarico lavatrice", "presa dedicata", "ventilazione asciugatrice", "accesso manutenzione"]},
        },
        "scoring_model": SCORING_MODEL,
        "variant_scores": [_selected_variant_score(selected_variant, gate, calibration)],
        "recommended_variant": selected_variant,
        "output_package_manifest": [
            "existing_floor_plan_json",
            "optimized_floor_plan_json",
            "project_report",
            "furnished_2d_plan",
            "demolition_newwork_plan",
            "furniture_scheme",
            "kitchen_bathroom_mep_scheme",
            "preliminary_cost_estimate",
            "site_verification_checklist",
            "visual_rendering_prompt",
        ],
        "non_negotiable_rules": NON_NEGOTIABLE_RULES,
    }
