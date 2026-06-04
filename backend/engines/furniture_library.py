from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict


RESEARCH_REFERENCES = [
    {
        "id": "ada_2010_accessible_routes",
        "label": "2010 ADA Standards - accessible routes and maneuvering clearances",
        "url": "https://www.ada.gov/law-and-regs/design-standards/2010-stds/",
        "use": "minimum circulation and door-clearance sanity checks, converted to metric where useful",
    },
    {
        "id": "dm_236_1989_accessibility",
        "label": "DM 236/1989 - accessibilita, visitabilita e adattabilita",
        "url": "https://www.mit.gov.it/normativa/decreto-ministeriale-numero-236-del-14061989",
        "source_urls": [
            "https://www.mit.gov.it/normativa/decreto-ministeriale-numero-236-del-14061989",
            "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=089G0298&atto.dataPubblicazioneGazzetta=1989-06-23&qId=&tipoDettaglio=originario",
        ],
        "use": "Italian residential accessibility reference: doors, corridors, maneuvering spaces",
        "source_quality": "primary",
    },
    {
        "id": "dm_5_7_1975_hygiene",
        "label": "DM 5 luglio 1975 - requisiti igienico-sanitari abitazioni",
        "url": "https://www.lavoripubblici.it/normativa/19750705/Decreto-ministeriale-Sanit-5-luglio-1975-25076.html",
        "source_urls": [
            "https://www.lavoripubblici.it/normativa/19750705/Decreto-ministeriale-Sanit-5-luglio-1975-25076.html",
            "https://www.bosettiegatti.eu/INFO/NORME/statali/1975_dm_05_07.htm",
        ],
        "use": "minimum residential room and hygiene checks; not a furniture source",
        "source_quality": "technical_reference",
    },
    {
        "id": "ikea_metod_reference",
        "label": "IKEA METOD cabinet dimensions",
        "url": "https://www.ikea.com/nl/en/p/metod-base-cabinet-frame-black-grey-80591701/",
        "use": "European modular kitchen sanity ranges, not project-specific specification",
    },
]


GENERAL_CLEARANCES_CM = {
    "main_circulation_min": 90,
    "comfortable_circulation": 100,
    "door_clear_opening_reference": 80,
    "wardrobe_front_min": 80,
    "bed_side_min": 60,
    "bed_front_min": 80,
    "table_around_min": 80,
    "kitchen_working_side_min": 95,
    "kitchen_two_cook_aisle": 120,
    "shower_entry_min": 60,
    "washer_service_front": 80,
    "accessible_turning_reference": 150,
    "minimum_internal_corridor_reference": 100,
    "door_maneuvering_reference": 120,
}


PARAMETRIC_SOLVER_RULES = {
    "room_compatibility": [
        "reject if room label matches any forbidden_rooms token",
        "prefer if room label matches allowed_rooms token",
        "if room label is uncertain, mark selected position as estimated_to_verify",
    ],
    "geometry": [
        "external perimeter, balconies and external openings are locked",
        "balcony furniture is allowed only on detected balconies and cannot create new balcony geometry",
        "keep all furniture clear of door swing and window opening zones",
    ],
    "mep": [
        "kitchen, laundry and bathroom fixtures require MEP checks before final approval",
        "do not move kitchen or sanitary fixtures away from wet areas without flagging scarichi, pendenze and ventilation",
        "reject kitchen modules inside bathrooms and sanitary fixtures inside kitchens/living areas",
    ],
    "metric": [
        "run exact collision checks only after scale calibration",
        "if calibration is qualitative_only, output furniture intent with metric_solver_status waiting_for_metric_calibration",
    ],
}


PARAMETRIC_FURNITURE_LIBRARY: Dict[str, Dict[str, Any]] = {
    "entry": {
        "console": {
            "dimensions_cm": [{"width": 90, "depth": 30}, {"width": 120, "depth": 35}],
            "clearance_cm": {"front": 90},
            "allowed_rooms": ["ingresso", "disimpegno largo"],
            "forbidden_rooms": ["bagno", "cucina stretta"],
        },
        "shoe_cabinet": {
            "dimensions_cm": [{"width": 80, "depth": 25}, {"width": 120, "depth": 35}],
            "clearance_cm": {"front": 80},
            "allowed_rooms": ["ingresso", "disimpegno", "guardaroba"],
            "forbidden_rooms": ["bagno", "corridoio stretto"],
        },
        "coat_closet": {
            "dimensions_cm": [{"width": 100, "depth": 60}, {"width": 160, "depth": 60}],
            "clearance_cm": {"front": 80},
            "allowed_rooms": ["ingresso", "guardaroba", "disimpegno largo"],
            "forbidden_rooms": ["bagno", "cucina"],
        },
        "entry_bench": {
            "dimensions_cm": [{"width": 90, "depth": 40}, {"width": 120, "depth": 45}],
            "clearance_cm": {"front": 80},
            "allowed_rooms": ["ingresso", "guardaroba"],
            "forbidden_rooms": ["bagno", "cucina"],
        },
    },
    "living": {
        "sofa_2_seat": {
            "dimensions_cm": [{"width": 180, "depth": 90}, {"width": 200, "depth": 95}],
            "clearance_cm": {"front": 90, "side": 50},
            "allowed_rooms": ["living", "soggiorno", "studio ospiti"],
            "forbidden_rooms": ["bagno", "bagno di servizio", "cabina armadio"],
        },
        "sofa_3_seat": {
            "dimensions_cm": [{"width": 240, "depth": 95}, {"width": 280, "depth": 100}, {"width": 300, "depth": 100}],
            "clearance_cm": {"front": 90, "side": 60},
            "allowed_rooms": ["living", "soggiorno", "zona giorno"],
            "forbidden_rooms": ["bagno", "cucina stretta", "disimpegno"],
        },
        "chaise_longue_sofa": {
            "dimensions_cm": [{"width": 280, "depth": 160}, {"width": 320, "depth": 170}],
            "clearance_cm": {"front": 95, "open_side": 80},
            "allowed_rooms": ["living", "soggiorno"],
            "forbidden_rooms": ["camera", "bagno", "corridoio"],
        },
        "tv_wall": {
            "dimensions_cm": [{"width": 180, "depth": 35}, {"width": 240, "depth": 45}],
            "clearance_cm": {"front": 100},
            "allowed_rooms": ["living", "soggiorno", "camera"],
            "forbidden_rooms": ["bagno"],
        },
        "armchair": {
            "dimensions_cm": [{"width": 80, "depth": 85}, {"width": 95, "depth": 95}],
            "clearance_cm": {"front": 70, "side": 50},
            "allowed_rooms": ["living", "soggiorno", "camera grande", "studio"],
            "forbidden_rooms": ["bagno", "cucina stretta"],
        },
        "coffee_table": {
            "dimensions_cm": [{"width": 90, "depth": 60}, {"width": 120, "depth": 70}],
            "clearance_cm": {"around": 45, "main_path": 90},
            "allowed_rooms": ["living", "soggiorno"],
            "forbidden_rooms": ["bagno", "corridoio"],
        },
    },
    "dining": {
        "dining_table_4": {
            "dimensions_cm": [{"width": 140, "depth": 80}, {"width": 160, "depth": 90}],
            "clearance_cm": {"around": 80, "preferred_around": 90},
            "allowed_rooms": ["living", "soggiorno", "cucina", "zona pranzo"],
            "forbidden_rooms": ["bagno", "camera piccola"],
        },
        "dining_table_6": {
            "dimensions_cm": [{"width": 180, "depth": 90}, {"width": 200, "depth": 95}],
            "clearance_cm": {"around": 90},
            "allowed_rooms": ["living", "soggiorno", "zona pranzo"],
            "forbidden_rooms": ["bagno", "corridoio"],
        },
        "round_table": {
            "dimensions_cm": [{"diameter": 110}, {"diameter": 120}, {"diameter": 140}],
            "clearance_cm": {"around": 85},
            "allowed_rooms": ["living", "soggiorno", "cucina"],
            "forbidden_rooms": ["bagno"],
        },
    },
    "bedroom": {
        "single_bed": {
            "dimensions_cm": [{"width": 90, "depth": 200}, {"width": 120, "depth": 200}],
            "clearance_cm": {"side": 60, "front": 80},
            "allowed_rooms": ["camera", "cameretta", "studio ospiti"],
            "forbidden_rooms": ["bagno", "cucina"],
        },
        "double_bed": {
            "dimensions_cm": [{"width": 160, "depth": 200}, {"width": 180, "depth": 200}],
            "clearance_cm": {"left": 60, "right": 60, "front": 80},
            "allowed_rooms": ["camera matrimoniale", "camera", "suite"],
            "forbidden_rooms": ["bagno", "cabina armadio", "cucina"],
        },
        "king_bed": {
            "dimensions_cm": [{"width": 190, "depth": 200}, {"width": 200, "depth": 200}],
            "clearance_cm": {"left": 70, "right": 70, "front": 90},
            "allowed_rooms": ["suite", "camera matrimoniale grande"],
            "forbidden_rooms": ["bagno", "cameretta"],
        },
        "nightstand_pair": {
            "dimensions_cm": [{"width": 45, "depth": 40}, {"width": 55, "depth": 45}],
            "clearance_cm": {"front": 50},
            "allowed_rooms": ["camera", "suite"],
            "forbidden_rooms": ["bagno"],
        },
        "crib": {
            "dimensions_cm": [{"width": 70, "depth": 140}],
            "clearance_cm": {"front": 80, "side": 60},
            "allowed_rooms": ["camera", "cameretta"],
            "forbidden_rooms": ["bagno", "cucina", "cabina armadio"],
        },
        "bunk_bed": {
            "dimensions_cm": [{"width": 90, "depth": 200}],
            "clearance_cm": {"front": 90, "ladder_side": 80},
            "allowed_rooms": ["cameretta", "camera figli"],
            "forbidden_rooms": ["bagno", "suite stretta"],
        },
    },
    "storage": {
        "wardrobe_hinged": {
            "dimensions_cm": [{"width": 180, "depth": 60}, {"width": 240, "depth": 60}, {"width": 300, "depth": 60}],
            "clearance_cm": {"front": 90},
            "allowed_rooms": ["camera", "cabina armadio", "disimpegno largo"],
            "forbidden_rooms": ["bagno stretto", "cucina"],
        },
        "wardrobe_sliding": {
            "dimensions_cm": [{"width": 180, "depth": 65}, {"width": 240, "depth": 65}, {"width": 300, "depth": 65}],
            "clearance_cm": {"front": 80},
            "allowed_rooms": ["camera", "cabina armadio"],
            "forbidden_rooms": ["bagno", "corridoio stretto"],
        },
        "linear_walk_in_closet": {
            "dimensions_cm": [{"width": 240, "depth": 60}, {"width": 300, "depth": 60}],
            "clearance_cm": {"passage": 90, "minimum_passage": 80},
            "allowed_rooms": ["cabina armadio", "suite"],
            "forbidden_rooms": ["bagno di servizio", "cucina"],
        },
        "laundry_closet": {
            "dimensions_cm": [{"width": 130, "depth": 70}, {"width": 180, "depth": 70}],
            "clearance_cm": {"front": 80, "maintenance": 80},
            "allowed_rooms": ["lavanderia", "ripostiglio tecnico", "bagno grande"],
            "forbidden_rooms": ["camera", "living"],
            "mep_required": ["scarico", "presa dedicata", "ventilazione"],
        },
    },
    "kitchen": {
        "linear_kitchen_base": {
            "dimensions_cm": [{"width": 240, "depth": 60}, {"width": 300, "depth": 60}, {"width": 360, "depth": 60}],
            "clearance_cm": {"working_front": 100, "minimum_front": 95},
            "allowed_rooms": ["cucina", "living con cucina"],
            "forbidden_rooms": ["bagno", "camera", "cabina armadio"],
            "mep_required": ["scarico lavello", "adduzione acqua", "elettrico cucina", "cappa/fumi"],
        },
        "kitchen_peninsula": {
            "dimensions_cm": [{"width": 180, "depth": 90}, {"width": 220, "depth": 95}],
            "clearance_cm": {"working_side": 95, "circulation_side": 90, "stools_side": 110},
            "allowed_rooms": ["cucina", "living con cucina", "open space"],
            "forbidden_rooms": ["bagno", "corridoio"],
            "mep_required": ["eventuale elettrico piano", "passaggi minimi"],
        },
        "kitchen_island": {
            "dimensions_cm": [{"width": 180, "depth": 90}, {"width": 240, "depth": 100}],
            "clearance_cm": {"all_sides_min": 100, "preferred": 110},
            "allowed_rooms": ["open space grande", "cucina grande"],
            "forbidden_rooms": ["bagno", "cucina stretta", "camera"],
            "mep_required": ["elettrico", "eventuale idrico/scarico se lavello"],
        },
        "tall_units": {
            "dimensions_cm": [{"width": 120, "depth": 60}, {"width": 180, "depth": 60}],
            "clearance_cm": {"front": 95},
            "allowed_rooms": ["cucina", "dispensa"],
            "forbidden_rooms": ["bagno"],
        },
        "pantry_wall": {
            "dimensions_cm": [{"width": 180, "depth": 60}, {"width": 240, "depth": 60}],
            "clearance_cm": {"front": 95},
            "allowed_rooms": ["cucina", "dispensa", "living con cucina"],
            "forbidden_rooms": ["bagno", "camera", "cabina armadio"],
            "mep_required": ["presa frigo se integrato", "ventilazione elettrodomestici"],
        },
    },
    "appliances": {
        "refrigerator": {
            "dimensions_cm": [{"width": 60, "depth": 65}, {"width": 90, "depth": 70}],
            "clearance_cm": {"front": 95, "door_swing_side": 5},
            "allowed_rooms": ["cucina", "dispensa"],
            "forbidden_rooms": ["bagno", "camera"],
            "mep_required": ["presa dedicata", "ventilazione"],
        },
        "dishwasher": {
            "dimensions_cm": [{"width": 45, "depth": 60}, {"width": 60, "depth": 60}],
            "clearance_cm": {"front_open_door": 100},
            "allowed_rooms": ["cucina"],
            "forbidden_rooms": ["bagno", "camera"],
            "mep_required": ["scarico", "adduzione acqua", "presa"],
        },
        "washing_machine": {
            "dimensions_cm": [{"width": 60, "depth": 60}, {"width": 60, "depth": 65}],
            "clearance_cm": {"front": 80, "maintenance": 80},
            "allowed_rooms": ["lavanderia", "bagno grande", "ripostiglio tecnico"],
            "forbidden_rooms": ["camera", "living", "balcone non chiuso"],
            "mep_required": ["scarico lavatrice", "adduzione acqua", "presa dedicata"],
        },
        "dryer": {
            "dimensions_cm": [{"width": 60, "depth": 60}, {"width": 60, "depth": 65}],
            "clearance_cm": {"front": 80, "ventilation": 10},
            "allowed_rooms": ["lavanderia", "ripostiglio tecnico", "bagno grande"],
            "forbidden_rooms": ["camera", "living"],
            "mep_required": ["presa dedicata", "ventilazione"],
        },
        "washer_dryer_column": {
            "dimensions_cm": [{"width": 65, "depth": 70}],
            "clearance_cm": {"front": 85, "maintenance": 85},
            "allowed_rooms": ["lavanderia", "ripostiglio tecnico", "bagno grande"],
            "forbidden_rooms": ["camera", "living", "cucina stretta"],
            "mep_required": ["scarico", "adduzione acqua", "presa dedicata", "ventilazione"],
        },
    },
    "bathroom": {
        "wc": {
            "dimensions_cm": [{"width": 40, "depth": 55}],
            "clearance_cm": {"front": 60, "side_service": 20},
            "allowed_rooms": ["bagno", "bagno di servizio"],
            "forbidden_rooms": ["cucina", "living", "camera"],
            "mep_required": ["colonna scarico", "pendenza"],
        },
        "bidet": {
            "dimensions_cm": [{"width": 40, "depth": 55}],
            "clearance_cm": {"front": 60, "side_service": 20},
            "allowed_rooms": ["bagno"],
            "forbidden_rooms": ["cucina", "living"],
            "mep_required": ["scarico", "adduzione acqua"],
        },
        "vanity": {
            "dimensions_cm": [{"width": 60, "depth": 45}, {"width": 90, "depth": 50}, {"width": 120, "depth": 50}],
            "clearance_cm": {"front": 70},
            "allowed_rooms": ["bagno", "bagno di servizio"],
            "forbidden_rooms": ["cucina"],
        },
        "shower": {
            "dimensions_cm": [{"width": 80, "depth": 80}, {"width": 90, "depth": 90}, {"width": 120, "depth": 80}],
            "clearance_cm": {"entry": 60, "front": 70},
            "allowed_rooms": ["bagno", "bagno di servizio"],
            "forbidden_rooms": ["cucina", "camera"],
            "mep_required": ["scarico", "pendenza", "ventilazione"],
        },
        "bathtub": {
            "dimensions_cm": [{"width": 170, "depth": 70}, {"width": 180, "depth": 80}],
            "clearance_cm": {"front": 70},
            "allowed_rooms": ["bagno grande", "suite"],
            "forbidden_rooms": ["bagno di servizio stretto", "cucina"],
            "mep_required": ["scarico", "adduzione acqua"],
        },
    },
    "workspace": {
        "desk_compact": {
            "dimensions_cm": [{"width": 120, "depth": 60}, {"width": 140, "depth": 70}],
            "clearance_cm": {"chair_pullback": 90, "side": 50},
            "allowed_rooms": ["studio", "camera", "living", "ospiti"],
            "forbidden_rooms": ["bagno"],
        },
        "desk_executive": {
            "dimensions_cm": [{"width": 160, "depth": 80}, {"width": 180, "depth": 90}],
            "clearance_cm": {"chair_pullback": 100, "visitor_side": 90},
            "allowed_rooms": ["studio", "camera grande"],
            "forbidden_rooms": ["bagno", "corridoio"],
        },
        "bookcase": {
            "dimensions_cm": [{"width": 120, "depth": 35}, {"width": 240, "depth": 40}],
            "clearance_cm": {"front": 70},
            "allowed_rooms": ["studio", "living", "camera"],
            "forbidden_rooms": ["bagno umido"],
        },
        "guest_sofa_bed": {
            "dimensions_cm": [{"width": 200, "depth": 95, "open_depth": 210}],
            "clearance_cm": {"front_closed": 90, "front_open": 80, "side": 60},
            "allowed_rooms": ["studio ospiti", "camera ospiti", "living"],
            "forbidden_rooms": ["bagno", "corridoio"],
        },
    },
    "balcony": {
        "bistro_table": {
            "dimensions_cm": [{"diameter": 60}, {"diameter": 70}],
            "clearance_cm": {"around": 60, "door_path": 90},
            "allowed_rooms": ["balcone", "terrazzo"],
            "forbidden_rooms": ["living interno", "bagno", "camera"],
            "placement_prerequisite": "balcony_detected",
        },
        "outdoor_storage": {
            "dimensions_cm": [{"width": 80, "depth": 45}, {"width": 120, "depth": 50}],
            "clearance_cm": {"front": 70, "door_path": 90},
            "allowed_rooms": ["balcone", "terrazzo"],
            "forbidden_rooms": ["living interno", "bagno"],
            "placement_prerequisite": "balcony_detected",
        },
    },
}


def furniture_library_payload() -> Dict[str, Any]:
    return {
        "schema": "gb-parametric-furniture-library-v1",
        "unit": "cm",
        "general_clearances_cm": deepcopy(GENERAL_CLEARANCES_CM),
        "categories": deepcopy(PARAMETRIC_FURNITURE_LIBRARY),
        "research_references": deepcopy(RESEARCH_REFERENCES),
        "solver_rules": deepcopy(PARAMETRIC_SOLVER_RULES),
        "coverage": {
            "categories": len(PARAMETRIC_FURNITURE_LIBRARY),
            "items": sum(len(items) for items in PARAMETRIC_FURNITURE_LIBRARY.values()),
            "variant_ready": ["conservative", "premium_suite", "investment", "family", "smart_working"],
        },
        "usage_rules": [
            "dimensioni e clearances sono vincoli di pre-check, non sostituiscono rilievo e progetto esecutivo",
            "un arredo non puo essere posizionato in una stanza presente in forbidden_rooms",
            "cucine, elettrodomestici e penisole non sono ammessi in bagni o locali sanitari",
            "lavanderia e cucina richiedono sempre verifica MEP prima di confermare la variante",
            "se la planimetria non e calibrata metricamente, il solver deve restare in modalita qualitativa",
        ],
    }
