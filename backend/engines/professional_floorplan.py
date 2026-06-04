from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from .schemas import (
    Floorplan2DBrief,
    OptimizationAction,
    ProfessionalFinding,
    ProfessionalFloorplanPackage,
    RenderFidelityContract,
)


DISCLAIMER = "Concept preliminare non esecutivo: da validare con tecnico abilitato e sopralluogo prima di qualsiasi intervento."


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean(value: Any, default: str = "") -> str:
    text = str(value or default).strip()
    return re.sub(r"\s+", " ", text)


def _lower_words(values: Iterable[Any]) -> str:
    return " ".join(_clean(value).lower() for value in values if _clean(value))


def _room_names(analysis: Dict[str, Any]) -> List[str]:
    return [_clean(room.get("name")) for room in analysis.get("detected_rooms") or [] if isinstance(room, dict)]


def _feature_count(analysis: Dict[str, Any], key: str) -> int:
    elements = analysis.get("detected_elements") or {}
    value = elements.get(key) or []
    return len(value) if isinstance(value, list) else 0


def _is_defined(job: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
    selected = job.get("plan_type_selected")
    detected = analysis.get("plan_type_detected") or job.get("plan_type_detected")
    action = analysis.get("recommended_action")
    return selected == "defined_project" or detected == "defined_project" or action == "keep_layout"


def _is_redistribution(job: Dict[str, Any], analysis: Dict[str, Any]) -> bool:
    selected = job.get("plan_type_selected")
    action = analysis.get("recommended_action")
    return selected == "existing_state" or action == "redistribute"


def _confidence(analysis: Dict[str, Any]) -> float:
    return max(0.0, min(1.0, _safe_float(analysis.get("confidence"), 0.0)))


def _finding(
    category: str,
    severity: str,
    title: str,
    evidence: str,
    recommendation: str,
    confidence: float,
    verification_required: bool = True,
) -> ProfessionalFinding:
    return ProfessionalFinding(
        category=category,
        severity=severity,
        title=title,
        evidence=evidence,
        recommendation=recommendation,
        confidence=max(0.0, min(1.0, confidence)),
        verification_required=verification_required,
        disclaimer=DISCLAIMER,
    )


def build_technical_findings(job: Dict[str, Any]) -> List[ProfessionalFinding]:
    analysis = job.get("vision_analysis") or {}
    rooms = analysis.get("detected_rooms") or []
    names = _lower_words(room.get("name") for room in rooms if isinstance(room, dict))
    priorities = _lower_words(job.get("priorities") or [])
    findings: List[ProfessionalFinding] = []
    confidence = _confidence(analysis)

    uncertain_rooms = [
        room for room in rooms
        if isinstance(room, dict) and (room.get("verification_required") or _safe_float(room.get("confidence"), 0) < 0.72)
    ]
    if analysis.get("measurement_notes"):
        findings.append(
            _finding(
                "measurement",
                "medium",
                "Scala e quote da confermare",
                _clean(analysis.get("measurement_notes")),
                "Usare le superfici come stima preliminare e confermare misure, spessori murari e quote in sopralluogo prima di preventivo esecutivo.",
                max(confidence, 0.55),
            )
        )

    if uncertain_rooms:
        sample = ", ".join(_clean(room.get("name"), "ambiente") for room in uncertain_rooms[:4])
        findings.append(
            _finding(
                "layout",
                "medium",
                "Ambienti con lettura da verificare",
                f"Ambienti marcati con verifica richiesta: {sample}.",
                "La proposta 2D deve mantenere perimetro e relazioni visibili, evitando spostamenti radicali sugli ambienti meno leggibili.",
                0.68,
            )
        )

    if _feature_count(analysis, "windows") == 0:
        findings.append(
            _finding(
                "light",
                "high",
                "Aperture esterne non lette con sicurezza",
                "La vision non ha restituito finestre/aperture esterne affidabili.",
                "Non proporre camere o zona giorno in posizioni prive di aperture confermate; verificare rapporti aeroilluminanti e affacci reali.",
                0.62,
            )
        )
    elif any(word in priorities for word in ["luce", "open space", "spazio"]):
        findings.append(
            _finding(
                "light",
                "medium",
                "Priorita luce naturale",
                "Il brief cliente valorizza luce, open space o ampliamento percepito.",
                "Orientare la zona giorno verso le aperture piu leggibili e ridurre filtri/corridoi non necessari, senza alterare finestre o facciata.",
                0.74,
            )
        )

    if "corridoio" in names or _feature_count(analysis, "corridors") > 0:
        findings.append(
            _finding(
                "circulation",
                "medium",
                "Distribuzione di passaggio da ottimizzare",
                "Sono presenti corridoi o disimpegni riconosciuti dalla planimetria.",
                "Ridurre superfici di solo passaggio e trasferire metri utili a zona giorno, contenimento o lavanderia, mantenendo porte e accessi coerenti.",
                0.72,
            )
        )

    has_bath = "bagno" in names or _feature_count(analysis, "bathrooms") > 0
    has_kitchen = "cucina" in names or _feature_count(analysis, "kitchen_zones") > 0
    if has_bath or has_kitchen:
        findings.append(
            _finding(
                "plumbing",
                "high" if has_bath and has_kitchen else "medium",
                "Nuclei impiantistici da preservare",
                "Bagno e/o cucina risultano rilevati come zone tecniche.",
                "Mantenere bagni e cucina vicino alle posizioni impiantistiche visibili; eventuali spostamenti richiedono verifica pendenze scarichi, colonne e canne fumarie.",
                0.78,
            )
        )

    if _feature_count(analysis, "structural_constraints_uncertain") > 0:
        findings.append(
            _finding(
                "structure",
                "high",
                "Vincoli strutturali non certi",
                "La planimetria contiene elementi potenzialmente strutturali o non verificabili.",
                "La proposta deve trattare muri portanti, pilastri e cavedi come invarianti finche non viene fatta verifica tecnica.",
                0.76,
            )
        )

    if not findings:
        findings.append(
            _finding(
                "other",
                "low",
                "Analisi preliminare senza criticita forti",
                "La planimetria non evidenzia criticita automatiche ad alta priorita.",
                "Procedere con una proposta conservativa e validare misure, impianti e vincoli prima di trasformarla in progetto esecutivo.",
                max(confidence, 0.65),
            )
        )
    return findings[:8]


def build_optimization_strategy(job: Dict[str, Any]) -> List[OptimizationAction]:
    analysis = job.get("vision_analysis") or {}
    priorities = _lower_words(job.get("priorities") or [])
    defined = _is_defined(job, analysis)
    actions: List[OptimizationAction] = []

    if defined:
        return [
            OptimizationAction(
                priority=1,
                title="Pulizia professionale della planimetria caricata",
                rationale="Il file e trattato come progetto definito: la priorita e renderlo leggibile senza reinterpretare la distribuzione.",
                constraints=["perimetro invariato", "muri e aperture mantenuti", "ambienti non rinominati se incerti"],
                expected_effect="Output 2D piu chiaro per review, preventivo e render fedeli.",
                risk_note="Qualsiasi modifica distributiva va richiesta come nuova variante, non applicata automaticamente.",
            ),
            OptimizationAction(
                priority=2,
                title="Normalizzazione grafica e legenda tecnica",
                rationale="Etichette, legenda e note permettono allo staff di capire cosa e certo e cosa va verificato.",
                constraints=["quote solo indicative", "nessuna certificazione esecutiva"],
                expected_effect="Meno ambiguita in fase commerciale e sopralluogo.",
                risk_note="La pulizia grafica non sostituisce elaborati CAD esecutivi.",
            ),
        ]

    actions.append(
        OptimizationAction(
            priority=1,
            title="Preservare involucro, aperture e nuclei tecnici",
            rationale="La redistribuzione e credibile solo se non altera elementi non verificabili da una planimetria preliminare.",
            constraints=["perimetro invariato", "finestre mantenute", "bagni/cucina vicino agli impianti visibili", "muri portanti trattati come non demolibili"],
            expected_effect="Concept realistico e difendibile in sopralluogo.",
            risk_note="Servono verifica strutturale e impiantistica prima di demolizioni o spostamenti.",
        )
    )
    if any(word in priorities for word in ["open space", "luce", "spazio", "cucina"]):
        actions.append(
            OptimizationAction(
                priority=2,
                title="Ampliare la zona giorno dove supportato dalle aperture",
                rationale="Open space e luce richiedono una zona giorno piu continua, ma vincolata agli affacci reali.",
                constraints=["non aggiungere finestre", "non spostare cucina lontano da scarichi/fumi", "mantenere accessi principali"],
                expected_effect="Maggiore valore percepito, profondita visiva e fruibilita quotidiana.",
                risk_note="Verificare rapporti aeroilluminanti, tramezzi demolibili e posizione canna fumaria.",
            )
        )
    actions.append(
        OptimizationAction(
            priority=3,
            title="Separare flussi giorno/notte e ridurre passaggi inutili",
            rationale="Una buona redistribuzione residenziale riduce metri persi e protegge privacy delle camere.",
            constraints=["corridoi minimi ma funzionali", "porte interne e disimpegni coerenti", "bagno non direttamente aperto su cucina"],
            expected_effect="Layout piu ordinato, commerciale e utilizzabile.",
            risk_note="Dimensioni minime e normativa locale vanno validate con rilievo.",
        )
    )
    if "bagno" in priorities or "lavanderia" in priorities or "contenimento" in priorities:
        actions.append(
            OptimizationAction(
                priority=4,
                title="Integrare funzioni tecniche leggere",
                rationale="Bagno aggiuntivo, lavanderia o contenimento aumentano valore solo se non forzano impianti e passaggi.",
                constraints=["adiacenza a scarichi", "areazione/ventilazione", "accessi non conflittuali"],
                expected_effect="Maggiore funzionalita senza compromettere la fattibilita preliminare.",
                risk_note="Non confermare nuovi bagni senza rilievo impiantistico.",
            )
        )
    return actions[:5]


def _floorplan_mode(job: Dict[str, Any]) -> str:
    analysis = job.get("vision_analysis") or {}
    if _is_defined(job, analysis):
        return "clean_defined_project"
    if _is_redistribution(job, analysis):
        return "optimized_existing_state"
    return "verification_only"


def build_floorplan_2d_brief(job: Dict[str, Any], actions: List[OptimizationAction]) -> Floorplan2DBrief:
    mode = _floorplan_mode(job)
    if mode == "clean_defined_project":
        title = "Planimetria 2D professionale - progetto definito"
        intent = "Pulire e rendere leggibile la planimetria caricata senza modificare distribuzione, muri, aperture o funzioni."
        changes = ["Nessuna redistribuzione automatica", "Etichette e note tecniche rese piu leggibili", "Incertezze evidenziate per review staff"]
    elif mode == "optimized_existing_state":
        title = "Proposta 2D preliminare - spazi ottimizzati"
        intent = "Generare una redistribuzione conservativa e realistica dello stato di fatto, vincolata agli elementi visibili."
        changes = [action.title for action in actions[:4]]
    else:
        title = "Planimetria 2D preliminare - verifica richiesta"
        intent = "Produrre una base leggibile senza redistribuzioni automatiche finche la classificazione non viene confermata."
        changes = ["Confermare se il file rappresenta stato di fatto o progetto", "Non generare render inventati prima della conferma"]
    return Floorplan2DBrief(
        mode=mode,
        title=title,
        drawing_intent=intent,
        constraints_respected=[
            "Perimetro esterno invariato",
            "Accessi e aperture visibili mantenuti",
            "Balconi, terrazzi, logge e volumi esterni non aggiunti se non presenti nel file",
            "Bagni, cucina, cavedi e scarichi trattati come vincoli finche non verificati",
            "Arredi e moduli cucina mai inseriti in bagni, bagni di servizio o locali tecnici",
            "Muri portanti o elementi non chiari non demoliti automaticamente",
            "Nessun muro dichiarato portante senza prova documentale o verifica tecnica",
        ],
        drafting_requirements=[
            "Stile tavola architettonica pulito, linee nere, muri spessi e campiture sobrie",
            "Etichette stanze leggibili e non sovrapposte",
            "Legenda con invarianti, interventi proposti e punti da verificare",
            "Quote solo indicative se la scala non e certa",
            "Nessun logo, watermark o elemento decorativo non tecnico",
        ],
        legend_items=["muri esistenti", "aperture mantenute", "interventi proposti", "punti da verificare"],
        change_summary=changes,
        approval_checklist=[
            "Perimetro coerente con il file caricato",
            "Finestre e accessi non inventati",
            "Balconi/terrazzi assenti se non rilevati nel file originale",
            "Bagni/cucina coerenti con nuclei impiantistici",
            "Nessun arredo cucina dentro bagni o bagni di servizio",
            "Muri portanti indicati solo come verifica richiesta, non come certezza",
            "Nessuna stanza nuova non supportata dall'analisi",
            "Note di verifica presenti per elementi incerti",
        ],
        disclaimer=DISCLAIMER,
    )


def build_render_contract(job: Dict[str, Any], mode: str) -> RenderFidelityContract:
    clean_mode = mode == "clean_defined_project"
    return RenderFidelityContract(
        reference_required=True,
        reference_type="clean_2d_plan" if clean_mode else "optimized_2d_plan",
        must_preserve=[
            "perimetro e proporzioni relative della planimetria 2D approvata",
            "posizione relativa di muri, porte, finestre, bagni, cucina e accessi",
            "numero e relazione degli ambienti rappresentati nella 2D",
            "vincoli tecnici indicati come non modificabili",
        ],
        must_not_add=[
            "stanze, bagni, finestre, porte, scale, balconi o livelli non presenti nella 2D",
            "balconi, terrazzi, logge o estensioni esterne non presenti nella planimetria originale",
            "cucine, penisole, elettrodomestici o mobili cucina dentro bagni e bagni di servizio",
            "etichette di muro portante o strutturale quando il dato e solo incerto",
            "spostamenti creativi di muri o aperture",
            "arredi che bloccano passaggi o contraddicono la distribuzione",
            "testi, quote, loghi, watermark o viste fantasy",
        ],
        allowed_views=["zenithal_top_down", "soggiorno_3_4", "cucina_3_4", "camera_3_4"],
        negative_prompt=(
            "no extra rooms, no invented windows, no invented doors, no second floor, no balcony unless present, "
            "no invented terrace, no kitchen furniture in bathrooms, no unverified load-bearing wall label, "
            "no structural fantasy, no text, no watermark, no logo, no impossible plumbing relocation"
        ),
        fidelity_notes=[
            "Generare prima top-down/zenithal e usare quello come controllo coerenza.",
            "Le viste interne devono restare compatibili con la 2D approvata.",
            "Se un elemento e incerto, rappresentarlo in modo neutro e non definitivo.",
        ],
    )


def build_professional_floorplan_package(job: Dict[str, Any]) -> Dict[str, Any]:
    analysis = job.get("vision_analysis") or {}
    confidence = _confidence(analysis)
    plan_type = analysis.get("plan_type_detected") or job.get("plan_type_detected") or "unclear"
    findings = build_technical_findings(job)
    actions = build_optimization_strategy(job)
    floorplan = build_floorplan_2d_brief(job, actions)
    render_contract = build_render_contract(job, floorplan.mode)
    rooms = _room_names(analysis)
    unverifiable = [
        finding.title
        for finding in findings
        if finding.verification_required and finding.severity in {"medium", "high"}
    ]
    package = ProfessionalFloorplanPackage(
        mode=floorplan.mode,
        plan_type=plan_type,
        confidence=confidence,
        summary=_summary(plan_type, floorplan.mode, rooms, findings),
        technical_findings=findings,
        optimization_strategy=actions,
        floorplan_2d=floorplan,
        render_contract=render_contract,
        unverifiable_elements=unverifiable[:8],
        quality={
            "rooms_count": len(rooms),
            "windows_count": _feature_count(analysis, "windows"),
            "doors_count": _feature_count(analysis, "doors"),
            "bathrooms_count": _feature_count(analysis, "bathrooms"),
            "kitchen_zones_count": _feature_count(analysis, "kitchen_zones"),
            "render_reference_required": True,
            "professional_readiness": round((confidence * 0.65) + (min(len(rooms), 6) / 6 * 0.35), 3),
        },
    )
    return package.model_dump(mode="json", by_alias=True)


def _summary(plan_type: str, mode: str, rooms: List[str], findings: List[ProfessionalFinding]) -> str:
    room_text = ", ".join(rooms[:6]) if rooms else "ambienti da verificare"
    high = [finding.title for finding in findings if finding.severity == "high"]
    if mode == "clean_defined_project":
        base = "La planimetria viene trattata come progetto definito: il layout resta bloccato e viene reso piu leggibile."
    elif mode == "optimized_existing_state":
        base = "La planimetria viene trattata come stato di fatto: la proposta 2D ottimizza gli spazi con approccio conservativo."
    else:
        base = "La classificazione richiede conferma: la generazione resta conservativa e non inventa redistribuzioni."
    critical = f" Priorita tecniche: {', '.join(high[:3])}." if high else ""
    return f"{base} Ambienti letti: {room_text}.{critical}"


def professional_2d_prompt_addendum(package: Optional[Dict[str, Any]]) -> str:
    if not package:
        return ""
    floorplan = package.get("floorplan_2d") or {}
    actions = package.get("optimization_strategy") or []
    constraints = floorplan.get("constraints_respected") or []
    drafting = floorplan.get("drafting_requirements") or []
    action_lines = [
        f"{item.get('title')}: {item.get('rationale')}"
        for item in actions[:5]
        if isinstance(item, dict)
    ]
    return (
        " PROFESSIONAL_2D_BRIEF: "
        f"mode={floorplan.get('mode')}; intent={floorplan.get('drawing_intent')}; "
        f"constraints={constraints}; drafting_requirements={drafting}; "
        f"optimization_strategy={action_lines}; approval_checklist={floorplan.get('approval_checklist') or []}. "
        "Draw a sober professional architectural 2D plan, not an illustration. Include only technical labels, "
        "a compact legend and clear uncertain/verifica notes."
    )


def render_prompt_addendum(package: Optional[Dict[str, Any]]) -> str:
    if not package:
        return ""
    contract = package.get("render_contract") or {}
    return (
        " RENDER_FIDELITY_CONTRACT: use the approved 2D plan as a hard reference. "
        f"Must preserve: {contract.get('must_preserve') or []}. "
        f"Must not add: {contract.get('must_not_add') or []}. "
        f"Negative prompt: {contract.get('negative_prompt') or ''}. "
        "If the reference is ambiguous, keep uncertain elements neutral instead of inventing them. "
    )


def professional_advice_text(package: Optional[Dict[str, Any]], *, style: str, goal: str, priorities: str) -> str:
    if not package:
        return ""
    findings = package.get("technical_findings") or []
    actions = package.get("optimization_strategy") or []
    finding_text = " ".join(
        f"{item.get('title')}: {item.get('recommendation')}"
        for item in findings[:4]
        if isinstance(item, dict)
    )
    action_text = " ".join(
        f"{item.get('title')}: {item.get('expected_effect')}"
        for item in actions[:4]
        if isinstance(item, dict)
    )
    return (
        f"Sintesi tecnica: {package.get('summary')} Obiettivo: {goal}. Priorita cliente: {priorities}. "
        f"Strategia 2D: {action_text} Criticita e verifiche: {finding_text} "
        f"Stile render/materiali: {style}, da applicare solo dopo approvazione della planimetria 2D. {DISCLAIMER}"
    )
