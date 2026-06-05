from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional

from .floorplan_automation import (
    DEFAULT_VARIANT,
    NON_NEGOTIABLE_RULES,
    ROOM_ASSIGNMENT_WEIGHTS,
    SCORING_MODEL,
    VARIANT_CATALOG,
    normalize_project_variant,
)
from .furniture_library import furniture_library_payload


TECHNICAL_JSON_SCHEMA = "gb-technical-floor-plan-json-v1"
OPTIMIZED_JSON_SCHEMA = "gb-optimized-floor-plan-json-v1"


def technical_extraction_prompt(job: Dict[str, Any]) -> str:
    brief = {
        "plan_type_selected": job.get("plan_type_selected"),
        "project_variant_selected": normalize_project_variant(job.get("project_variant_selected")),
        "style_selected": job.get("style_selected"),
        "project_goal": job.get("project_goal"),
        "priorities": job.get("priorities") or [],
        "sqm_declared_by_user": job.get("sqm"),
        "residents": job.get("residents"),
        "budget": job.get("budget"),
        "notes": job.get("notes"),
    }
    return (
        "Analizza questa planimetria come un architetto tecnico specializzato in rilievo, interior design "
        "e ristrutturazioni residenziali.\n\n"
        "Obiettivo: estrarre un JSON tecnico completo, strutturato e validabile, non una semplice descrizione visiva.\n\n"
        "Regole:\n"
        "1. Usa centimetri come unita di misura.\n"
        "2. Se la scala non e dichiarata, calibra il disegno usando le quote visibili.\n"
        "3. Non inventare dati non presenti.\n"
        "4. Ogni informazione incerta deve avere confidence score da 0 a 1.\n"
        "5. Distingui dati rilevati dalla planimetria, dati stimati, dati mancanti e dati da verificare in sopralluogo.\n"
        "6. Riconosci ambienti, muri, aperture, porte, finestre, balconi, arredi, sanitari, cucina, disimpegni e vani tecnici.\n"
        "7. Per ogni ambiente calcola, se possibile, superficie netta, perimetro, dimensioni principali, rapporti, accessi, finestre, arredi compatibili e criticita.\n"
        "8. Per ogni muro crea un oggetto separato con ID, coordinate, lunghezza, spessore se rilevabile, stato e funzione.\n"
        "9. Per ogni porta/apertura crea un oggetto separato con ID, larghezza, verso apertura se visibile, ambienti collegati e muro di appartenenza.\n"
        "10. Per ogni finestra/portafinestra crea un oggetto separato con ID, ambiente servito, parete, dimensioni, affaccio e impatto su luce/aerazione.\n"
        "11. Inserisci sezioni per demolizioni, nuovi tramezzi, interventi consigliati, vincoli tecnici e verifiche necessarie.\n"
        "12. Restituisci solo JSON valido, senza testo esterno.\n\n"
        "Il JSON deve essere inserito nel campo technical_floor_plan_json dello schema richiesto. "
        f"Brief utente: {json.dumps(brief, ensure_ascii=False)}"
    )


def optimization_prompt(job: Dict[str, Any], technical_floor_plan_json: Dict[str, Any]) -> str:
    variant = VARIANT_CATALOG[normalize_project_variant(job.get("project_variant_selected"))]
    return (
        "Agisci come un architetto senior specializzato in ristrutturazione di appartamenti, space planning, "
        "interior design residenziale e ottimizzazione immobiliare.\n\n"
        "Riceverai in input un JSON tecnico estratto da una planimetria esistente. Analizza il JSON e genera "
        "una proposta ottimizzata mantenendo coerenza con la geometria della planimetria di partenza.\n\n"
        f"VARIANTE SCELTA DAL CLIENTE: {variant['label']} - {variant['strategy']}. Genera solo questa variante.\n\n"
        "Regole: non inventare dati tecnici non presenti; se manca un dato, inserirlo nei dati mancanti/da verificare; "
        "mantieni perimetro esterno, balconi, affacci e aperture esterne; non demolire muri potenzialmente portanti; "
        "non spostare bagni e cucina senza verifica scarichi, colonne, pendenze e cavedi; usa centimetri e metri quadrati; "
        "motiva ogni scelta architettonica e commerciale.\n\n"
        "Restituisci un JSON con: sintesi progettuale, analisi stato attuale, criticita, strategia, nuova distribuzione, "
        "interventi edilizi, arredo, materiali/finiture, verifiche obbligatorie, scoring finale, optimized_floor_plan_json "
        "e prompt visuale per planimetria 2D colorata.\n\n"
        f"JSON tecnico di input: {json.dumps(technical_floor_plan_json, ensure_ascii=False, separators=(',', ':'))[:12000]}"
    )


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _features(analysis: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
    value = (analysis.get("detected_elements") or {}).get(key) or []
    return [item for item in value if isinstance(item, dict)]


def _status(confidence: Optional[float], verification_required: bool = True) -> str:
    if confidence is None:
        return "missing"
    if verification_required or confidence < 0.78:
        return "estimated_to_verify"
    return "detected"


def _normalized_box(box: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(box, dict):
        return None
    required = ("x", "y", "width", "height")
    if not all(key in box for key in required):
        return None
    return {key: _safe_float(box.get(key), 0.0) for key in required}


def _incoming_technical_json(job: Dict[str, Any]) -> Dict[str, Any]:
    analysis = job.get("vision_analysis") or {}
    value = analysis.get("technical_floor_plan_json") or job.get("technical_floor_plan_json")
    return deepcopy(value) if isinstance(value, dict) else {}


def _room_furniture_candidates(room_name: str, library: Dict[str, Any]) -> List[Dict[str, Any]]:
    name = room_name.lower()
    categories = library.get("categories") or {}
    selected: List[Dict[str, Any]] = []
    preferred_categories: List[str] = []
    if any(token in name for token in ["soggiorno", "living", "giorno"]):
        preferred_categories = ["living", "dining", "workspace"]
    elif "cucina" in name:
        preferred_categories = ["kitchen", "appliances", "dining"]
    elif "bagno" in name or "servizio" in name:
        preferred_categories = ["bathroom", "appliances"]
    elif "camera" in name or "letto" in name:
        preferred_categories = ["bedroom", "storage", "workspace"]
    elif "studio" in name:
        preferred_categories = ["workspace", "storage"]
    elif "balcon" in name or "terrazz" in name:
        preferred_categories = ["balcony"]
    else:
        preferred_categories = ["storage", "entry", "workspace"]
    for category in preferred_categories:
        for item_id, item in (categories.get(category) or {}).items():
            selected.append(
                {
                    "id": item_id,
                    "category": category,
                    "dimensions_cm": item.get("dimensions_cm"),
                    "clearance_cm": item.get("clearance_cm"),
                    "data_status": "library_constraint",
                }
            )
            if len(selected) >= 5:
                return selected
    return selected


def _technical_rooms(analysis: Dict[str, Any], library: Dict[str, Any]) -> List[Dict[str, Any]]:
    rooms: List[Dict[str, Any]] = []
    for index, room in enumerate(analysis.get("detected_rooms") or [], start=1):
        if not isinstance(room, dict) or not room.get("name"):
            continue
        confidence = _safe_float(room.get("confidence"), 0.0) or 0.0
        area = _safe_float(room.get("estimated_area_sqm"))
        rooms.append(
            {
                "id": f"room_{index:02d}",
                "name": room.get("name"),
                "data_status": _status(confidence, bool(room.get("verification_required", True))),
                "source": "vision_analysis",
                "confidence": confidence,
                "evidence": room.get("evidence"),
                "approx_position": room.get("approx_position"),
                "bounding_box_normalized": _normalized_box(room.get("bounding_box")),
                "surface_net_sqm": area,
                "surface_status": "estimated" if area is not None else "missing",
                "perimeter_cm": None,
                "perimeter_status": "missing",
                "main_dimensions_cm": [],
                "relationships": [],
                "access_ids": [],
                "window_ids": [],
                "compatible_furniture": _room_furniture_candidates(str(room.get("name") or ""), library),
                "criticalities": [
                    "dimensioni principali non quotate" if area is None else "superficie stimata da verificare",
                    "spessori murari e quote da verificare in sopralluogo",
                ],
            }
        )
    return rooms


def _feature_objects(items: Iterable[Dict[str, Any]], prefix: str, role: str, *, status_default: str = "da_verificare") -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        confidence = _safe_float(item.get("confidence"), 0.0) or 0.0
        output.append(
            {
                "id": f"{prefix}_{index:02d}",
                "label": item.get("label"),
                "role": role,
                "coordinates": None,
                "approx_position": item.get("approx_position"),
                "length_cm": None,
                "width_cm": None,
                "height_cm": None,
                "thickness_cm": None,
                "opening_direction": None,
                "connected_rooms": [],
                "parent_wall_id": None,
                "status": status_default,
                "function": role,
                "data_status": _status(confidence, bool(item.get("verification_required", True))),
                "confidence": confidence,
                "evidence": item.get("evidence"),
                "site_check_required": bool(item.get("verification_required", True)) or confidence < 0.85,
            }
        )
    return output


def build_technical_floor_plan_json(job: Dict[str, Any]) -> Dict[str, Any]:
    incoming = _incoming_technical_json(job)
    if incoming:
        payload = deepcopy(incoming)
        payload.setdefault("schema", TECHNICAL_JSON_SCHEMA)
        payload.setdefault("unit", "cm")
        payload.setdefault("source", "vision_model_technical_floor_plan_json")
        payload.setdefault("generated_by", "image_first_technical_extraction")
        payload.setdefault("data_status", "model_extracted_to_verify")
        payload.setdefault("technical_extraction_prompt", technical_extraction_prompt(job))
        return payload

    analysis = job.get("vision_analysis") or {}
    library = furniture_library_payload()
    rooms = _technical_rooms(analysis, library)
    walls = (
        _feature_objects(_features(analysis, "external_walls"), "wall_ext", "esterno", status_default="esistente")
        + _feature_objects(_features(analysis, "internal_walls"), "wall_int", "divisorio", status_default="esistente_da_verificare")
        + _feature_objects(_features(analysis, "structural_constraints_uncertain"), "wall_uncertain", "portante_sconosciuto", status_default="da_verificare")
    )
    doors = _feature_objects(_features(analysis, "doors"), "door", "porta_o_apertura", status_default="esistente")
    windows = _feature_objects(_features(analysis, "windows"), "window", "finestra_o_portafinestra", status_default="esistente")
    balconies = _feature_objects(_features(analysis, "balconies"), "balcony", "balcone", status_default="esistente")
    kitchens = _feature_objects(_features(analysis, "kitchen_zones"), "kitchen", "cucina", status_default="esistente_da_verificare")
    bathrooms = _feature_objects(_features(analysis, "bathrooms"), "bathroom", "bagno", status_default="esistente_da_verificare")
    missing = [
        "scala dichiarata o quote sufficienti per calibrazione metrica",
        "coordinate metriche di muri e aperture",
        "spessori murari certi",
        "classificazione portanti/tramezzi",
        "posizione colonne di scarico e cavedi",
        "dimensioni finestre e davanzali",
        "altezza interna",
        "orientamento nord",
    ]
    return {
        "schema": TECHNICAL_JSON_SCHEMA,
        "unit": "cm",
        "source": "deterministic_from_plan_vision_analysis",
        "generated_by": "image_first_json_fallback",
        "data_status": "partial_to_verify",
        "technical_extraction_prompt": technical_extraction_prompt(job),
        "metadata": {
            "filename": job.get("original_filename"),
            "file_type": job.get("file_type"),
            "plan_type_selected": job.get("plan_type_selected"),
            "plan_type_detected": analysis.get("plan_type_detected") or job.get("plan_type_detected"),
            "project_variant_selected": normalize_project_variant(job.get("project_variant_selected")),
            "confidence": _safe_float(analysis.get("confidence"), 0.0),
        },
        "calibration": {
            "scale_declared": False,
            "method": "visible_dimensions_if_present_else_qualitative",
            "reference_dimensions_cm": [],
            "confidence": 0.35,
            "limitation": "JSON costruito senza coordinate metriche complete; usare come contratto tecnico preliminare.",
        },
        "rooms": rooms,
        "walls": walls,
        "doors": doors,
        "windows": windows,
        "balconies": balconies,
        "furniture_detected": _feature_objects(_features(analysis, "furniture"), "furniture", "arredo_esistente", status_default="esistente_da_verificare"),
        "sanitary": _feature_objects(_features(analysis, "sanitary"), "sanitary", "sanitario", status_default="esistente_da_verificare"),
        "kitchen": kitchens,
        "bathrooms": bathrooms,
        "corridors": _feature_objects(_features(analysis, "corridors"), "corridor", "disimpegno", status_default="esistente_da_verificare"),
        "technical_shafts": _feature_objects(_features(analysis, "technical_shafts"), "shaft", "vano_tecnico_o_cavedio", status_default="da_verificare"),
        "demolitions": [],
        "new_partitions": [],
        "recommended_interventions": [],
        "technical_constraints": [
            "perimetro esterno bloccato",
            "aperture esterne da mantenere",
            "bagni e cucina vincolati a scarichi/colonne da verificare",
            "muri portanti non classificabili automaticamente",
        ],
        "missing_data": missing,
        "site_checks_required": missing + [
            "rilievo metrico completo",
            "verifica strutturale prima di demolizioni",
            "verifica impiantistica prima di spostare cucina, bagni o lavanderia",
        ],
        "confidence_scores": {
            "overall": _safe_float(analysis.get("confidence"), 0.0),
            "geometry": 0.45 if rooms else 0.2,
            "metric_calibration": 0.35,
            "mep_constraints": 0.3,
        },
    }


def _room_assignment_label(index: int, variant: str) -> str:
    labels = {
        "premium_suite": ["living open-space", "suite matrimoniale", "camera/studio", "bagno/lavanderia"],
        "family": ["living familiare", "camera matrimoniale", "camera figli", "studio/camera flessibile"],
        "investment": ["living compatto", "camera principale", "camera affitto", "studio/ospiti"],
        "smart_working": ["living ordinato", "studio principale", "camera matrimoniale", "ospiti flessibile"],
        "conservative": ["funzione esistente ottimizzata", "funzione esistente ottimizzata", "funzione esistente ottimizzata"],
    }
    selected = labels.get(variant, labels[DEFAULT_VARIANT])
    return selected[min(index, len(selected) - 1)]


def _score_value(base: float, missing_count: int, *, technical_risk: bool = True) -> float:
    value = base - min(1.2, missing_count * 0.08)
    if technical_risk:
        value -= 0.25
    return round(max(1.0, min(10.0, value)), 1)


def build_optimized_floor_plan_json(job: Dict[str, Any], technical_floor_plan_json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    technical = technical_floor_plan_json or build_technical_floor_plan_json(job)
    variant_key = normalize_project_variant(job.get("project_variant_selected"))
    variant = VARIANT_CATALOG[variant_key]
    library = furniture_library_payload()
    rooms = technical.get("rooms") or []
    missing = technical.get("missing_data") or []
    optimized_rooms: List[Dict[str, Any]] = []
    for index, room in enumerate(rooms[:8]):
        room_name = str(room.get("name") or f"Ambiente {index + 1}")
        suggested_function = _room_assignment_label(index, variant_key)
        optimized_rooms.append(
            {
                "id": f"opt_room_{index + 1:02d}",
                "source_room_id": room.get("id"),
                "existing_name": room_name,
                "new_function": suggested_function,
                "position": room.get("approx_position"),
                "surface_sqm": room.get("surface_net_sqm"),
                "dimensions_cm": room.get("main_dimensions_cm") or [],
                "furniture": _room_furniture_candidates(suggested_function + " " + room_name, library),
                "minimum_clearances_cm": library.get("general_clearances_cm"),
                "connections": room.get("relationships") or [],
                "changes_from_existing": [
                    "funzione ottimizzata secondo variante cliente",
                    "geometria non modificata senza verifica tecnica",
                ],
                "design_reason": f"Coerente con strategia {variant['label']}: {variant['strategy']}.",
                "commercial_reason": f"Allinea l'ambiente a {variant['target']}.",
                "confidence": min(0.82, _safe_float(room.get("confidence"), 0.62) or 0.62),
                "data_status": "estimated_to_verify",
            }
        )

    if not optimized_rooms:
        optimized_rooms.append(
            {
                "id": "opt_room_01",
                "source_room_id": None,
                "existing_name": "Ambienti non sufficientemente estratti",
                "new_function": variant["label"],
                "position": "da verificare",
                "surface_sqm": None,
                "dimensions_cm": [],
                "furniture": [],
                "minimum_clearances_cm": library.get("general_clearances_cm"),
                "connections": [],
                "changes_from_existing": ["nessuna redistribuzione automatica senza JSON tecnico valido"],
                "design_reason": "Il sistema non inventa ambienti non presenti nel JSON tecnico.",
                "commercial_reason": "La qualita percepita dipende da rilievo o planimetria piu leggibile.",
                "confidence": 0.25,
                "data_status": "insufficient_data",
            }
        )

    technical_risk = bool(missing)
    scoring = {
        "functionality": _score_value(8.2, len(missing), technical_risk=technical_risk),
        "real_estate_value": _score_value(8.4 if variant_key == "premium_suite" else 8.0, len(missing), technical_risk=technical_risk),
        "natural_light": _score_value(7.8, len(missing), technical_risk="orientamento nord" in " ".join(missing).lower()),
        "circulation": _score_value(8.0, len(missing), technical_risk=technical_risk),
        "living_area_quality": _score_value(8.3, len(missing), technical_risk=technical_risk),
        "night_area_quality": _score_value(8.0, len(missing), technical_risk=technical_risk),
        "cost_control": _score_value(8.5 if variant_key == "conservative" else 7.5, len(missing), technical_risk=technical_risk),
        "technical_feasibility": _score_value(7.8, len(missing), technical_risk=True),
        "commercial_appeal": _score_value(8.5, len(missing), technical_risk=technical_risk),
        "future_flexibility": _score_value(8.1, len(missing), technical_risk=technical_risk),
    }
    visual_prompt = (
        "Generate a professional colored 2D architectural floor plan from optimized_floor_plan_json only. "
        "Preserve the uploaded external perimeter, balconies, terraces, exterior openings and detected wet areas. "
        "Do not invent rooms, balconies, doors, windows, stairs, structural walls or furniture not allowed by the JSON. "
        "Use clean black wall lines, subtle room colors, realistic furniture blocks from the parametric library, dimension labels only where available, "
        "legend for existing walls, demolitions, new partitions, MEP checks, and site-verification notes. "
        "If a datum is missing, mark it as to verify instead of drawing it as certain."
    )
    return {
        "schema": OPTIMIZED_JSON_SCHEMA,
        "unit": "cm",
        "source": "technical_floor_plan_json",
        "optimization_prompt": optimization_prompt(job, technical),
        "metadata": {
            "project_goal": job.get("project_goal"),
            "style_selected": job.get("style_selected"),
            "selected_variant": {"id": variant_key, **variant},
            "technical_source_schema": technical.get("schema"),
            "technical_source": technical.get("source"),
        },
        "strategy": {
            "summary": f"Generare solo la variante {variant['label']} mantenendo vincoli e dati incerti espliciti.",
            "objectives": [variant["strategy"], variant["target"], "massimizzare coerenza con la planimetria caricata"],
            "non_negotiable_rules": NON_NEGOTIABLE_RULES,
            "room_assignment_weights": ROOM_ASSIGNMENT_WEIGHTS,
        },
        "existing_state_analysis": {
            "rooms_count": len(rooms),
            "strengths": (job.get("vision_analysis") or {}).get("architectural_analysis", {}).get("strengths", []),
            "criticalities": (job.get("vision_analysis") or {}).get("architectural_analysis", {}).get("weaknesses", []),
            "missing_data": missing,
            "potential": variant["best_for"],
        },
        "optimized_rooms": optimized_rooms,
        "walls_to_keep": technical.get("walls") or [],
        "walls_to_demolish": [],
        "new_partitions": [],
        "doors_and_openings": technical.get("doors") or [],
        "windows_and_views": technical.get("windows") or [],
        "furniture": [item for room in optimized_rooms for item in (room.get("furniture") or [])],
        "bathrooms": technical.get("bathrooms") or [],
        "kitchen": technical.get("kitchen") or [],
        "laundry": {
            "proposal": "lavanderia solo se compatibile con scarichi, ventilazione e spazio manutentivo",
            "status": "to_verify",
            "mep_checks": ["scarico lavatrice", "presa dedicata", "ventilazione asciugatrice", "accesso manutenzione"],
        },
        "materials_and_finishes": [
            "pavimento continuo o grande formato per aumentare continuita visiva",
            "illuminazione tecnica su percorsi e zone operative",
            "contenimento su misura dove il JSON indica spazi residui o disimpegni",
        ],
        "legend": {
            "existing": "nero",
            "demolition": "rosso solo se verificato",
            "new_partitions": "blu solo se verificato",
            "mep_to_verify": "arancio",
            "missing_or_uncertain": "grigio tratteggiato",
        },
        "technical_checks_required": technical.get("site_checks_required") or [],
        "scoring_model": SCORING_MODEL,
        "final_scoring": scoring,
        "confidence": {
            "overall": round(sum(scoring.values()) / max(len(scoring), 1) / 10, 2),
            "geometry": (technical.get("confidence_scores") or {}).get("geometry"),
            "metric": (technical.get("confidence_scores") or {}).get("metric_calibration"),
            "mep": (technical.get("confidence_scores") or {}).get("mep_constraints"),
        },
        "visual_prompt": visual_prompt,
    }
