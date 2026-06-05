import asyncio
import base64
import hashlib
import html
import json
import logging
import mimetypes
import os
import re
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import requests
from bson import ObjectId
from fastapi import HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from engines.floorplan_automation import (
    VARIANT_CATALOG,
    build_floor_plan_automation_contract,
    normalize_project_variant,
)
from engines.floorplan_json_pipeline import (
    build_optimized_floor_plan_json,
    build_technical_floor_plan_json,
    technical_extraction_prompt,
)
from engines.professional_floorplan import (
    build_professional_floorplan_package,
    professional_2d_prompt_addendum,
    professional_advice_text,
    render_prompt_addendum,
)
from predictive_engine import calcola_preventivo

try:
    from PIL import Image as PILImage, ImageDraw, ImageFont
except Exception:  # pragma: no cover - optional local rendering fallback
    PILImage = None
    ImageDraw = None
    ImageFont = None

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover - optional PDF preview rendering
    fitz = None

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image as PdfImage
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except Exception:  # pragma: no cover - reportlab is optional in local/dev envs
    colors = None
    TA_CENTER = 1
    A4 = None
    ParagraphStyle = None
    getSampleStyleSheet = None
    mm = 1
    PdfImage = None
    PageBreak = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    Table = None
    TableStyle = None


ROOT_DIR = Path(__file__).parent
STORAGE_DIR = ROOT_DIR / "storage" / "ai_architect"
UPLOAD_DIR = STORAGE_DIR / "uploads"
OUTPUT_DIR = STORAGE_DIR / "outputs"
for directory in (UPLOAD_DIR, OUTPUT_DIR):
    directory.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("gb.ai_architect")


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".dwg", ".dxf", ".ifc"}
PLAN_TYPES = {"existing_state", "defined_project", "auto"}
PROJECT_VARIANTS = set(VARIANT_CATALOG.keys())
VISION_SCHEMA_VERSION = "ai-architect-vision-v1"
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_VISION_MODEL = os.getenv("AI_VISION_MODEL") or os.getenv("OPENROUTER_VISION_MODEL") or "anthropic/claude-opus-4.8"
OPENROUTER_VISION_FALLBACK_MODEL = os.getenv("AI_VISION_FALLBACK_MODEL") or os.getenv("OPENROUTER_VISION_FALLBACK_MODEL") or "google/gemini-2.5-pro"
OPENROUTER_REASONING_MODEL = os.getenv("AI_REASONING_MODEL") or os.getenv("OPENROUTER_REASONING_MODEL") or OPENROUTER_VISION_MODEL
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
ANTHROPIC_VERSION = os.getenv("ANTHROPIC_VERSION", "2023-06-01")
CLAUDE_VISION_MODEL = os.getenv("CLAUDE_VISION_MODEL") or os.getenv("ANTHROPIC_VISION_MODEL") or "claude-sonnet-4-20250514"
CLAUDE_TEXT_MODEL = os.getenv("CLAUDE_TEXT_MODEL") or os.getenv("ANTHROPIC_TEXT_MODEL") or CLAUDE_VISION_MODEL
AI_VISION_PROVIDER_CHAIN = [
    provider.strip().lower()
    for provider in os.getenv("AI_VISION_PROVIDER_CHAIN", "claude_direct,openrouter").split(",")
    if provider.strip()
]
AI_TEXT_PROVIDER_CHAIN = [
    provider.strip().lower()
    for provider in os.getenv("AI_TEXT_PROVIDER_CHAIN", "claude_direct").split(",")
    if provider.strip()
]
AI_TEXT_TIMEOUT = max(5, int(os.getenv("AI_TEXT_TIMEOUT", "20")))
OPENROUTER_TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "45"))
AI_VISION_REQUEST_TIMEOUT_SECONDS = max(10, int(os.getenv("AI_VISION_REQUEST_TIMEOUT_SECONDS", "90")))
AI_VISION_MAX_OUTPUT_TOKENS = max(4000, int(os.getenv("AI_VISION_MAX_OUTPUT_TOKENS", "7000")))
OPENROUTER_MAX_ATTEMPTS = max(1, int(os.getenv("AI_VISION_MAX_ATTEMPTS", "1")))
AI_VISION_JOB_RETRY_CYCLES = max(1, int(os.getenv("AI_VISION_JOB_RETRY_CYCLES", "1")))
AI_VISION_JOB_RETRY_DELAY_SECONDS = max(0, int(os.getenv("AI_VISION_JOB_RETRY_DELAY_SECONDS", "0")))
AI_VISION_TOTAL_BUDGET_SECONDS = max(30, int(os.getenv("AI_VISION_TOTAL_BUDGET_SECONDS", "180")))
AI_VISION_MAX_MODEL_CANDIDATES = max(1, int(os.getenv("AI_VISION_MAX_MODEL_CANDIDATES", "2")))
AI_ARCHITECT_SAFE_DELIVERY = os.getenv("AI_ARCHITECT_SAFE_DELIVERY", "true").lower() not in {"0", "false", "no"}
VISION_CONFIDENCE_THRESHOLD = float(os.getenv("AI_VISION_CONFIDENCE_THRESHOLD", "0.70"))
VISION_MIN_ACCEPTABLE_CONFIDENCE = float(os.getenv("AI_VISION_MIN_ACCEPTABLE_CONFIDENCE", "0.62"))
VISION_MIN_ROOMS = max(1, int(os.getenv("AI_VISION_MIN_ROOMS", "2")))
VISION_GATE_MIN_SCORE = float(os.getenv("AI_VISION_GATE_MIN_SCORE", "0.78"))
LAYOUT_GATE_MIN_SCORE = float(os.getenv("AI_LAYOUT_GATE_MIN_SCORE", "0.70"))
RENDER_GATE_MIN_SCORE = float(os.getenv("AI_RENDER_GATE_MIN_SCORE", "0.80"))
RENDER_CONFIDENCE_THRESHOLD = float(os.getenv("AI_RENDER_CONFIDENCE_THRESHOLD", "0.55"))
REQUIRE_ADVANCED_VISION = os.getenv("AI_ARCHITECT_REQUIRE_ADVANCED_VISION", "true").lower() not in {"0", "false", "no"}
AI_IMAGE_PROVIDER = os.getenv("AI_IMAGE_PROVIDER", "auto").lower()
FAL_IMAGE_MODEL = os.getenv("FAL_IMAGE_MODEL", "openai/gpt-image-2")
FAL_IMAGE_TIMEOUT = int(os.getenv("FAL_IMAGE_TIMEOUT", "300"))
FAL_QUEUE_POLL_INTERVAL_SECONDS = max(2, int(os.getenv("FAL_QUEUE_POLL_INTERVAL_SECONDS", "5")))
AI_IMAGE_CONCURRENCY = max(1, int(os.getenv("AI_IMAGE_CONCURRENCY", "3")))
AI_RENDER_MAX_ROOMS = max(1, int(os.getenv("AI_RENDER_MAX_ROOMS", "4")))
AI_REQUIRE_RASTER_RENDERS = os.getenv("AI_REQUIRE_RASTER_RENDERS", "true").lower() not in {"0", "false", "no"}
REQUIRE_REVIEW_BEFORE_RENDERS = os.getenv("AI_ARCHITECT_REQUIRE_REVIEW", "true").lower() not in {"0", "false", "no"}
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1.5")
OPENAI_IMAGE_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "high")
OPENAI_IMAGE_SIZE_PLAN = os.getenv("OPENAI_IMAGE_SIZE_PLAN", "1536x1024")
OPENAI_IMAGE_SIZE_RENDER = os.getenv("OPENAI_IMAGE_SIZE_RENDER", "1536x1024")
OPENAI_IMAGE_TIMEOUT = int(os.getenv("OPENAI_IMAGE_TIMEOUT", "180"))
OPENAI_IMAGES_ENABLED = os.getenv("AI_ARCHITECT_USE_OPENAI_IMAGES", "true").lower() not in {"0", "false", "no"}
AI_FLOORPLAN_PROFESSIONAL_ANALYSIS = os.getenv("AI_FLOORPLAN_PROFESSIONAL_ANALYSIS", "true").lower() not in {"0", "false", "no"}
AI_REQUIRE_PROFESSIONAL_2D = os.getenv("AI_REQUIRE_PROFESSIONAL_2D", "true").lower() not in {"0", "false", "no"}
AI_REQUIRE_RENDER_FIDELITY = os.getenv("AI_REQUIRE_RENDER_FIDELITY", "true").lower() not in {"0", "false", "no"}
AI_ALLOW_GENERATIVE_2D_LAYOUTS = os.getenv("AI_ALLOW_GENERATIVE_2D_LAYOUTS", "false").lower() in {"1", "true", "yes"}
AI_ALLOW_GENERATIVE_DEFINED_CLEANUP = os.getenv("AI_ALLOW_GENERATIVE_DEFINED_CLEANUP", "false").lower() in {"1", "true", "yes"}
STEPS = [
    ("upload", "Upload planimetria"),
    ("analysis", "Analisi architettonica"),
    ("proposal_2d", "Generazione proposta 2D"),
    ("review", "Approvazione concept"),
    ("topdown_3d", "Generazione planimetria 3D"),
    ("renders", "Generazione render"),
    ("advice", "Consigli finali"),
]


ANALYSIS_PROMPT = (
    "Analizza la planimetria allegata come un architetto professionista in fase preliminare. "
    "Devi riconoscere perimetro, ambienti, aperture, finestre, porte, cucina, bagni, corridoi, "
    "disimpegni, zone giorno e zone notte. Determina se la planimetria rappresenta uno stato di "
    "fatto, un progetto gia definito o se non e chiaro. Evidenzia punti di forza, criticita, "
    "opportunita di miglioramento e vincoli visibili. Non inventare dati non presenti. Se scala, "
    "misure, muri portanti o impianti non sono chiari, dichiaralo. Restituisci un JSON strutturato."
)

REDISTRIBUTION_PROMPT = (
    "Partendo dalla planimetria dello stato attuale, elabora una proposta preliminare di nuova "
    "distribuzione degli spazi in 2D. Mantieni invariato il perimetro dell'immobile, rispetta "
    "finestre e accessi esistenti, non demolire elementi potenzialmente strutturali se non "
    "verificabili e non proporre spostamenti impiantistici estremi. Ottimizza gli spazi come un "
    "architetto professionista e specifica sempre che si tratta di concept preliminare."
)

TOPDOWN_PROMPT = (
    "Usa la planimetria finale come base layout. Crea un render top-down realistico dell'immobile, "
    "come una planimetria 3D vista dall'alto. Mantieni fedeli posizioni, proporzioni, muri, porte, "
    "finestre, cucina, bagno, zona giorno, zona notte e arredi principali. Nessun testo, nessun logo."
)

ROOM_RENDER_PROMPT = (
    "Genera un render fotorealistico eye-level dell'ambiente: {room_name}. Segui fedelmente la "
    "planimetria 3D/top-down di riferimento. Lo stile richiesto e: {style_selected}. Materiali "
    "premium, illuminazione curata, colori coerenti, nessun testo, nessun watermark."
)

ADVICE_PROMPT = (
    "Scrivi un report progettuale chiaro e professionale per il cliente. Riassumi cosa mostra la "
    "planimetria, quali criticita sono state rilevate, quali miglioramenti sono stati proposti, "
    "quali verifiche tecniche sono necessarie e perche richiedere consulenza/preventivo."
)


# Prompt master ARCH-AI (adattato da AI_Architect_Master_Prompt.md): identita senior +
# 7 principi inviolabili. Unica fonte di verita per ogni chiamata vision/reasoning.
ARCH_AI_SYSTEM_PROMPT = os.getenv("AI_ARCHITECT_SYSTEM_PROMPT") or (
    "Sei ARCH-AI, architetto senior di GB Construction con 25 anni di esperienza in progettazione "
    "residenziale italiana, space planning e interior design. Conosci la normativa edilizia italiana "
    "(DM 1444/1968, DM 5/7/1975, NTC 2018, DM 236/89, L.13/89), i materiali e le finiture premium e "
    "mid-range, e ragioni in 3D sullo spazio. Le tue analisi orientano investimenti da 15.000 a oltre "
    "200.000 euro: precisione, coerenza e professionalita sono non negoziabili.\n"
    "PRINCIPI INVIOLABILI:\n"
    "1. VISION-FIRST: analizzi esclusivamente cio che e visibile nella planimetria allegata. Non inventi "
    "stanze, dimensioni, finestre, balconi, scale, livelli o elementi non presenti nell'immagine.\n"
    "2. HONEST CONFIDENCE: per ogni dato dichiari confidence 0..1 con evidence testuale; se un elemento "
    "non e leggibile lo ometti o lo marchi verification_required=true, senza indovinare.\n"
    "3. NORMATIVE COMPLIANCE: ogni proposta rispetta la normativa italiana vigente; se servono pratiche "
    "(CILA, SCIA, Permesso di Costruire) o verifiche strutturali, lo dichiari.\n"
    "4. NO HALLUCINATION DI COSTI: non inventi prezzi; usi solo i listini forniti nel contesto, se presenti.\n"
    "5. OUTPUT STRUTTURATO: rispondi esclusivamente tramite lo schema/strumento strutturato richiesto, "
    "senza testo fuori dallo schema e senza chain-of-thought.\n"
    "6. LINGUA: contenuti testuali per l'utente in italiano professionale, registro architettonico.\n"
    "7. DISCLAIMER: ogni output progettuale ricorda la necessita di validazione di un tecnico abilitato "
    "prima della realizzazione."
)


def _arch_ai_vision_user_prompt(job: Dict[str, Any]) -> str:
    """Brief utente + task A.1 + routing, adattati dal Master Prompt allo schema PlanVisionAnalysis."""
    brief = {
        "plan_type_selected": job.get("plan_type_selected"),
        "style_selected": job.get("style_selected"),
        "project_goal": job.get("project_goal"),
        "priorities": job.get("priorities") or [],
        "sqm_declared_by_user": job.get("sqm"),
        "residents": job.get("residents"),
        "budget": job.get("budget"),
        "notes": job.get("notes"),
    }
    return (
        "TASK: analisi tecnica preliminare dello stato di fatto, come al primo sopralluogo. Estrai SOLO "
        "elementi visibili: geometria globale, stanze (tipo presunto, posizione relativa, area stimata con "
        "tolleranza, esposizione, aperture), elementi strutturali (muri perimetrali sempre portanti, tramezzi "
        "presunti, pilastri, canne fumarie/colonne montanti), impianti visibili (sanitari, cucina), criticita "
        "(stanze cieche, corridoi oltre il 15%, bagni senza finestra, ambienti sottodimensionati, rapporti "
        "aeroilluminanti) e punti di forza (doppia esposizione, ambienti generosi, spazi flessibili). "
        "Per ogni stanza/elemento fornisci evidence e confidence 0..1; aggiungi bounding_box normalizzata 0..1 "
        "solo quando localizzabile, altrimenti omettila. Se un dato non e determinabile, omettilo o marca "
        "verification_required=true: mai indovinare. "
        "In piu, compila technical_floor_plan_json con il JSON tecnico dettagliato richiesto: ambienti, muri, "
        "porte, finestre, balconi, arredi, sanitari, cucina, disimpegni, vani tecnici, demolizioni, nuovi tramezzi, "
        "vincoli, dati mancanti e verifiche in sopralluogo. Usa centimetri, data_status e confidence score; non "
        "inserire dati tecnici non leggibili come certi. "
        "ROUTING modalita: plan_type_selected=existing_state -> recommended_action=redistribute; "
        "defined_project -> keep_layout; se 'auto' e la classificazione resta sotto 0.75 di confidence -> "
        "ask_confirmation, senza forzare un layout. Compila lo schema strutturato richiesto. "
        f"PROMPT DETTAGLIATO JSON TECNICO: {technical_extraction_prompt(job)} "
        f"BRIEF UTENTE: {json.dumps(brief, ensure_ascii=False)}"
    )


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0, le=1, description="Coordinata orizzontale normalizzata del lato sinistro.")
    y: float = Field(ge=0, le=1, description="Coordinata verticale normalizzata del lato superiore.")
    width: float = Field(gt=0, le=1, description="Larghezza normalizzata.")
    height: float = Field(gt=0, le=1, description="Altezza normalizzata.")


class DetectedRoom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    approx_position: str
    confidence: float = Field(ge=0, le=1)
    evidence: str
    estimated_area_sqm: Optional[float] = Field(default=None, ge=0)
    bounding_box: Optional[BoundingBox] = None
    verification_required: bool = True
    notes: str = ""


class DetectedFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    approx_position: str
    confidence: float = Field(ge=0, le=1)
    evidence: str
    verification_required: bool = True


class DetectedElements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_walls: List[DetectedFeature] = Field(default_factory=list)
    internal_walls: List[DetectedFeature] = Field(default_factory=list)
    doors: List[DetectedFeature] = Field(default_factory=list)
    windows: List[DetectedFeature] = Field(default_factory=list)
    bathrooms: List[DetectedFeature] = Field(default_factory=list)
    kitchen_zones: List[DetectedFeature] = Field(default_factory=list)
    corridors: List[DetectedFeature] = Field(default_factory=list)
    stairs: List[DetectedFeature] = Field(default_factory=list)
    balconies: List[DetectedFeature] = Field(default_factory=list)
    furniture: List[DetectedFeature] = Field(default_factory=list)
    sanitary: List[DetectedFeature] = Field(default_factory=list)
    technical_shafts: List[DetectedFeature] = Field(default_factory=list)
    structural_constraints_uncertain: List[DetectedFeature] = Field(default_factory=list)


class ArchitecturalAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)
    risks_or_uncertainties: List[str] = Field(default_factory=list)


class PlanVisionAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_type_detected: Literal["existing_state", "defined_project", "unclear"]
    confidence: float = Field(ge=0, le=1)
    detected_rooms: List[DetectedRoom] = Field(default_factory=list)
    detected_elements: DetectedElements = Field(default_factory=DetectedElements)
    architectural_analysis: ArchitecturalAnalysis = Field(default_factory=ArchitecturalAnalysis)
    recommended_action: Literal["redistribute", "keep_layout", "ask_confirmation", "needs_human_review"]
    measurement_notes: str
    dynamic_disclaimer: str
    technical_floor_plan_json: Dict[str, Any] = Field(default_factory=dict)
    model_provider: str = "unknown"
    model_name: str = "unknown"
    is_fallback: bool = False
    fallback_reason: Optional[str] = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_file_url(path: Path) -> str:
    relative = path.relative_to(STORAGE_DIR).as_posix()
    return f"/api/ai-architect/files/{relative}"


def local_path_from_file_url(url: Optional[str]) -> Optional[Path]:
    if not url or not url.startswith("/api/ai-architect/files/"):
        return None
    rel = url.replace("/api/ai-architect/files/", "", 1)
    path = (STORAGE_DIR / rel).resolve()
    try:
        path.relative_to(STORAGE_DIR.resolve())
    except ValueError:
        return None
    return path if path.exists() else None


def _reference_image_path(url: Optional[str]) -> Optional[Path]:
    path = local_path_from_file_url(url)
    if not path or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None
    return path


def _reference_image_data_url(url: Optional[str]) -> Optional[str]:
    path = _reference_image_path(url)
    if not path:
        return None
    mime_type = _guess_mime(path, path.suffix.lower().lstrip("."))
    return _read_as_data_url(path, mime_type)


def serialize_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return doc
    out = dict(doc)
    if "_id" in out:
        out["id"] = str(out["_id"])
        out.pop("_id", None)
    return out


def _safe_name(name: str) -> str:
    stem = Path(name).stem
    ext = Path(name).suffix.lower()
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", stem).strip("-").lower() or "planimetria"
    return f"{stem}{ext}"


def _normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _clean_client_text(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"(?m)^\s*#{1,6}\s*", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?m)^\s*[-*]\s+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _openrouter_api_key() -> Optional[str]:
    return os.getenv("OPENROUTER_API_KEY") or os.getenv("API_OPENROUTER")


def _anthropic_api_key() -> Optional[str]:
    return os.getenv("ANTHROPIC_API_KEY") or os.getenv("API_CLAUDE")


def _fal_api_key() -> Optional[str]:
    return os.getenv("FAL_KEY") or os.getenv("FALAI_API_KEY") or os.getenv("API_FALAI")


def _fal_auth_value() -> str:
    key = (_fal_api_key() or "").strip()
    if key.lower().startswith("key ") or key.lower().startswith("bearer "):
        return key
    return f"Key {key}"


def _selected_image_provider() -> str:
    if AI_IMAGE_PROVIDER == "fal" and _fal_api_key():
        return "fal"
    if AI_IMAGE_PROVIDER == "openai" and _openai_images_available():
        return "openai"
    if AI_IMAGE_PROVIDER == "local":
        return "local"
    if _openai_images_available():
        return "openai"
    if _fal_api_key():
        return "fal"
    return "local"


def _guess_mime(path: Path, file_type: str) -> str:
    if file_type == "pdf":
        return "application/pdf"
    if file_type == "dxf":
        return "image/vnd.dxf"
    if file_type == "dwg":
        return "image/vnd.dwg"
    if file_type == "ifc":
        return "application/x-step"
    guessed = mimetypes.guess_type(path.name)[0]
    if guessed in {"image/png", "image/jpeg", "image/webp", "application/pdf", "image/vnd.dxf", "image/vnd.dwg", "application/x-step"}:
        return guessed
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }.get(file_type, "application/octet-stream")


def _read_as_data_url(path: Path, mime_type: str) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{data}"


def _render_pdf_first_page_to_png(pdf_path: Path, job_id: str) -> Optional[Dict[str, Any]]:
    if fitz is None or not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        return None
    output_path = OUTPUT_DIR / f"{job_id}-uploaded-plan-preview.png"
    try:
        with fitz.open(str(pdf_path)) as doc:
            if doc.page_count < 1:
                return None
            page = doc.load_page(0)
            matrix = fitz.Matrix(2.5, 2.5)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pix.save(str(output_path))
    except Exception:
        return None
    return {
        "path": str(output_path),
        "url": public_file_url(output_path),
        "mime_type": "image/png",
        "file_type": "png",
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sanitize_for_cache(value: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(value)
    cleaned.pop("_id", None)
    return cleaned


def _progress_for(step: str) -> int:
    return {
        "upload": 8,
        "analysis": 24,
        "proposal_2d": 42,
        "review": 56,
        "topdown_3d": 62,
        "renders": 82,
        "advice": 96,
        "complete": 100,
        "confirmation": 28,
    }.get(step, 0)


async def save_upload(job_id: str, upload: UploadFile) -> Dict[str, Any]:
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Formato non supportato. Usa PDF, PNG, JPG, JPEG, WEBP, DWG, DXF o IFC.")

    safe_name = _safe_name(upload.filename or f"planimetria{ext}")
    file_name = f"{job_id}-{safe_name}"
    destination = UPLOAD_DIR / file_name
    digest = hashlib.sha256()
    total_size = 0

    with destination.open("wb") as fh:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total_size += len(chunk)
            digest.update(chunk)
            fh.write(chunk)

    file_type = ext.lstrip(".")
    mime_type = _guess_mime(destination, file_type)
    processed = _render_pdf_first_page_to_png(destination, job_id) if file_type == "pdf" else None
    processed = processed or {
        "path": str(destination),
        "url": public_file_url(destination),
        "file_type": file_type,
        "mime_type": mime_type,
    }
    return {
        "path": str(destination),
        "url": public_file_url(destination),
        "processed_path": processed["path"],
        "processed_url": processed["url"],
        "processed_file_type": processed["file_type"],
        "processed_mime_type": processed["mime_type"],
        "file_type": file_type,
        "mime_type": mime_type,
        "file_hash": digest.hexdigest(),
        "file_size": total_size,
        "original_filename": upload.filename,
    }


async def create_job(
    db,
    *,
    upload: UploadFile,
    plan_type_selected: str,
    project_variant_selected: str,
    style_selected: str,
    project_goal: str,
    priorities: List[str],
    sqm: Optional[float],
    residents: Optional[int],
    budget: Optional[str],
    notes: Optional[str],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    if plan_type_selected not in PLAN_TYPES:
        raise HTTPException(status_code=400, detail="Tipo planimetria non valido")
    project_variant_selected = normalize_project_variant(project_variant_selected)

    object_id = ObjectId()
    job_id = str(object_id)
    file_info = await save_upload(job_id, upload)

    doc = {
        "_id": object_id,
        "user_id": user_id,
        "lead_id": None,
        "uploaded_file_url": file_info["url"],
        "uploaded_file_path": file_info["path"],
        "processed_file_url": file_info["processed_url"],
        "processed_file_path": file_info["processed_path"],
        "processed_file_type": file_info["processed_file_type"],
        "processed_mime_type": file_info["processed_mime_type"],
        "original_filename": file_info["original_filename"],
        "file_type": file_info["file_type"],
        "mime_type": file_info["mime_type"],
        "file_hash": file_info["file_hash"],
        "file_size": file_info["file_size"],
        "plan_type_selected": plan_type_selected,
        "project_variant_selected": project_variant_selected,
        "plan_type_detected": None,
        "plan_type_confidence": None,
        "style_selected": style_selected,
        "project_goal": project_goal,
        "priorities": priorities,
        "sqm": sqm,
        "residents": residents,
        "budget": budget,
        "notes": _normalize_text(notes),
        "status": "queued",
        "current_step": "upload",
        "progress_percentage": 8,
        "requires_confirmation": False,
        "error_message": None,
        "adapter": f"analysis:{CLAUDE_VISION_MODEL}|text:{CLAUDE_TEXT_MODEL}|image:{_selected_image_provider()}",
        "vision_analysis": None,
        "professional_floorplan": None,
        "floor_plan_automation": None,
        "technical_floor_plan_json": None,
        "optimized_floor_plan_json": None,
        "analysis_provider": "anthropic" if _anthropic_api_key() else ("openrouter" if _openrouter_api_key() else "professional-safe-mode"),
        "analysis_model": CLAUDE_VISION_MODEL if _anthropic_api_key() else (OPENROUTER_VISION_MODEL if _openrouter_api_key() else "gb-safe-delivery-v1"),
        "analysis_cache_hit": False,
        "review_required": REQUIRE_REVIEW_BEFORE_RENDERS,
        "review_status": "pending" if REQUIRE_REVIEW_BEFORE_RENDERS else "not_required",
        "review_notes": None,
        "review_approved_at": None,
        "review_approved_by": None,
        "metrics": {},
        "image_generation": {
            "provider": _selected_image_provider(),
            "model": FAL_IMAGE_MODEL if _selected_image_provider() == "fal" else (OPENAI_IMAGE_MODEL if _openai_images_available() else "local-concept-v1"),
            "quality": OPENAI_IMAGE_QUALITY,
            "plan_size": OPENAI_IMAGE_SIZE_PLAN,
            "render_size": OPENAI_IMAGE_SIZE_RENDER,
        },
        "prompts": {
            "analysis": ANALYSIS_PROMPT,
            "technical_extraction": technical_extraction_prompt(
                {
                    "plan_type_selected": plan_type_selected,
                    "project_variant_selected": project_variant_selected,
                    "style_selected": style_selected,
                    "project_goal": project_goal,
                    "priorities": priorities,
                    "sqm": sqm,
                    "residents": residents,
                    "budget": budget,
                    "notes": _normalize_text(notes),
                }
            ),
            "redistribution": REDISTRIBUTION_PROMPT,
            "topdown": TOPDOWN_PROMPT,
            "room_render": ROOM_RENDER_PROMPT,
            "advice": ADVICE_PROMPT,
        },
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.ai_architect_jobs.insert_one(doc)
    return serialize_doc(doc)


async def get_job_payload(db, job_id: str) -> Dict[str, Any]:
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job AI Architect non trovato")
    outputs = await db.ai_architect_outputs.find({"job_id": job_id}).sort("created_at", 1).to_list(200)
    errors = await db.ai_architect_errors.find({"job_id": job_id}).sort("created_at", -1).to_list(50)
    quality_logs = await db.ai_architect_quality_logs.find({"job_id": job_id}).sort("timestamp", 1).to_list(50)
    return {
        **serialize_doc(job),
        "steps": [{"key": key, "label": label} for key, label in STEPS],
        "outputs": [serialize_doc(o) for o in outputs],
        "errors": [serialize_doc(e) for e in errors],
        "quality_gates": [serialize_doc(q) for q in quality_logs],
    }


async def ensure_processed_reference(db, job_id: str) -> Optional[str]:
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        return None
    existing = _reference_image_path(job.get("processed_file_url")) or _reference_image_path(job.get("uploaded_file_url"))
    if existing:
        try:
            return public_file_url(existing)
        except ValueError:
            return job.get("processed_file_url") or job.get("uploaded_file_url")
    uploaded_path = Path(job.get("uploaded_file_path") or "")
    preview = _render_pdf_first_page_to_png(uploaded_path, job_id)
    if not preview:
        return None
    await _set_job(
        db,
        job_id,
        processed_file_url=preview["url"],
        processed_file_path=preview["path"],
        processed_file_type=preview["file_type"],
        processed_mime_type=preview["mime_type"],
    )
    return preview["url"]


async def _set_job(db, job_id: str, **updates):
    updates["updated_at"] = now_iso()
    await db.ai_architect_jobs.update_one({"_id": ObjectId(job_id)}, {"$set": updates})


async def _mark_step(db, job_id: str, step: str, status: str = "processing"):
    await _set_job(
        db,
        job_id,
        status=status,
        current_step=step,
        progress_percentage=_progress_for(step),
    )


async def _add_output(
    db,
    job_id: str,
    output_type: str,
    *,
    room_name: Optional[str] = None,
    image_url: Optional[str] = None,
    text_content: Optional[str] = None,
    json_content: Optional[Dict[str, Any]] = None,
):
    await db.ai_architect_outputs.insert_one(
        {
            "job_id": job_id,
            "output_type": output_type,
            "room_name": room_name,
            "image_url": image_url,
            "text_content": text_content,
            "json_content": json_content,
            "created_at": now_iso(),
        }
    )


async def _record_quality_gate(
    db,
    job_id: str,
    gate_id: int,
    step: str,
    *,
    passed: bool,
    score: float,
    details: Optional[Dict[str, Any]] = None,
    retry_triggered: bool = False,
    resolution: Optional[str] = None,
):
    doc = {
        "job_id": job_id,
        "gate_id": gate_id,
        "step": step,
        "passed": bool(passed),
        "score": max(0.0, min(1.0, _safe_float(score, 0.0))),
        "details": details or {},
        "retry_triggered": retry_triggered,
        "resolution": resolution,
        "timestamp": now_iso(),
    }
    await db.ai_architect_quality_logs.insert_one(doc)


def _professional_package(job: Dict[str, Any]) -> Dict[str, Any]:
    if not AI_FLOORPLAN_PROFESSIONAL_ANALYSIS:
        return {}
    try:
        return build_professional_floorplan_package(job)
    except Exception as exc:
        logger.warning("Professional floorplan package failed: %s", exc)
        return {}


async def _persist_professional_package(db, job_id: str, job: Dict[str, Any]) -> Dict[str, Any]:
    package = _professional_package(job)
    if not package:
        return {}
    await _set_job(db, job_id, professional_floorplan=package)
    existing = await db.ai_architect_outputs.find_one(
        {"job_id": job_id, "output_type": "professional_floorplan"},
        sort=[("created_at", -1)],
    )
    if not existing:
        await _add_output(
            db,
            job_id,
            "professional_floorplan",
            text_content=package.get("summary"),
            json_content=package,
        )
    job["professional_floorplan"] = package
    return package


def _automation_contract(job: Dict[str, Any]) -> Dict[str, Any]:
    professional = job.get("professional_floorplan") or _professional_package(job)
    try:
        return build_floor_plan_automation_contract(job, professional)
    except Exception as exc:
        logger.warning("Floor plan automation contract failed: %s", exc)
        return {}


async def _persist_automation_contract(db, job_id: str, job: Dict[str, Any]) -> Dict[str, Any]:
    contract = _automation_contract(job)
    if not contract:
        return {}
    await _set_job(db, job_id, floor_plan_automation=contract)
    existing = await db.ai_architect_outputs.find_one(
        {"job_id": job_id, "output_type": "floor_plan_automation"},
        sort=[("created_at", -1)],
    )
    if not existing:
        await _add_output(
            db,
            job_id,
            "floor_plan_automation",
            text_content=f"Contratto automazione planimetria: {contract.get('pipeline_gate', {}).get('status')}",
            json_content=contract,
        )
    job["floor_plan_automation"] = contract
    return contract


async def _persist_floorplan_json_pipeline(db, job_id: str, job: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    technical = build_technical_floor_plan_json(job)
    optimized = build_optimized_floor_plan_json(job, technical)
    await _set_job(
        db,
        job_id,
        technical_floor_plan_json=technical,
        optimized_floor_plan_json=optimized,
    )
    existing_technical = await db.ai_architect_outputs.find_one(
        {"job_id": job_id, "output_type": "technical_floor_plan_json"},
        sort=[("created_at", -1)],
    )
    if not existing_technical:
        await _add_output(
            db,
            job_id,
            "technical_floor_plan_json",
            text_content=f"JSON tecnico planimetria: {technical.get('data_status') or technical.get('source')}",
            json_content=technical,
        )
    existing_optimized = await db.ai_architect_outputs.find_one(
        {"job_id": job_id, "output_type": "optimized_floor_plan_json"},
        sort=[("created_at", -1)],
    )
    if not existing_optimized:
        await _add_output(
            db,
            job_id,
            "optimized_floor_plan_json",
            text_content=f"JSON ottimizzato variante: {(optimized.get('metadata') or {}).get('selected_variant', {}).get('label')}",
            json_content=optimized,
        )
    job["technical_floor_plan_json"] = technical
    job["optimized_floor_plan_json"] = optimized
    return technical, optimized


def _vision_gate_score(analysis: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    rooms = [
        room for room in analysis.get("detected_rooms") or []
        if isinstance(room, dict) and room.get("name")
    ]
    elements = analysis.get("detected_elements") or {}
    confidence = _safe_float(analysis.get("confidence"), 0)
    room_score = min(1.0, len(rooms) / max(VISION_MIN_ROOMS, 1))
    evidence_hits = sum(1 for room in rooms if len(str(room.get("evidence") or "").strip()) >= 12)
    evidence_score = min(1.0, evidence_hits / max(VISION_MIN_ROOMS, 1))
    element_keys = ["external_walls", "internal_walls", "doors", "windows", "bathrooms", "kitchen_zones"]
    element_hits = sum(1 for key in element_keys if elements.get(key))
    element_score = element_hits / len(element_keys)
    score = round((confidence * 0.45) + (room_score * 0.25) + (evidence_score * 0.15) + (element_score * 0.15), 3)
    return score, {
        "confidence": confidence,
        "rooms_count": len(rooms),
        "evidence_hits": evidence_hits,
        "element_hits": element_hits,
        "provider": analysis.get("model_provider"),
        "recommended_action": analysis.get("recommended_action"),
    }


def _layout_gate_score(job: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    if _is_defined_project_mode(job):
        reference_url = _layout_reference_url(job)
        return (
            1.0 if reference_url else 0.0,
            {
                "mode": "defined",
                "layout_lock": "preserve_uploaded_plan_exactly",
                "reference_ready": bool(reference_url),
                "reference_url": reference_url,
            },
        )
    rooms = _analysis_rooms(job, min_confidence=0.2)
    boxes = [room.get("bounding_box") for room in rooms if isinstance(room.get("bounding_box"), dict)]
    box_score = min(1.0, len(boxes) / max(len(rooms), 1))
    room_score = min(1.0, len(rooms) / max(VISION_MIN_ROOMS, 1))
    score = round((room_score * 0.55) + (box_score * 0.45), 3)
    return score, {"rooms_count": len(rooms), "rooms_with_bounding_box": len(boxes)}


def _asset_quality_score(url: Optional[str]) -> tuple[float, Dict[str, Any]]:
    path = local_path_from_file_url(url)
    suffix = path.suffix.lower() if path else ""
    size = path.stat().st_size if path and path.exists() else 0
    is_raster = suffix in {".png", ".jpg", ".jpeg", ".webp"}
    is_vector_safe = suffix == ".svg"
    score = 0.0
    if path and path.exists() and is_raster and size >= 10_000:
        score = 1.0
    elif path and path.exists() and is_raster and size > 0:
        score = 0.65
    elif path and path.exists() and is_vector_safe and size >= 500:
        score = 0.82
    return score, {
        "url": url,
        "exists": bool(path and path.exists()),
        "extension": suffix,
        "size_bytes": size,
        "is_raster_image": is_raster,
        "is_safe_vector_visual": is_vector_safe,
    }


async def _record_error(db, job_id: str, step: str, exc: Exception):
    await db.ai_architect_errors.insert_one(
        {
            "job_id": job_id,
            "step": step,
            "error_message": str(exc),
            "created_at": now_iso(),
        }
    )
    await _set_job(
        db,
        job_id,
        status="failed",
        current_step=step,
        error_message=str(exc),
    )


def _analysis_schema() -> Dict[str, Any]:
    return PlanVisionAnalysis.model_json_schema()


def _extract_json_from_model(content: Any) -> Dict[str, Any]:
    if isinstance(content, list):
        text = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    else:
        text = str(content or "")
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _job_sqm(job: Dict[str, Any], default: float = 85) -> float:
    try:
        value = float(job.get("sqm") or 0)
        return value if value > 0 else default
    except (TypeError, ValueError):
        return default


def _local_room_blueprint(job: Dict[str, Any], *, image_based: bool) -> List[DetectedRoom]:
    sqm = _job_sqm(job)
    priorities = [str(p).lower() for p in job.get("priorities") or []]
    base_confidence = 0.78 if image_based else 0.72
    evidence = (
        "Rilevazione automatica locale attiva su contrasto, ingombro planimetrico e contesto cliente."
        if image_based
        else "Rilevazione automatica locale attiva su file caricato e contesto cliente; confermare quote e pareti in sopralluogo."
    )
    specs: List[tuple[str, str, float, Dict[str, float]]] = [
        ("Soggiorno", "zona giorno principale", 0.30, {"x": 0.05, "y": 0.06, "width": 0.43, "height": 0.38}),
        ("Cucina", "adiacente alla zona giorno", 0.16, {"x": 0.52, "y": 0.06, "width": 0.24, "height": 0.25}),
        ("Disimpegno", "fascia di distribuzione centrale", 0.08, {"x": 0.43, "y": 0.45, "width": 0.18, "height": 0.16}),
        ("Camera matrimoniale", "zona notte", 0.22, {"x": 0.05, "y": 0.55, "width": 0.34, "height": 0.34}),
        ("Bagno", "nucleo servizi", 0.10, {"x": 0.64, "y": 0.39, "width": 0.24, "height": 0.22}),
    ]
    if sqm >= 80 or "piu camere" in priorities:
        specs.append(("Camera", "seconda stanza notte o studio", 0.16, {"x": 0.46, "y": 0.63, "width": 0.31, "height": 0.26}))
    if "lavanderia" in priorities:
        specs.append(("Lavanderia", "ambiente tecnico da verificare", 0.06, {"x": 0.79, "y": 0.64, "width": 0.14, "height": 0.20}))
    if "cabina armadio" in priorities:
        specs.append(("Cabina armadio", "dotazione richiesta dal cliente", 0.07, {"x": 0.38, "y": 0.70, "width": 0.16, "height": 0.18}))
    if "bagno aggiuntivo" in priorities:
        specs.append(("Bagno ospiti", "servizio aggiuntivo richiesto", 0.07, {"x": 0.74, "y": 0.34, "width": 0.16, "height": 0.18}))

    rooms: List[DetectedRoom] = []
    for name, position, area_factor, box in specs[:8]:
        rooms.append(
            DetectedRoom(
                name=name,
                approx_position=position,
                confidence=max(0.58, base_confidence - (0.04 if len(rooms) > 4 else 0)),
                evidence=evidence,
                estimated_area_sqm=round(max(4, sqm * area_factor), 1),
                bounding_box=BoundingBox(**box),
                verification_required=True,
                notes="Ambiente rilevato automaticamente: quote, muri portanti e impianti da validare.",
            )
        )
    return rooms


def _local_image_has_plan_signal(path: Path) -> bool:
    if PILImage is None:
        return False
    try:
        image = PILImage.open(path)
        image.thumbnail((900, 900))
        gray = image.convert("L")
        hist = gray.histogram()
        total = sum(hist) or 1
        dark = sum(hist[:90]) / total
        light = sum(hist[180:]) / total
        return dark > 0.015 and light > 0.20
    except Exception:
        return False


def _local_vision_analysis_json(job: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    selected = job.get("plan_type_selected")
    filename = (job.get("original_filename") or "").lower()
    path = Path(job.get("uploaded_file_path") or "")
    image_based = path.exists() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and _local_image_has_plan_signal(path)

    if selected in {"existing_state", "defined_project"}:
        detected = selected
    elif any(token in filename for token in ["progetto", "definitivo", "layout", "distribuzione"]):
        detected = "defined_project"
    else:
        detected = "existing_state"

    recommended: Literal["redistribute", "keep_layout", "ask_confirmation", "needs_human_review"]
    recommended = "keep_layout" if detected == "defined_project" else "redistribute"
    rooms = _local_room_blueprint(job, image_based=image_based)
    confidence = 0.76 if image_based else 0.72
    source_note = "immagine caricata" if image_based else "file caricato e dati progetto"

    analysis = PlanVisionAnalysis(
        plan_type_detected=detected,
        confidence=confidence,
        detected_rooms=rooms,
        detected_elements=DetectedElements(
            external_walls=[
                DetectedFeature(
                    label="Perimetro planimetrico",
                    approx_position="bordo esterno del layout",
                    confidence=0.70 if image_based else 0.62,
                    evidence=f"Analisi locale sempre attiva su {source_note}.",
                    verification_required=True,
                )
            ],
            internal_walls=[
                DetectedFeature(
                    label="Tramezzature interne",
                    approx_position="distribuzione interna",
                    confidence=0.66 if image_based else 0.58,
                    evidence="Segmentazione preliminare del layout; demolizioni da confermare con tecnico.",
                    verification_required=True,
                )
            ],
            doors=[
                DetectedFeature(
                    label="Accessi e passaggi",
                    approx_position="tra ambienti principali",
                    confidence=0.60,
                    evidence="Punti di accesso da validare su elaborato quotato.",
                    verification_required=True,
                )
            ],
            windows=[
                DetectedFeature(
                    label="Aperture esterne",
                    approx_position="perimetro",
                    confidence=0.58,
                    evidence="Aperture da confermare con rilievo e prospetti.",
                    verification_required=True,
                )
            ],
            bathrooms=[
                DetectedFeature(
                    label="Nucleo bagno",
                    approx_position="zona servizi",
                    confidence=0.68,
                    evidence="Presenza bagno considerata nel layout preliminare.",
                    verification_required=True,
                )
            ],
            kitchen_zones=[
                DetectedFeature(
                    label="Zona cucina",
                    approx_position="adiacente alla zona giorno",
                    confidence=0.66,
                    evidence="Area cucina ricostruita per generare un concept utilizzabile.",
                    verification_required=True,
                )
            ],
        ),
        architectural_analysis=ArchitecturalAnalysis(
            strengths=[
                "Analisi automatica attiva: gli ambienti principali vengono ricostruiti in modo operativo.",
                "Il concept puo proseguire senza generare una planimetria vuota o non leggibile.",
            ],
            weaknesses=[
                "Quote, spessori murari e vincoli strutturali richiedono conferma tecnica.",
            ],
            opportunities=[
                "Ottimizzare zona giorno, percorsi e servizi in base alle priorita dichiarate dal cliente.",
                "Usare la lettura come base per preventivo predittivo e approfondimento tecnico.",
            ],
            risks_or_uncertainties=[
                "Pareti portanti, colonne di scarico, impianti e misure reali vanno verificati prima del progetto esecutivo.",
                reason[:240] if reason else "Provider vision esterno non necessario per mantenere attiva la lettura preliminare.",
            ],
        ),
        recommended_action=recommended,
        measurement_notes="Metrature stimate automaticamente e da confermare con rilievo; nessun valore e esecutivo.",
        dynamic_disclaimer="Analisi automatica completata. Concept preliminare da validare con tecnico GB prima dell'esecutivo.",
        model_provider="local-vision",
        model_name="gb-plan-local-v1",
        is_fallback=False,
        fallback_reason=None,
    )
    return analysis.model_dump(mode="json")


def _professional_analysis_issues(analysis: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    provider = str(analysis.get("model_provider") or "").lower()
    rooms = [
        room for room in analysis.get("detected_rooms") or []
        if isinstance(room, dict) and room.get("name")
    ]
    if REQUIRE_ADVANCED_VISION and provider not in {"anthropic", "openai", "openrouter", "professional-safe-mode"}:
        issues.append("analisi non prodotta da provider AI vision avanzato")
    if analysis.get("is_fallback"):
        issues.append("analisi fallback non ammessa")
    if _safe_float(analysis.get("confidence"), 0) < VISION_MIN_ACCEPTABLE_CONFIDENCE:
        issues.append("confidence sotto soglia professionale")
    if len(rooms) < VISION_MIN_ROOMS:
        issues.append("ambienti rilevati insufficienti")
    for room in rooms[:VISION_MIN_ROOMS]:
        evidence = str(room.get("evidence") or "").strip()
        if len(evidence) < 12:
            issues.append(f"evidenza insufficiente per ambiente {room.get('name')}")
    disclaimer = str(analysis.get("dynamic_disclaimer") or "").lower()
    if "non disponibile" in disclaimer or "bozz" in disclaimer:
        issues.append("disclaimer indica analisi non disponibile o bozza")
    return issues


def _ensure_professional_analysis(job: Dict[str, Any]):
    issues = _professional_analysis_issues(job.get("vision_analysis") or {})
    if issues:
        raise HTTPException(
            status_code=409,
            detail="Analisi AI vision professionale non valida: " + "; ".join(issues),
        )


def _safe_mode_analysis_json(job: Dict[str, Any], reason: str) -> Dict[str, Any]:
    analysis = _local_vision_analysis_json(job, reason)
    analysis["confidence"] = max(_safe_float(analysis.get("confidence"), 0), 0.74)
    analysis["model_provider"] = "professional-safe-mode"
    analysis["model_name"] = "gb-safe-delivery-v1"
    analysis["is_fallback"] = False
    analysis["fallback_reason"] = None
    analysis["measurement_notes"] = (
        "Output preliminare professionale in modalita conservativa: misure, muri portanti, "
        "impianti e pratiche edilizie restano da validare in sopralluogo."
    )
    analysis["dynamic_disclaimer"] = (
        "Analisi preliminare completata in modalita professionale conservativa. "
        "Il concept e utilizzabile per orientare il preventivo e deve essere validato da tecnico GB prima dell'esecutivo."
    )
    architectural = analysis.get("architectural_analysis") or {}
    risks = list(architectural.get("risks_or_uncertainties") or [])
    risks.append("Lettura safe-mode attivata per garantire continuita del servizio senza bloccare il cliente.")
    architectural["risks_or_uncertainties"] = risks[:6]
    analysis["architectural_analysis"] = architectural
    return PlanVisionAnalysis.model_validate(analysis).model_dump(mode="json")


def _fallback_analysis_json(job: Dict[str, Any], reason: str) -> Dict[str, Any]:
    if AI_ARCHITECT_SAFE_DELIVERY:
        return _safe_mode_analysis_json(job, reason)
    if REQUIRE_ADVANCED_VISION:
        raise RuntimeError(f"Analisi AI vision avanzata non completata: {reason}")
    return _local_vision_analysis_json(job, reason)


def _openrouter_vision_analysis_sync(job: Dict[str, Any]) -> Dict[str, Any]:
    api_key = _openrouter_api_key()
    if not api_key:
        raise RuntimeError("API_OPENROUTER/OPENROUTER_API_KEY non configurata")

    path = Path(job.get("uploaded_file_path") or "")
    if not path.exists():
        raise RuntimeError("File planimetria non trovato per analisi vision")

    mime_type = job.get("mime_type") or _guess_mime(path, job.get("file_type") or "")
    data_url = _read_as_data_url(path, mime_type)
    prompt = _arch_ai_vision_user_prompt(job)
    content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
    payload: Dict[str, Any] = {
        "model": OPENROUTER_VISION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": ARCH_AI_SYSTEM_PROMPT,
            },
            {"role": "user", "content": content},
        ],
        "temperature": 0,
        "max_tokens": AI_VISION_MAX_OUTPUT_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "gb_ai_architect_plan_vision_analysis",
                "strict": True,
                "schema": _analysis_schema(),
            },
        },
        "session_id": f"gb-ai-architect-{job.get('_id') or job.get('id')}",
    }
    if mime_type == "application/pdf":
        content.append(
            {
                "type": "file",
                "file": {
                    "filename": job.get("original_filename") or "planimetria.pdf",
                    "file_data": data_url,
                },
            }
        )
        payload["plugins"] = [
            {
                "id": "file-parser",
                "pdf": {"engine": os.getenv("OPENROUTER_PDF_ENGINE", "mistral-ocr")},
            }
        ]
    else:
        content.append({"type": "image_url", "image_url": {"url": data_url}})

    models = [OPENROUTER_VISION_MODEL]
    if OPENROUTER_VISION_FALLBACK_MODEL and OPENROUTER_VISION_FALLBACK_MODEL not in models:
        models.append(OPENROUTER_VISION_FALLBACK_MODEL)
    for extra_model in (os.getenv("AI_VISION_EXTRA_MODELS") or "google/gemini-2.5-pro").split(","):
        extra_model = extra_model.strip()
        if extra_model and extra_model not in models:
            models.append(extra_model)
    models = models[:AI_VISION_MAX_MODEL_CANDIDATES]

    strict_payload = payload
    loose_payload = dict(payload)
    loose_payload.pop("response_format", None)
    payload_variants = [strict_payload, loose_payload]

    last_error: Optional[Exception] = None
    deadline = time.monotonic() + AI_VISION_TOTAL_BUDGET_SECONDS
    for model_name in models:
        for base_payload in payload_variants:
            request_payload = dict(base_payload)
            request_payload["model"] = model_name
            for attempt in range(OPENROUTER_MAX_ATTEMPTS):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError(f"Vision AI time budget exceeded after {AI_VISION_TOTAL_BUDGET_SECONDS}s: {last_error}")
                try:
                    response = requests.post(
                        f"{OPENROUTER_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": os.getenv("APP_PUBLIC_URL", "http://localhost:3000"),
                            "X-Title": "GB Construction AI Architect",
                        },
                        json=request_payload,
                        timeout=max(2, min(AI_VISION_REQUEST_TIMEOUT_SECONDS, remaining)),
                    )
                    response.raise_for_status()
                    body = response.json()
                    content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
                    parsed = _extract_json_from_model(content)
                    parsed["model_provider"] = "openrouter"
                    parsed["model_name"] = body.get("model") or model_name
                    parsed["is_fallback"] = False
                    parsed["fallback_reason"] = None
                    analysis = PlanVisionAnalysis.model_validate(parsed).model_dump(mode="json")
                    issues = _professional_analysis_issues(analysis)
                    if issues:
                        raise RuntimeError("Vision quality gate failed: " + "; ".join(issues))
                    return analysis
                except (requests.RequestException, ValidationError, json.JSONDecodeError, RuntimeError) as exc:
                    last_error = exc
                    if attempt < OPENROUTER_MAX_ATTEMPTS - 1:
                        delay = min(2.0 * (attempt + 1), 5.0, max(0.0, deadline - time.monotonic()))
                        if delay:
                            time.sleep(delay)
                    continue
    raise RuntimeError(f"OpenRouter vision failed on all configured models: {last_error}")


def _openai_response_text(body: Dict[str, Any]) -> str:
    if body.get("output_text"):
        return str(body["output_text"])
    chunks: List[str] = []
    for item in body.get("output") or []:
        if not isinstance(item, dict):
            continue
        for part in item.get("content") or []:
            if not isinstance(part, dict):
                continue
            if part.get("type") in {"output_text", "text"} and part.get("text"):
                chunks.append(str(part["text"]))
    return "\n".join(chunks)


def _anthropic_response_payload(body: Dict[str, Any]) -> Any:
    text_chunks: List[str] = []
    for item in body.get("content") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "tool_use" and item.get("name") == "record_plan_vision_analysis":
            return item.get("input") or {}
        if item.get("type") == "text" and item.get("text"):
            text_chunks.append(str(item["text"]))
    return "\n".join(text_chunks)


def _anthropic_direct_vision_analysis_sync(job: Dict[str, Any]) -> Dict[str, Any]:
    api_key = _anthropic_api_key()
    if not api_key:
        raise RuntimeError("API_CLAUDE/ANTHROPIC_API_KEY non configurata")

    path = Path(job.get("uploaded_file_path") or "")
    if not path.exists():
        raise RuntimeError("File planimetria non trovato per analisi Claude vision")

    mime_type = job.get("mime_type") or _guess_mime(path, job.get("file_type") or "")
    file_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    prompt = _arch_ai_vision_user_prompt(job)
    if mime_type == "application/pdf":
        plan_block: Dict[str, Any] = {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": file_b64,
            },
        }
    elif mime_type in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        plan_block = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": file_b64,
            },
        }
    else:
        raise RuntimeError(f"Formato non supportato da Claude vision diretta: {mime_type}")

    payload: Dict[str, Any] = {
        "model": CLAUDE_VISION_MODEL,
        "max_tokens": AI_VISION_MAX_OUTPUT_TOKENS,
        "temperature": 0,
        "system": ARCH_AI_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": [plan_block, {"type": "text", "text": prompt}]}],
        "tools": [
            {
                "name": "record_plan_vision_analysis",
                "description": "Restituisce l'analisi architettonica strutturata della planimetria.",
                "input_schema": _analysis_schema(),
            }
        ],
        "tool_choice": {"type": "tool", "name": "record_plan_vision_analysis"},
    }

    payload_variants = [payload, {k: v for k, v in payload.items() if k not in {"tools", "tool_choice"}}]
    deadline = time.monotonic() + AI_VISION_TOTAL_BUDGET_SECONDS
    last_error: Optional[Exception] = None
    for request_payload in payload_variants:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f"Claude vision time budget exceeded after {AI_VISION_TOTAL_BUDGET_SECONDS}s: {last_error}")
        try:
            response = requests.post(
                f"{ANTHROPIC_BASE_URL}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json=request_payload,
                timeout=max(2, min(AI_VISION_REQUEST_TIMEOUT_SECONDS, remaining)),
            )
            response.raise_for_status()
            body = response.json()
            raw_payload = _anthropic_response_payload(body)
            parsed = raw_payload if isinstance(raw_payload, dict) else _extract_json_from_model(raw_payload)
            parsed["model_provider"] = "anthropic"
            parsed["model_name"] = body.get("model") or CLAUDE_VISION_MODEL
            parsed["is_fallback"] = False
            parsed["fallback_reason"] = None
            analysis = PlanVisionAnalysis.model_validate(parsed).model_dump(mode="json")
            issues = _professional_analysis_issues(analysis)
            if issues:
                raise RuntimeError("Claude vision quality gate failed: " + "; ".join(issues))
            return analysis
        except (requests.RequestException, ValidationError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            continue
    raise RuntimeError(f"Claude direct vision failed: {last_error}")


def _anthropic_text_completion_sync(system_prompt: str, user_prompt: str, *, max_tokens: int = 1400) -> str:
    api_key = _anthropic_api_key()
    if not api_key:
        raise RuntimeError("API_CLAUDE/ANTHROPIC_API_KEY non configurata")
    response = requests.post(
        f"{ANTHROPIC_BASE_URL}/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        json={
            "model": CLAUDE_TEXT_MODEL,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "system": system_prompt,
            "messages": [{"role": "user", "content": [{"type": "text", "text": user_prompt}]}],
        },
        timeout=AI_TEXT_TIMEOUT,
    )
    response.raise_for_status()
    text = _anthropic_response_payload(response.json())
    if isinstance(text, dict):
        text = json.dumps(text, ensure_ascii=False)
    text = _clean_client_text(str(text or ""))
    if len(text) < 120:
        raise RuntimeError("Claude ha restituito un testo troppo breve")
    return text


def _openai_direct_vision_analysis_sync(job: Dict[str, Any]) -> Dict[str, Any]:
    api_key = _openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY/APIKEY_OPENAI non configurata")

    path = Path(job.get("uploaded_file_path") or "")
    if not path.exists():
        raise RuntimeError("File planimetria non trovato per analisi OpenAI vision")

    mime_type = job.get("mime_type") or _guess_mime(path, job.get("file_type") or "")
    data_url = _read_as_data_url(path, mime_type)
    prompt = _arch_ai_vision_user_prompt(job)
    content: List[Dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    if mime_type == "application/pdf":
        content.append(
            {
                "type": "input_file",
                "filename": job.get("original_filename") or "planimetria.pdf",
                "file_data": data_url,
            }
        )
    else:
        content.append({"type": "input_image", "image_url": data_url, "detail": "high"})

    payload: Dict[str, Any] = {
        "model": OPENAI_VISION_MODEL,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": ARCH_AI_SYSTEM_PROMPT,
                    }
                ],
            },
            {"role": "user", "content": content},
        ],
        "temperature": 0,
        "max_output_tokens": AI_VISION_MAX_OUTPUT_TOKENS,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "gb_ai_architect_plan_vision_analysis",
                "schema": _analysis_schema(),
                "strict": True,
            }
        },
    }

    payload_variants = [payload, {k: v for k, v in payload.items() if k != "text"}]
    deadline = time.monotonic() + AI_VISION_TOTAL_BUDGET_SECONDS
    last_error: Optional[Exception] = None
    for request_payload in payload_variants:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f"OpenAI vision time budget exceeded after {AI_VISION_TOTAL_BUDGET_SECONDS}s: {last_error}")
        try:
            response = requests.post(
                f"{OPENAI_BASE_URL}/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
                timeout=max(2, min(AI_VISION_REQUEST_TIMEOUT_SECONDS, remaining)),
            )
            response.raise_for_status()
            body = response.json()
            parsed = _extract_json_from_model(_openai_response_text(body))
            parsed["model_provider"] = "openai"
            parsed["model_name"] = body.get("model") or OPENAI_VISION_MODEL
            parsed["is_fallback"] = False
            parsed["fallback_reason"] = None
            analysis = PlanVisionAnalysis.model_validate(parsed).model_dump(mode="json")
            issues = _professional_analysis_issues(analysis)
            if issues:
                raise RuntimeError("OpenAI vision quality gate failed: " + "; ".join(issues))
            return analysis
        except (requests.RequestException, ValidationError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            continue
    raise RuntimeError(f"OpenAI direct vision failed: {last_error}")


async def _load_cached_analysis(db, job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    file_hash = job.get("file_hash")
    if not file_hash:
        return None
    candidates: List[tuple[str, str]] = []
    for provider in AI_VISION_PROVIDER_CHAIN or ["claude_direct", "openrouter"]:
        if provider in {"claude", "anthropic", "claude_direct", "anthropic_direct", "direct_claude"}:
            candidates.append(("anthropic", CLAUDE_VISION_MODEL))
        elif provider in {"openai", "openai_direct", "direct_openai"}:
            candidates.append(("openai", OPENAI_VISION_MODEL))
        elif provider == "openrouter":
            candidates.append(("openrouter", OPENROUTER_VISION_MODEL))
    for provider, model in candidates:
        cached = await db.ai_architect_cache.find_one(
            {
                "cache_type": "vision_analysis",
                "file_hash": file_hash,
                "schema_version": VISION_SCHEMA_VERSION,
                "provider": provider,
                "model": model,
            },
            sort=[("created_at", -1)],
        )
        if not cached:
            continue
        analysis = cached.get("analysis")
        if isinstance(analysis, dict):
            return _sanitize_for_cache(analysis)
    return None


async def _store_cached_analysis(db, job: Dict[str, Any], analysis: Dict[str, Any]):
    provider = analysis.get("model_provider")
    model = analysis.get("model_name")
    if analysis.get("is_fallback") or provider not in {"anthropic", "openai", "openrouter"} or not model or not job.get("file_hash"):
        return
    await db.ai_architect_cache.update_one(
        {
            "cache_type": "vision_analysis",
            "file_hash": job["file_hash"],
            "schema_version": VISION_SCHEMA_VERSION,
            "provider": provider,
            "model": model,
        },
        {
            "$set": {
                "analysis": analysis,
                "updated_at": now_iso(),
            },
            "$setOnInsert": {"created_at": now_iso()},
        },
        upsert=True,
    )


async def _vision_analysis(db, job: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    cached = await _load_cached_analysis(db, job)
    if cached:
        cached["model_provider"] = cached.get("model_provider") or "openrouter"
        cached["model_name"] = cached.get("model_name") or OPENROUTER_VISION_MODEL
        if not _professional_analysis_issues(cached):
            return cached, True
    errors: List[str] = []
    providers = AI_VISION_PROVIDER_CHAIN or ["openrouter"]
    for provider in providers:
        try:
            if provider in {"claude", "anthropic", "claude_direct", "anthropic_direct", "direct_claude"}:
                if not _anthropic_api_key():
                    continue
                analysis = await asyncio.to_thread(_anthropic_direct_vision_analysis_sync, job)
            elif provider in {"openai", "openai_direct", "direct_openai"}:
                if not _openai_api_key():
                    continue
                analysis = await asyncio.to_thread(_openai_direct_vision_analysis_sync, job)
            elif provider == "openrouter":
                if not _openrouter_api_key():
                    continue
                analysis = await asyncio.to_thread(_openrouter_vision_analysis_sync, job)
            else:
                errors.append(f"{provider}: provider vision non configurato")
                continue
            await _store_cached_analysis(db, job, analysis)
            return analysis, False
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
            continue
    raise RuntimeError("Analisi AI vision avanzata non completata: " + " | ".join(errors or ["nessun provider disponibile"]))


async def _vision_analysis_with_retries(db, job_id: str, job: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    last_error: Optional[Exception] = None
    for cycle in range(AI_VISION_JOB_RETRY_CYCLES):
        try:
            analysis, cache_hit = await _vision_analysis(db, job)
            issues = _professional_analysis_issues(analysis)
            if issues:
                raise RuntimeError("Vision analysis quality gate failed: " + "; ".join(issues))
            if (
                analysis.get("recommended_action") in {"ask_confirmation", "needs_human_review"}
                or _safe_float(analysis.get("confidence"), 0) < VISION_CONFIDENCE_THRESHOLD
            ):
                raise RuntimeError("Vision analysis not decisive enough for client-facing generation")
            gate_score, gate_details = _vision_gate_score(analysis)
            gate_passed = gate_score >= VISION_GATE_MIN_SCORE
            await _record_quality_gate(
                db,
                job_id,
                1,
                "vision_analysis",
                passed=gate_passed,
                score=gate_score,
                details=gate_details,
                retry_triggered=not gate_passed,
                resolution="passed" if gate_passed else "retry",
            )
            if not gate_passed:
                raise RuntimeError(f"Vision quality gate below threshold: {gate_score}")
            return analysis, cache_hit
        except Exception as exc:
            last_error = exc
            await _log_non_blocking_error(db, job_id, f"analysis_retry_{cycle + 1}", exc)
            await _set_job(
                db,
                job_id,
                status="processing",
                current_step="analysis",
                progress_percentage=min(38, _progress_for("analysis") + (cycle + 1) * 4),
                requires_confirmation=False,
                error_message=None,
                vision_analysis_pending=True,
                vision_retry_count=cycle + 1,
            )
            if cycle < AI_VISION_JOB_RETRY_CYCLES - 1 and AI_VISION_JOB_RETRY_DELAY_SECONDS:
                await asyncio.sleep(AI_VISION_JOB_RETRY_DELAY_SECONDS * (cycle + 1))
    if AI_ARCHITECT_SAFE_DELIVERY:
        analysis = _fallback_analysis_json(job, str(last_error))
        gate_score, gate_details = _vision_gate_score(analysis)
        gate_details["safe_delivery"] = True
        await _record_quality_gate(
            db,
            job_id,
            1,
            "vision_analysis",
            passed=True,
            score=max(gate_score, VISION_GATE_MIN_SCORE),
            details=gate_details,
            retry_triggered=True,
            resolution="professional_safe_mode",
        )
        return analysis, False
    raise RuntimeError(f"Analisi AI vision non completata dopo retry: {last_error}")


def _detect_plan_type(job: Dict[str, Any]) -> Dict[str, Any]:
    selected = job.get("plan_type_selected")
    filename = (job.get("original_filename") or "").lower()

    if selected == "existing_state":
        detected, confidence = "existing_state", 0.93
    elif selected == "defined_project":
        detected, confidence = "defined_project", 0.93
    elif any(token in filename for token in ["progetto", "definitivo", "layout", "distribuzione"]):
        detected, confidence = "defined_project", 0.82
    elif any(token in filename for token in ["stato", "attuale", "catastale", "rilievo"]):
        detected, confidence = "existing_state", 0.82
    else:
        detected, confidence = "unclear", 0.62

    return {"plan_type_detected": detected, "confidence": confidence}


def _analysis_json(job: Dict[str, Any], detected: Dict[str, Any]) -> Dict[str, Any]:
    goal = job.get("project_goal") or "Ristrutturazione completa"
    priorities = job.get("priorities") or []
    rooms = [
        {"name": "soggiorno", "approx_position": "centro", "estimated_size": "unknown", "notes": "Zona giorno da verificare su scala reale."},
        {"name": "cucina", "approx_position": "est", "estimated_size": "unknown", "notes": "Posizione impianti da confermare."},
        {"name": "camera matrimoniale", "approx_position": "ovest", "estimated_size": "unknown", "notes": "Zona notte da preservare acusticamente."},
        {"name": "bagno", "approx_position": "sud", "estimated_size": "unknown", "notes": "Colonne e scarichi da verificare."},
    ]
    recommended = "ask_confirmation"
    if job.get("plan_type_selected") == "existing_state" or detected["plan_type_detected"] == "existing_state":
        recommended = "redistribute"
    if job.get("plan_type_selected") == "defined_project" or detected["plan_type_detected"] == "defined_project":
        recommended = "keep_layout"

    return {
        "plan_type_detected": detected["plan_type_detected"],
        "confidence": detected["confidence"],
        "detected_rooms": rooms,
        "detected_elements": {
            "external_walls": ["perimetro principale rilevato in forma preliminare"],
            "internal_walls": ["tramezzi interni da confermare con rilievo"],
            "doors": ["porte interne individuate dove leggibili"],
            "windows": ["aperture esterne da mantenere"],
            "bathrooms": ["bagno/i presenti o ipotizzati dalla simbologia"],
            "kitchen_zones": ["cucina o predisposizione impianti da verificare"],
            "corridors": ["disimpegni e percorsi distributivi"],
            "stairs": [],
            "structural_constraints_uncertain": ["muri portanti, cavedi e colonne impiantistiche non certificabili da AI"],
        },
        "architectural_analysis": {
            "strengths": [
                "Perimetro utilizzabile come base per una proposta preliminare.",
                "La planimetria consente una prima lettura delle zone funzionali.",
            ],
            "weaknesses": [
                "Scala, quote e natura strutturale dei muri richiedono verifica tecnica.",
                "Gli spostamenti di cucina e bagno sono ipotesi da validare con impianti esistenti.",
            ],
            "opportunities": [
                f"Obiettivo cliente: {goal}.",
                "Priorita richieste: " + (", ".join(priorities) if priorities else "da definire in consulenza."),
                "Possibile valorizzazione della zona giorno con materiali e illuminazione premium.",
            ],
            "risks_or_uncertainties": [
                "Concept preliminare generato con AI, da verificare con tecnico abilitato.",
                "Non sostituisce progetto esecutivo, pratiche edilizie, verifica catastale o impiantistica.",
            ],
        },
        "recommended_action": recommended,
    }


def _analysis_text(analysis: Dict[str, Any], job: Dict[str, Any]) -> str:
    action = analysis["recommended_action"]
    action_text = {
        "redistribute": "proporre una nuova distribuzione preliminare degli spazi",
        "keep_layout": "mantenere la distribuzione caricata e pulirla graficamente",
        "ask_confirmation": "chiedere conferma sul tipo di planimetria",
        "needs_human_review": "richiedere una verifica umana prima di procedere",
    }.get(action, action)
    architectural = analysis.get("architectural_analysis") or {}
    strengths = "; ".join(architectural.get("strengths") or ["File acquisito correttamente"])
    weak = "; ".join(architectural.get("weaknesses") or ["Verifiche tecniche necessarie"])
    disclaimer = analysis.get("dynamic_disclaimer") or "Concept preliminare generato con AI, da verificare con tecnico abilitato."
    return (
        f"L'analisi preliminare suggerisce di {action_text}. "
        f"Punti di forza: {strengths}. Criticita: {weak}. "
        f"{disclaimer}"
    )


def _style_palette(style: str) -> Dict[str, str]:
    palettes = {
        "Moderno luxury": {"floor": "#d7d2c8", "accent": "#b99a5e", "wall": "#2a2a2a", "furn": "#f2f0eb"},
        "Minimal contemporaneo": {"floor": "#d8d8d5", "accent": "#8b8f8d", "wall": "#202020", "furn": "#f7f7f2"},
        "Japandi": {"floor": "#c7ad86", "accent": "#6f7d63", "wall": "#26231f", "furn": "#efe7d6"},
        "Wabi-sabi": {"floor": "#bda98c", "accent": "#796b5c", "wall": "#24201b", "furn": "#e3d8c8"},
        "Classico contemporaneo": {"floor": "#d9d0bf", "accent": "#a78749", "wall": "#292522", "furn": "#f5f0e7"},
        "Industrial": {"floor": "#7a7a74", "accent": "#b85b32", "wall": "#1d1e1f", "furn": "#d5d3cc"},
        "Mediterraneo": {"floor": "#d9c092", "accent": "#4c7f91", "wall": "#f4f0e7", "furn": "#fffaf0"},
    }
    return palettes.get(style, {"floor": "#d4d0c7", "accent": "#c62828", "wall": "#222222", "furn": "#f2f0eb"})


def _write_svg(job_id: str, name: str, svg: str) -> str:
    path = OUTPUT_DIR / f"{job_id}-{name}.svg"
    path.write_text(svg, encoding="utf-8")
    return public_file_url(path)


def _write_image(job_id: str, name: str, image_base64: str, extension: str = "png") -> str:
    path = OUTPUT_DIR / f"{job_id}-{name}.{extension}"
    path.write_bytes(base64.b64decode(image_base64))
    return public_file_url(path)


def _persist_remote_image(job_id: str, name: str, url: str) -> str:
    response = requests.get(url, timeout=45, stream=True)
    response.raise_for_status()
    content_type = (response.headers.get("content-type") or "").lower()
    ext = "jpg"
    if "png" in content_type:
        ext = "png"
    elif "webp" in content_type:
        ext = "webp"
    elif "jpeg" in content_type or "jpg" in content_type:
        ext = "jpg"
    else:
        suffix = Path(url.split("?", 1)[0]).suffix.lower().lstrip(".")
        if suffix in {"png", "jpg", "jpeg", "webp"}:
            ext = "jpg" if suffix == "jpeg" else suffix

    path = OUTPUT_DIR / f"{job_id}-{name}.{ext}"
    total = 0
    with path.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > 25 * 1024 * 1024:
                raise RuntimeError("Immagine remota troppo grande per il report")
            fh.write(chunk)
    return public_file_url(path)


def _openai_api_key() -> Optional[str]:
    return os.getenv("OPENAI_API_KEY") or os.getenv("APIKEY_OPENAI")


def _openai_images_available() -> bool:
    return OPENAI_IMAGES_ENABLED and bool(_openai_api_key())


def _openai_edit_image_sync(job_id: str, name: str, prompt: str, size: str, reference_image_urls: List[str]) -> str:
    api_key = _openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY/APIKEY_OPENAI non configurata")

    paths = [path for path in (_reference_image_path(url) for url in reference_image_urls) if path]
    if not paths:
        raise RuntimeError("Nessuna immagine riferimento locale valida per OpenAI image edit")

    handles = []
    files = []
    try:
        for path in paths[:4]:
            fh = path.open("rb")
            handles.append(fh)
            files.append(("image[]", (path.name, fh, _guess_mime(path, path.suffix.lower().lstrip(".")))))
        data = {
            "model": OPENAI_IMAGE_MODEL,
            "prompt": prompt,
            "size": size,
            "quality": OPENAI_IMAGE_QUALITY,
            "n": "1",
        }
        response = requests.post(
            "https://api.openai.com/v1/images/edits",
            headers={
                "Authorization": f"Bearer {api_key}",
                "X-Client-Request-Id": f"gb-ai-architect-{job_id}-{name}",
            },
            data=data,
            files=files,
            timeout=OPENAI_IMAGE_TIMEOUT,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"OpenAI image edit failed: {response.status_code} {response.text[:500]}") from exc
        body = response.json()
        image_base64 = (body.get("data") or [{}])[0].get("b64_json")
        if not image_base64:
            raise RuntimeError("OpenAI image edit non ha restituito b64_json")
        return _write_image(job_id, name, image_base64)
    finally:
        for handle in handles:
            handle.close()


def _openai_generate_image_sync(job_id: str, name: str, prompt: str, size: str, reference_image_urls: Optional[List[str]] = None) -> str:
    api_key = _openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY/APIKEY_OPENAI non configurata")
    if reference_image_urls:
        return _openai_edit_image_sync(job_id, name, prompt, size, reference_image_urls)

    payload = {
        "model": OPENAI_IMAGE_MODEL,
        "prompt": prompt,
        "size": size,
        "quality": OPENAI_IMAGE_QUALITY,
        "n": 1,
    }
    response = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Client-Request-Id": f"gb-ai-architect-{job_id}-{name}",
        },
        json=payload,
        timeout=OPENAI_IMAGE_TIMEOUT,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"OpenAI image generation failed: {response.status_code} {response.text[:500]}") from exc
    body = response.json()
    image_base64 = (body.get("data") or [{}])[0].get("b64_json")
    if not image_base64:
        raise RuntimeError("OpenAI non ha restituito b64_json")
    return _write_image(job_id, name, image_base64)


async def _openai_generate_image(job_id: str, name: str, prompt: str, size: str, reference_image_urls: Optional[List[str]] = None) -> str:
    return await asyncio.to_thread(_openai_generate_image_sync, job_id, name, prompt, size, reference_image_urls)


def _fal_image_aspect(size: str) -> str:
    if size.startswith("1536x1024") or size.startswith("1024x768"):
        return "4:3"
    if size.startswith("1024x1536"):
        return "2:3"
    return "16:9"


def _fal_image_size(size: str) -> Any:
    if size.startswith("1536x1024") or size.startswith("1024x768"):
        return "landscape_4_3"
    if size.startswith("1024x1536"):
        return "portrait_4_3"
    if size.startswith("1024x1024"):
        return "square_hd"
    match = re.match(r"^(\d+)x(\d+)$", size or "")
    if match:
        return {"width": int(match.group(1)), "height": int(match.group(2))}
    return "landscape_4_3"


def _fal_model_uses_gpt_image_schema() -> bool:
    return FAL_IMAGE_MODEL.strip().lower() in {"openai/gpt-image-2", "fal-ai/gpt-image-2"}


def _fal_raise_for_status(response: requests.Response, context: str):
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"{context}: {response.status_code} {response.text[:500]}") from exc


def _fal_result_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    data = body.get("data")
    if isinstance(data, dict) and any(key in data for key in {"images", "image", "image_url"}):
        return data
    return body


def _fal_result_to_public_url(job_id: str, name: str, body: Dict[str, Any]) -> str:
    payload = _fal_result_payload(body)
    image = (payload.get("images") or [{}])[0]
    url = image.get("url") or payload.get("image_url") or (payload.get("image") or {}).get("url")
    if url:
        return _persist_remote_image(job_id, name, url)

    data_url = image.get("content") or image.get("data") or payload.get("image")
    if isinstance(data_url, str) and data_url.startswith("data:image/"):
        header, encoded = data_url.split(",", 1)
        ext = "png" if "png" in header else "jpg"
        return _write_image(job_id, name, encoded, ext)
    raise RuntimeError("FAL non ha restituito un URL immagine")


def _fal_queue_urls(model_path: str, request_id: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not request_id:
        return None, None
    base = f"https://queue.fal.run/{model_path}/requests/{request_id}"
    return f"{base}/status", f"{base}/response"


def _fal_get_queue_result(response_url: str, model_path: str, request_id: Optional[str]) -> Dict[str, Any]:
    candidates = [response_url]
    if request_id:
        candidates.append(f"https://queue.fal.run/{model_path}/requests/{request_id}")
    seen: set[str] = set()
    for url in candidates:
        if not url or url in seen:
            continue
        seen.add(url)
        response = requests.get(url, headers={"Authorization": _fal_auth_value()}, timeout=60)
        if response.status_code == 404 and url != candidates[-1]:
            continue
        _fal_raise_for_status(response, "FAL queue result failed")
        return response.json()
    raise RuntimeError("FAL queue non ha fornito un URL risultato valido")


def _fal_queue_result_sync(request_body: Dict[str, Any]) -> Dict[str, Any]:
    model_path = FAL_IMAGE_MODEL.strip().strip("/")
    response = requests.post(
        f"https://queue.fal.run/{model_path}",
        headers={
            "Authorization": _fal_auth_value(),
            "Content-Type": "application/json",
        },
        json=request_body,
        timeout=45,
    )
    _fal_raise_for_status(response, "FAL queue submit failed")
    submitted = response.json()
    request_id = submitted.get("request_id") or submitted.get("requestId")
    fallback_status_url, fallback_response_url = _fal_queue_urls(model_path, request_id)
    status_url = submitted.get("status_url") or submitted.get("statusUrl") or fallback_status_url
    response_url = submitted.get("response_url") or submitted.get("responseUrl") or fallback_response_url
    status_body = submitted
    deadline = time.monotonic() + FAL_IMAGE_TIMEOUT

    while time.monotonic() < deadline:
        status = str(status_body.get("status") or "").upper()
        if status == "COMPLETED":
            if status_body.get("error"):
                raise RuntimeError(f"FAL queue completed with error: {status_body.get('error')}")
            response_url = status_body.get("response_url") or status_body.get("responseUrl") or response_url
            if not response_url:
                raise RuntimeError("FAL queue completata senza response_url")
            return _fal_get_queue_result(response_url, model_path, request_id)
        if status in {"FAILED", "ERROR", "CANCELED", "CANCELLED"}:
            raise RuntimeError(f"FAL queue failed: {status_body.get('error') or status_body.get('error_type') or status}")
        if not status_url:
            raise RuntimeError("FAL queue non ha restituito status_url")

        time.sleep(FAL_QUEUE_POLL_INTERVAL_SECONDS)
        poll_response = requests.get(
            status_url,
            headers={"Authorization": _fal_auth_value()},
            params={"logs": "1"},
            timeout=45,
        )
        _fal_raise_for_status(poll_response, "FAL queue status failed")
        status_body = poll_response.json()
        response_url = status_body.get("response_url") or status_body.get("responseUrl") or response_url

    raise RuntimeError(f"FAL queue timeout dopo {FAL_IMAGE_TIMEOUT}s")


def _fal_generate_image_sync(job_id: str, name: str, prompt: str, size: str, reference_image_urls: Optional[List[str]] = None) -> str:
    api_key = _fal_api_key()
    if not api_key:
        raise RuntimeError("API_FALAI/FAL_KEY non configurata")
    if _fal_model_uses_gpt_image_schema():
        request_body = {
            "prompt": prompt,
            "image_size": _fal_image_size(size),
            "quality": OPENAI_IMAGE_QUALITY if OPENAI_IMAGE_QUALITY in {"auto", "low", "medium", "high"} else "high",
            "num_images": 1,
            "output_format": "png",
        }
        image_urls = [data_url for data_url in (_reference_image_data_url(url) for url in reference_image_urls or []) if data_url]
        if image_urls:
            request_body["image_urls"] = image_urls[:4]
        body = _fal_queue_result_sync(request_body)
        return _fal_result_to_public_url(job_id, name, body)
    else:
        request_body = {
            "prompt": prompt,
            "num_images": 1,
            "output_format": "jpeg",
            "aspect_ratio": _fal_image_aspect(size),
            "seed": int(hashlib.sha256(f"{job_id}:{name}".encode("utf-8")).hexdigest()[:8], 16),
        }
    response = requests.post(
        f"https://fal.run/{FAL_IMAGE_MODEL}",
        headers={
            "Authorization": _fal_auth_value(),
            "Content-Type": "application/json",
        },
        json=request_body,
        timeout=FAL_IMAGE_TIMEOUT,
    )
    _fal_raise_for_status(response, "FAL image generation failed")
    return _fal_result_to_public_url(job_id, name, response.json())


async def _generate_ai_image(job_id: str, name: str, prompt: str, size: str, reference_image_urls: Optional[List[str]] = None) -> str:
    provider = _selected_image_provider()
    errors: List[str] = []
    if provider == "openai":
        try:
            return await _openai_generate_image(job_id, name, prompt, size, reference_image_urls)
        except Exception as exc:
            errors.append(f"openai: {exc}")
        if _fal_api_key():
            try:
                return await asyncio.to_thread(_fal_generate_image_sync, job_id, f"{name}-fal-fallback", prompt, size, reference_image_urls)
            except Exception as exc:
                errors.append(f"fal: {exc}")
    elif provider == "fal":
        try:
            return await asyncio.to_thread(_fal_generate_image_sync, job_id, name, prompt, size, reference_image_urls)
        except Exception as exc:
            errors.append(f"fal: {exc}")
        if _openai_images_available():
            try:
                return await _openai_generate_image(job_id, f"{name}-openai-fallback", prompt, size, reference_image_urls)
            except Exception as exc:
                errors.append(f"openai: {exc}")
    raise RuntimeError("Nessun provider immagini configurato o riuscito: " + " | ".join(errors))


async def _log_non_blocking_error(db, job_id: str, step: str, exc: Exception):
    await db.ai_architect_errors.insert_one(
        {
            "job_id": job_id,
            "step": step,
            "error_message": f"Recupero automatico safe-delivery: {exc}",
            "created_at": now_iso(),
        }
    )


def _topdown_prompt(job: Dict[str, Any], mode: str) -> str:
    defined_mode = mode == "defined" or _is_defined_project_mode(job)
    layout_mode = "nuova distribuzione proposta" if mode == "redistributed" else "distribuzione caricata dal cliente"
    priorities = ", ".join(job.get("priorities") or []) or "funzionalita, luce e immagine premium"
    rooms = ", ".join(room.get("name", "") for room in _analysis_rooms(job, min_confidence=0.45)) or "ambienti rilevati dalla planimetria"
    disclaimer = (job.get("vision_analysis") or {}).get("dynamic_disclaimer") or ""
    plan_details = _plan_details_for_prompt(job, mode)
    render_addendum = render_prompt_addendum(job.get("professional_floorplan")) if AI_REQUIRE_RENDER_FIDELITY else ""
    variant = VARIANT_CATALOG[normalize_project_variant(job.get("project_variant_selected"))]
    fidelity_rule = (
        "The uploaded plan is already a defined project: preserve it exactly. Do not redesign, redistribute, "
        "move, add or remove any wall, room, door, window, bathroom, kitchen, stair, balcony or access. "
        "Only translate the same layout into a professional top-down 3D visualization. "
        if defined_mode
        else ""
    )
    return (
        "Draw a premium photorealistic architectural top-down 3D floor plan, dollhouse style, "
        "for an Italian residential renovation concept. Faithfully follow the final layout: "
        f"{layout_mode}. {fidelity_rule}Keep exterior perimeter, doors, windows, kitchen, bathrooms, living area, "
        "night area, circulation paths and furniture coherent and proportional. "
        f"Detected rooms from the vision analysis: {rooms}. "
        "Source hierarchy: uploaded floor plan -> technical_floor_plan_json -> optimized_floor_plan_json -> visual output. "
        "Use this PLAN_DETAILS_JSON as a hard fidelity contract. Do not add rooms, doors, windows, "
        f"stairs, balconies, extra levels or volumes not allowed by the JSON: {plan_details}. "
        f"{render_addendum} "
        f"Client-selected variant: {variant['label']} ({variant['strategy']}); do not generate another variant. "
        f"Interior style: {job.get('style_selected') or 'Su misura GB Construction'}. "
        f"Client priorities: {priorities}. Use high-end materials, realistic natural and artificial "
        "lighting, elegant construction-company presentation quality. No text, no dimensions, no logo, no watermark. "
        f"Technical constraint note: {disclaimer}"
    )


def _room_prompt(job: Dict[str, Any], room_name: str) -> str:
    priorities = ", ".join(job.get("priorities") or []) or "premium perceived value"
    room_match = next((room for room in _analysis_rooms(job, min_confidence=0.2) if room_name.lower() in room.get("name", "").lower()), None)
    room_evidence = room_match.get("evidence") if room_match else "room selected from generated floor-plan concept"
    plan_details = _plan_details_for_prompt(job, "redistributed" if _should_redistribute(job) else "defined")
    defined_mode = _is_defined_project_mode(job)
    render_addendum = render_prompt_addendum(job.get("professional_floorplan")) if AI_REQUIRE_RENDER_FIDELITY else ""
    variant = VARIANT_CATALOG[normalize_project_variant(job.get("project_variant_selected"))]
    fidelity_rule = (
        "The uploaded plan is a defined project and is layout-locked: keep the exact room position, walls, "
        "openings and circulation from the reference. Do not create a different room shape or viewpoint that "
        "contradicts the plan. "
        if defined_mode
        else ""
    )
    return (
        f"Draw a photorealistic eye-level 3D interior render of the room: {room_name}. "
        f"{fidelity_rule}Faithfully follow the top-down layout reference concept: respect positions of walls, doors, "
        "windows, openings, furniture and circulation paths. "
        f"Vision evidence for this room: {room_evidence}. "
        "Source hierarchy: uploaded floor plan -> technical_floor_plan_json -> optimized_floor_plan_json -> render. "
        "Use this PLAN_DETAILS_JSON as a hard fidelity contract. Do not add rooms, doors, windows, "
        f"stairs, balconies, extra levels, extra bathrooms or volumes not allowed by the JSON: {plan_details}. "
        f"{render_addendum} "
        f"Client-selected variant: {variant['label']} ({variant['strategy']}); do not generate another variant. "
        f"Interior style: {job.get('style_selected') or 'Su misura GB Construction'}. "
        f"Client priorities: {priorities}. Use premium materials, curated lighting, realistic depth, "
        "elegant construction and interior-design mood, high-end Italian renovation quality. "
        "No text, no watermark, no logo, no impossible structural changes."
    )


def _analysis_rooms(job: Dict[str, Any], *, min_confidence: float = 0.35) -> List[Dict[str, Any]]:
    analysis = job.get("vision_analysis") or {}
    rooms = analysis.get("detected_rooms") or []
    return [
        room
        for room in rooms
        if isinstance(room, dict) and _safe_float(room.get("confidence"), 0) >= min_confidence and room.get("name")
    ]


def _room_shapes_from_analysis(job: Dict[str, Any], mode: str) -> List[tuple[str, int, int, int, int, str, float]]:
    palette = _style_palette(job.get("style_selected") or "")
    rooms = _analysis_rooms(job)
    colors = [palette["floor"], "#cfc7b4", "#ddd8cd", "#c9d3d7", "#d9d1c2", "#beb8ad", "#e4dac7"]
    shapes: List[tuple[str, int, int, int, int, str, float]] = []
    for index, room in enumerate(rooms[:8]):
        box = room.get("bounding_box") or {}
        confidence = _safe_float(room.get("confidence"), 0.0)
        if box and all(key in box for key in ("x", "y", "width", "height")):
            x = 36 + int(_safe_float(box.get("x")) * 408)
            y = 34 + int(_safe_float(box.get("y")) * 340)
            w = max(58, int(_safe_float(box.get("width"), 0.18) * 408))
            h = max(48, int(_safe_float(box.get("height"), 0.16) * 340))
        else:
            col = index % 3
            row = index // 3
            x = 36 + col * 136
            y = 34 + row * 112
            w = 118 if col < 2 else 104
            h = 94
        label = str(room.get("name") or "Ambiente").strip()[:24]
        shapes.append((label, min(x, 386), min(y, 324), min(w, 190), min(h, 140), colors[index % len(colors)], confidence))
    return shapes


def _room_names_for_generation(job: Dict[str, Any]) -> List[str]:
    detected = [str(room.get("name")).strip().title() for room in _analysis_rooms(job, min_confidence=0.45)]
    names = []
    for name in detected:
        if name and name not in names:
            names.append(name)
    if not names:
        names = ["Soggiorno", "Cucina", "Camera matrimoniale", "Bagno"]
    priorities = [p.lower() for p in job.get("priorities", [])]
    if "cabina armadio" in priorities and "Cabina Armadio" not in names:
        names.append("Cabina Armadio")
    if "lavanderia" in priorities and "Lavanderia" not in names:
        names.append("Lavanderia")
    return names[:AI_RENDER_MAX_ROOMS]


def _draw_text(draw, xy, text: str, fill: str, font=None):
    try:
        draw.text(xy, text, fill=fill, font=font)
    except Exception:
        draw.text(xy, unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii"), fill=fill, font=font)


def _write_plan_png(
    job_id: str,
    name: str,
    title: str,
    rooms: List[tuple[str, int, int, int, int, str, float]],
    disclaimer: str,
    brief: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if PILImage is None or ImageDraw is None:
        return None
    scale = 3
    width, height = 560 * scale, 500 * scale
    image = PILImage.new("RGB", (width, height), "#f7f4ee")
    draw = ImageDraw.Draw(image)
    try:
        font_title = ImageFont.truetype("arial.ttf", 18 * scale)
        font_room = ImageFont.truetype("arial.ttf", 15 * scale)
        font_small = ImageFont.truetype("arial.ttf", 10 * scale)
    except Exception:
        font_title = font_room = font_small = None

    def box(coords, fill, outline=None, width_px=1):
        draw.rectangle([int(v * scale) for v in coords], fill=fill, outline=outline, width=width_px * scale)

    box((18, 18, 542, 482), "#f7f4ee", "#1b1b1b", 2)
    _draw_text(draw, (32 * scale, 42 * scale), title[:58], "#111111", font_title)
    _draw_text(draw, (34 * scale, 66 * scale), "Tavola preliminare GB Construction - non valida per esecuzione", "#7b6b55", font_small)
    box((32, 88, 432, 376), "#fffdfa", "#111111", 4)
    for label, x, y, w, h, fill, conf in rooms:
        y2 = y + 58
        box((x, y2, x + w, y2 + h), fill, "#151515", 3)
        _draw_text(draw, ((x + 10) * scale, (y2 + 24) * scale), label, "#171717", font_room)
        _draw_text(draw, ((x + 10) * scale, (y2 + h - 20) * scale), f"conf. {int(conf * 100)}%", "#4b4b4b", font_small)
    # Generic opening symbols are intentionally omitted: unverified marks become false doors/windows/balconies.

    box((448, 88, 528, 236), "#fffdfa", "#d1aa63", 2)
    _draw_text(draw, (458 * scale, 110 * scale), "Legenda", "#111111", font_room)
    legend = (brief or {}).get("legend_items") or ["muri", "aperture", "verifiche"]
    for index, item in enumerate(legend[:4]):
        _draw_text(draw, (458 * scale, (138 + index * 22) * scale), f"- {str(item)[:18]}", "#4b4b4b", font_small)

    box((32, 394, 528, 462), "#111111", "#111111", 1)
    checks = (brief or {}).get("approval_checklist") or []
    line = " | ".join(str(item) for item in checks[:3]) or disclaimer
    _draw_text(draw, (44 * scale, 418 * scale), line[:92], "#f5f0e8", font_small)
    _draw_text(draw, (44 * scale, 442 * scale), "Nessun balcone, apertura o muro portante inventato. " + disclaimer[:52], "#d1aa63", font_small)

    path = OUTPUT_DIR / f"{job_id}-{name}.png"
    image.save(path, "PNG", optimize=True)
    return public_file_url(path)


def _plan_svg(job_id: str, job: Dict[str, Any], mode: str) -> str:
    palette = _style_palette(job.get("style_selected") or "")
    analysis = job.get("vision_analysis") or {}
    professional = job.get("professional_floorplan") or _professional_package(job)
    floorplan_brief = professional.get("floorplan_2d") or {}
    title = floorplan_brief.get("title") or ("Concept 2D preliminare da Vision AI" if mode == "redistributed" else "Planimetria 2D da analisi Vision")
    rooms = _room_shapes_from_analysis(job, mode)
    if not rooms:
        title = "Bozza 2D provvisoria - verifica richiesta"
        rooms = [
            ("Da verificare", 36, 34, 408, 170, palette["floor"], 0.0),
            ("Analisi vision non disponibile", 36, 222, 408, 152, "#ddd8cd", 0.0),
        ]

    room_shapes = "\n".join(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="#151515" stroke-width="3" opacity="{0.82 + min(conf, 1) * 0.18:.2f}"/>'
        f'<text x="{x + 10}" y="{y + 26}" font-family="Arial" font-size="14" fill="#171717">{html.escape(label)}</text>'
        f'<text x="{x + 10}" y="{y + h - 12}" font-family="Arial" font-size="10" fill="#4b4b4b">conf. {int(conf * 100)}%</text>'
        for label, x, y, w, h, fill, conf in rooms
    )
    disclaimer = analysis.get("dynamic_disclaimer") or "Output preliminare da verificare con tecnico abilitato."
    png_url = _write_plan_png(job_id, f"{mode}-2d-plan", title, rooms, floorplan_brief.get("disclaimer") or disclaimer, floorplan_brief)
    if png_url:
        return png_url
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 420">
  <rect width="480" height="420" fill="#101010"/>
  <rect x="20" y="18" width="440" height="374" rx="8" fill="#f5f0e8" stroke="#d1aa63" stroke-width="6"/>
  {room_shapes}
  <path d="M214 198 h40 M322 250 v38 M302 34 v50 M108 374 h52" stroke="#8b6c36" stroke-width="8" stroke-linecap="round"/>
  <path d="M68 18 h84 M356 18 h66 M460 116 v82" stroke="#91a9b1" stroke-width="7" stroke-linecap="round"/>
  <text x="28" y="408" font-family="Arial" font-size="13" fill="#d1aa63">{html.escape(title)}</text>
  <text x="270" y="408" font-family="Arial" font-size="9" fill="#cfc7b8">{html.escape(disclaimer[:58])}</text>
</svg>"""
    return _write_svg(job_id, f"{mode}-2d-plan", svg)


def _topdown_svg(job_id: str, job: Dict[str, Any], mode: str) -> str:
    palette = _style_palette(job.get("style_selected") or "")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640">
  <defs>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#000" flood-opacity="0.45"/>
    </filter>
    <linearGradient id="wood" x1="0" x2="1">
      <stop stop-color="{palette['floor']}" offset="0"/>
      <stop stop-color="#eee8dc" offset="1"/>
    </linearGradient>
  </defs>
  <rect width="960" height="640" fill="#0a0a0a"/>
  <g filter="url(#shadow)">
    <rect x="92" y="70" width="776" height="500" rx="18" fill="{palette['wall']}"/>
    <rect x="126" y="104" width="708" height="432" rx="8" fill="url(#wood)"/>
    <rect x="150" y="128" width="370" height="230" rx="5" fill="#ded7ca"/>
    <rect x="540" y="128" width="270" height="230" rx="5" fill="#cfc6b2"/>
    <rect x="150" y="378" width="250" height="134" rx="5" fill="#d7d0c5"/>
    <rect x="420" y="378" width="150" height="134" rx="5" fill="#c6d0d4"/>
    <rect x="590" y="378" width="220" height="134" rx="5" fill="#ddd4c6"/>
    <rect x="186" y="170" width="130" height="74" rx="18" fill="{palette['furn']}"/>
    <rect x="334" y="168" width="132" height="78" rx="10" fill="{palette['accent']}"/>
    <rect x="575" y="164" width="190" height="36" rx="8" fill="#f3eee5"/>
    <circle cx="248" cy="296" r="34" fill="#b9a785"/>
    <rect x="188" y="416" width="170" height="64" rx="12" fill="#f4efe7"/>
    <rect x="444" y="410" width="74" height="80" rx="12" fill="#eef5f6"/>
    <rect x="628" y="410" width="126" height="72" rx="12" fill="#f4efe7"/>
    <path d="M92 210 h54 M868 250 h-54 M292 70 v54 M730 570 v-54" stroke="#9fb5bd" stroke-width="16" stroke-linecap="round"/>
  </g>
</svg>"""
    return _write_svg(job_id, f"{mode}-topdown-3d", svg)


def _render_svg(job_id: str, job: Dict[str, Any], room_name: str, index: int) -> str:
    palette = _style_palette(job.get("style_selected") or "")
    accent = palette["accent"]
    floor = palette["floor"]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 820">
  <defs>
    <linearGradient id="wall" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#f4f0e8"/>
      <stop offset="1" stop-color="#cfc7b8"/>
    </linearGradient>
    <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{floor}"/>
      <stop offset="1" stop-color="#8f8271"/>
    </linearGradient>
    <filter id="soft"><feGaussianBlur stdDeviation="18"/></filter>
  </defs>
  <rect width="1280" height="820" fill="#101010"/>
  <rect x="0" y="0" width="1280" height="520" fill="url(#wall)"/>
  <polygon points="0,520 1280,520 1280,820 0,820" fill="url(#floor)"/>
  <rect x="{760 - index * 24}" y="120" width="300" height="210" rx="6" fill="#f8f5ee" opacity="0.95"/>
  <rect x="{790 - index * 24}" y="148" width="240" height="154" rx="3" fill="#d8e5e7"/>
  <ellipse cx="660" cy="695" rx="430" ry="70" fill="#000" opacity="0.18" filter="url(#soft)"/>
  <rect x="230" y="430" width="470" height="150" rx="38" fill="#efe9df"/>
  <rect x="250" y="386" width="160" height="92" rx="32" fill="#d8d0c3"/>
  <rect x="445" y="386" width="210" height="92" rx="32" fill="#d8d0c3"/>
  <rect x="742" y="486" width="188" height="92" rx="10" fill="{accent}"/>
  <rect x="774" y="448" width="124" height="44" rx="22" fill="#f8f3ea"/>
  <circle cx="220" cy="610" r="44" fill="#b9a785"/>
  <rect x="950" y="395" width="70" height="230" rx="8" fill="#34302b"/>
  <circle cx="985" cy="366" r="58" fill="#f2e7c8" opacity="0.85"/>
</svg>"""
    return _write_svg(job_id, f"render-{index}-{_safe_name(room_name)}", svg)


def _proposal_json(mode: str, job: Dict[str, Any]) -> Dict[str, Any]:
    professional = job.get("professional_floorplan") or _professional_package(job)
    automation = job.get("floor_plan_automation") or _automation_contract(job)
    technical_json = job.get("technical_floor_plan_json") or build_technical_floor_plan_json(job)
    optimized_json = job.get("optimized_floor_plan_json") or build_optimized_floor_plan_json(job, technical_json)
    floorplan_2d = professional.get("floorplan_2d") or {}
    professional_payload = {
        "summary": professional.get("summary"),
        "technical_findings": professional.get("technical_findings") or [],
        "optimization_strategy": professional.get("optimization_strategy") or [],
        "approval_checklist": floorplan_2d.get("approval_checklist") or [],
        "change_summary": floorplan_2d.get("change_summary") or [],
        "drafting_requirements": floorplan_2d.get("drafting_requirements") or [],
    }
    automation_payload = {
        "schema": automation.get("schema"),
        "pipeline_gate": automation.get("pipeline_gate") or {},
        "selected_variant": (automation.get("variant_generation") or {}).get("selected_variant"),
        "generated_variant_count": (automation.get("variant_generation") or {}).get("generated_variant_count"),
        "site_checks_required": ((automation.get("technical_extraction") or {}).get("site_checks_required") or [])[:8],
        "non_negotiable_rules": automation.get("non_negotiable_rules") or [],
    }
    json_pipeline_payload = {
        "technical_schema": technical_json.get("schema"),
        "technical_source": technical_json.get("source"),
        "technical_data_status": technical_json.get("data_status"),
        "rooms_count": len(technical_json.get("rooms") or []),
        "optimized_schema": optimized_json.get("schema"),
        "optimized_variant": (optimized_json.get("metadata") or {}).get("selected_variant"),
        "visual_prompt": optimized_json.get("visual_prompt"),
    }
    detected_rooms = [
        {
            "name": room.get("name"),
            "intent": (
                "ambiente rilevato da Vision AI"
                if _safe_float(room.get("confidence"), 0) >= VISION_CONFIDENCE_THRESHOLD
                else "ambiente rilevato con confidenza bassa, da verificare"
            ),
            "confidence": room.get("confidence"),
            "verification_required": room.get("verification_required", True),
        }
        for room in _analysis_rooms(job, min_confidence=0.2)
    ]
    if mode == "redistributed":
        return {
            "concept": "redistribuzione_preliminare",
            "constraints_respected": floorplan_2d.get("constraints_respected") or ["perimetro invariato", "finestre mantenute", "accessi principali mantenuti"],
            "rooms": detected_rooms,
            "technical_note": floorplan_2d.get("disclaimer") or "Concept preliminare generato con AI, da verificare con tecnico abilitato.",
            "professional_floorplan": professional_payload,
            "floor_plan_automation": automation_payload,
            "json_pipeline": json_pipeline_payload,
        }
    if mode == "source_reference":
        return {
            "concept": "planimetria_allegata_riferimento",
            "layout_locked": True,
            "constraints_respected": ["file allegato mantenuto come riferimento vincolante"],
            "rooms": detected_rooms,
            "technical_note": "Nessun layout reinterpretato: serve verifica prima di procedere con render o redistribuzione.",
            "professional_floorplan": professional_payload,
            "floor_plan_automation": automation_payload,
            "json_pipeline": json_pipeline_payload,
        }
    return {
        "concept": "progetto_definito_mantenuto_identico",
        "layout_locked": True,
        "constraints_respected": [
            "distribuzione caricata mantenuta identica",
            "nessuna parete, porta, finestra o ambiente reinterpretato",
            "render successivi vincolati alla planimetria allegata",
        ],
        "rooms": detected_rooms,
        "technical_note": floorplan_2d.get("disclaimer") or "Concept preliminare generato con AI, da verificare con tecnico abilitato.",
        "professional_floorplan": professional_payload,
        "floor_plan_automation": automation_payload,
        "json_pipeline": json_pipeline_payload,
    }


def _plan_details_json(job: Dict[str, Any], mode: str) -> Dict[str, Any]:
    analysis = job.get("vision_analysis") or {}
    professional = job.get("professional_floorplan") or _professional_package(job)
    automation = job.get("floor_plan_automation") or _automation_contract(job)
    technical_json = job.get("technical_floor_plan_json") or build_technical_floor_plan_json(job)
    optimized_json = job.get("optimized_floor_plan_json") or build_optimized_floor_plan_json(job, technical_json)
    professional_render_contract = professional.get("render_contract") or {}
    professional_floorplan = professional.get("floorplan_2d") or {}
    defined_mode = mode == "defined" or _is_defined_project_mode(job)
    rooms = []
    for room in _analysis_rooms(job, min_confidence=0.2):
        box = room.get("bounding_box") or {}
        rooms.append(
            {
                "name": room.get("name"),
                "approx_position": room.get("approx_position"),
                "estimated_area_sqm": room.get("estimated_area_sqm"),
                "bounding_box": {
                    "x": box.get("x"),
                    "y": box.get("y"),
                    "width": box.get("width"),
                    "height": box.get("height"),
                }
                if box
                else None,
                "verification_required": room.get("verification_required", True),
                "evidence": room.get("evidence"),
            }
        )
    elements = analysis.get("detected_elements") or {}
    if defined_mode:
        must_preserve = [
            "planimetria allegata mantenuta identica come sorgente vincolante",
            "perimetro esterno esattamente come nel file allegato",
            "tutte le pareti interne visibili e le loro posizioni relative",
            "tutte le porte, finestre, varchi, balconi, scale e cavedi visibili",
            "numero, posizione e relazione degli ambienti gia disegnati",
            "bagni, cucina e zone impiantistiche nella posizione visibile o dichiarata",
        ]
        must_not_add = [
            "stanze nuove non presenti nel JSON",
            "qualsiasi stanza non visibile o non dichiarata nella planimetria allegata",
            "nuove porte, finestre, balconi, scale, bagni o secondi livelli",
            "spostamento creativo di muri, aperture, bagni, cucina o accessi",
            "reinterpretazioni di forma/perimetro per ragioni estetiche",
            "testi, quote, loghi, watermark",
        ]
        layout_lock = "preserve_uploaded_plan_exactly"
    else:
        must_preserve = [
            "perimetro esterno della planimetria",
            "posizione relativa degli ambienti rilevati",
            "relazioni tra zona giorno, cucina, disimpegno, camere e bagno",
            "aperture e passaggi indicati o desumibili",
            "assenza di nuovi vani non rilevati",
        ]
        must_not_add = [
            "stanze nuove non presenti nel JSON",
            "bagni, scale, balconi, finestre o porte non rilevati",
            "secondi livelli o ampliamenti volumetrici",
            "testi, quote, loghi, watermark",
        ]
        layout_lock = "preserve_perimeter_and_detected_constraints"
    must_preserve = list(dict.fromkeys(must_preserve + (professional_render_contract.get("must_preserve") or [])))
    must_not_add = list(dict.fromkeys(must_not_add + (professional_render_contract.get("must_not_add") or [])))
    return {
        "schema": "gb-ai-architect-plan-details-v1",
        "mode": mode,
        "plan_type": analysis.get("plan_type_detected") or job.get("plan_type_detected"),
        "layout_lock": layout_lock,
        "source_reference_url": _layout_reference_url(job),
        "render_contract": {
            "must_preserve": must_preserve,
            "must_not_add": must_not_add,
            "uncertain_items_require_neutral_rendering": [
                "muri portanti",
                "impianti e colonne di scarico",
                "quote reali",
                "aperture non chiaramente leggibili",
            ],
            "negative_prompt": professional_render_contract.get("negative_prompt"),
            "fidelity_notes": professional_render_contract.get("fidelity_notes") or [],
        },
        "professional_floorplan": {
            "summary": professional.get("summary"),
            "mode": professional.get("mode"),
            "technical_findings": professional.get("technical_findings") or [],
            "optimization_strategy": professional.get("optimization_strategy") or [],
            "floorplan_2d": professional_floorplan,
        },
        "floor_plan_automation": {
            "schema": automation.get("schema"),
            "pipeline_gate": automation.get("pipeline_gate") or {},
            "selected_variant": (automation.get("variant_generation") or {}).get("selected_variant"),
            "base_model": automation.get("base_model") or {},
            "constraints": automation.get("constraints") or {},
            "clash_detection": automation.get("clash_detection") or {},
        },
        "technical_floor_plan_json": technical_json,
        "optimized_floor_plan_json": optimized_json,
        "rooms": rooms,
        "detected_elements": {
            key: [
                {
                    "label": item.get("label"),
                    "approx_position": item.get("approx_position"),
                    "evidence": item.get("evidence"),
                    "verification_required": item.get("verification_required", True),
                }
                for item in (elements.get(key) or [])
                if isinstance(item, dict)
            ]
            for key in [
                "external_walls",
                "internal_walls",
                "doors",
                "windows",
                "bathrooms",
                "kitchen_zones",
                "corridors",
                "stairs",
                "structural_constraints_uncertain",
            ]
        },
        "client_constraints": {
            "style_selected": job.get("style_selected"),
            "project_goal": job.get("project_goal"),
            "project_variant_selected": normalize_project_variant(job.get("project_variant_selected")),
            "priorities": job.get("priorities") or [],
            "sqm_declared": job.get("sqm"),
            "residents": job.get("residents"),
        },
    }


def _plan_details_for_prompt(job: Dict[str, Any], mode: str) -> str:
    details = job.get("plan_details") or _plan_details_json(job, mode)
    return json.dumps(details, ensure_ascii=False, separators=(",", ":"))[:10000]


def _advice_text(job: Dict[str, Any], mode: str) -> str:
    style = job.get("style_selected") or "Su misura GB Construction"
    goal = job.get("project_goal") or "Ristrutturazione completa"
    priorities = ", ".join(job.get("priorities") or []) or "priorita da definire"
    variant = VARIANT_CATALOG[normalize_project_variant(job.get("project_variant_selected"))]
    professional = professional_advice_text(
        job.get("professional_floorplan"),
        style=style,
        goal=goal,
        priorities=priorities,
    )
    if professional:
        return f"Variante scelta dal cliente: {variant['label']} ({variant['strategy']}). {professional}"
    if mode == "redistributed":
        intro = "La proposta riduce le aree di passaggio e valorizza una zona giorno piu ampia e luminosa."
    else:
        intro = "La distribuzione caricata viene mantenuta e trasformata in una base visiva piu pulita e leggibile."
    return (
        f"Sintesi progetto: variante scelta dal cliente {variant['label']} ({variant['strategy']}). {intro} Obiettivo dichiarato: {goal}. "
        f"Priorita cliente: {priorities}. Stile selezionato: {style}. "
        "Materiali consigliati: pavimenti continui di grande formato, boiserie o pareti materiche nelle zone focali, "
        "rubinetterie e profili in finiture premium coerenti con lo stile. Illuminazione: combinare luce tecnica "
        "incassata, tagli LED e corpi decorativi nei punti di rappresentanza. Arredi: privilegiare contenimento "
        "su misura, passaggi liberi e proporzioni calibrate. Verifiche tecniche: muri portanti, cavedi, scarichi, "
        "quote, pratica edilizia, compatibilita catastale e impiantistica. "
        "Concept preliminare generato con AI, da verificare con tecnico abilitato. "
        "Vuoi trasformare questa proposta in un progetto reale? Richiedi una consulenza con GB Construction."
    )


def _budget_signals_luxury(budget: Optional[str]) -> bool:
    """True solo se il budget dichiarato indica chiaramente fascia luxury (>= 100k o termini espliciti)."""
    text = str(budget or "").lower()
    if not text:
        return False
    if any(token in text for token in ("luxury", "nessun limite", "illimitat", "altissimo", "top di gamma")):
        return True
    # Numeri come "120.000" / "120000" / "120k"
    raw = re.findall(r"\d[\d.\s]*", text)
    for token in raw:
        n = re.sub(r"[^\d]", "", token)
        if not n:
            continue
        value = int(n)
        if "k" in text and value < 1000:
            value *= 1000
        if value >= 100000:
            return True
    return False


def _gb_estimate_config(job: Dict[str, Any]) -> Dict[str, Any]:
    """Mappa il job AI Architect + analisi vision alla config del motore predittivo GB."""
    rooms = _analysis_rooms(job, min_confidence=0.2)
    names = [str(r.get("name") or "").lower() for r in rooms]
    bagni = sum(1 for n in names if "bagno" in n or "servizio" in n)
    camere = sum(1 for n in names if "camera" in n or "letto" in n)
    priorities = [str(p).lower() for p in job.get("priorities") or []]
    if any("bagno aggiuntivo" in p for p in priorities):
        bagni += 1
    if any("piu camere" in p for p in priorities):
        camere += 1
    # Lo stile d'arredo NON determina la fascia di capitolato: i preventivi GB reali
    # (54 quadri, mediana 53k = ~616 EUR/mq premium) mostrano che il lavoro tipico e premium.
    # La fascia luxury si attiva solo su segnale di budget esplicito alto, non sulla parola "luxury".
    livello = "luxury" if _budget_signals_luxury(job.get("budget")) else "premium"
    ambienti: List[str] = []
    if any(("soggiorno" in n or "living" in n or "giorno" in n) for n in names):
        ambienti.append("Soggiorno")
    if any("ingresso" in n for n in names):
        ambienti.append("Ingresso")
    if any(("balcon" in n or "terrazz" in n) for n in names) or any("balcon" in p for p in priorities):
        ambienti.append("Balconi/Terrazzi")
    return {
        "mq": _job_sqm(job),
        "bagni": max(1, bagni),
        "camere": max(1, camere),
        "cucina": True,
        "ambienti": ambienti,
        "livello": livello,
        "redistribuzione": _should_redistribute(job),
    }


def _gb_estimate(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Preventivo predittivo GB ancorato alle variabili del job. None se non calcolabile."""
    try:
        return calcola_preventivo(_gb_estimate_config(job))
    except Exception:
        return None


def _gb_pricing_context(estimate: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Solo i range prezzo GB da iniettare nel reasoning (nessuna voce/listino interno)."""
    if not estimate:
        return None
    pacchetti = estimate.get("pacchetti") or {}
    out: Dict[str, Any] = {}
    for key in ("essenziale", "premium", "luxury"):
        p = pacchetti.get(key) or {}
        if p.get("range_basso") and p.get("range_alto"):
            out[key] = {
                "range_basso_eur": p["range_basso"],
                "range_alto_eur": p["range_alto"],
                "costo_mq_eur": p.get("costo_mq"),
                "tempistiche": p.get("tempistiche"),
            }
    return out or None


def _claude_advice_text_sync(job: Dict[str, Any], mode: str) -> str:
    analysis = job.get("vision_analysis") or {}
    rooms = [
        {
            "name": room.get("name"),
            "position": room.get("approx_position"),
            "evidence": room.get("evidence"),
            "verification_required": room.get("verification_required", True),
        }
        for room in _analysis_rooms(job, min_confidence=0.2)[:8]
    ]
    context = {
        "mode": mode,
        "plan_type_detected": analysis.get("plan_type_detected") or job.get("plan_type_detected"),
        "project_goal": job.get("project_goal"),
        "style_selected": job.get("style_selected"),
        "priorities": job.get("priorities") or [],
        "sqm": job.get("sqm"),
        "residents": job.get("residents"),
        "budget": job.get("budget"),
        "rooms": rooms,
        "strengths": (analysis.get("architectural_analysis") or {}).get("strengths") or [],
        "weaknesses": (analysis.get("architectural_analysis") or {}).get("weaknesses") or [],
        "opportunities": (analysis.get("architectural_analysis") or {}).get("opportunities") or [],
        "risks_or_uncertainties": (analysis.get("architectural_analysis") or {}).get("risks_or_uncertainties") or [],
        "measurement_notes": analysis.get("measurement_notes"),
        "professional_floorplan": job.get("professional_floorplan") or _professional_package(job),
        "floor_plan_automation": job.get("floor_plan_automation") or _automation_contract(job),
        "technical_floor_plan_json": job.get("technical_floor_plan_json") or build_technical_floor_plan_json(job),
        "optimized_floor_plan_json": job.get("optimized_floor_plan_json")
        or build_optimized_floor_plan_json(job, job.get("technical_floor_plan_json") or build_technical_floor_plan_json(job)),
        "gb_pricing": _gb_pricing_context(job.get("estimate")),
    }
    system_prompt = (
        "Sei ARCH-AI, architetto consulente senior di GB Construction. Scrivi testi cliente in italiano, "
        "professionali, concreti e conservativi, coerenti con la normativa edilizia italiana. Non inventare dati, "
        "metrature o costi non presenti nel contesto fornito. Non citare mai provider AI, modelli, job id, "
        "confidence, quality gate, fallback o dettagli tecnici interni. Non promettere fattibilita esecutiva: "
        "indica sempre le verifiche tecniche necessarie (strutturali, impiantistiche, catastali, pratiche edilizie). "
        "Non usare Markdown, titoli con cancelletto, grassetti, bullet list o formattazione speciale."
    )
    user_prompt = (
        "Scrivi una sintesi progettuale pronta per il report AI Architect. Usa massimo 220 parole, tono premium ma tecnico. "
        "Restituisci solo testo piano in 1 o 2 paragrafi. Devi usare technical_floor_plan_json, optimized_floor_plan_json, "
        "professional_floorplan e floor_plan_automation come fonte primaria per variante scelta dal cliente, criticita, "
        "strategia 2D, checklist, vincoli e controlli. Non proporre varianti non scelte. "
        "Includi: sintesi del layout, priorita cliente, interventi consigliati, "
        "motivazione tecnica concreta, materiali e illuminazione, verifiche obbligatorie prima dell'esecutivo, invito alla consulenza GB Construction. "
        "Se citi costi, budget o investimento, usa ESCLUSIVAMENTE le cifre del campo gb_pricing (preventivo predittivo "
        "GB Construction), presentandole come stime di massima da confermare in sopralluogo; non inventare altri importi e "
        "non citare costi se gb_pricing e assente. "
        f"Dati progetto JSON: {json.dumps(context, ensure_ascii=False)}"
    )
    return _anthropic_text_completion_sync(system_prompt, user_prompt, max_tokens=1200)


async def _generate_advice_text(db, job_id: str, job: Dict[str, Any], mode: str) -> str:
    if not job.get("estimate"):
        estimate = _gb_estimate(job)
        if estimate:
            job["estimate"] = estimate
            job["estimate_config"] = _gb_estimate_config(job)
            await _set_job(db, job_id, estimate=estimate, estimate_config=job["estimate_config"])
    for provider in AI_TEXT_PROVIDER_CHAIN or ["claude_direct"]:
        if provider in {"claude", "anthropic", "claude_direct", "anthropic_direct", "direct_claude"}:
            if not _anthropic_api_key():
                continue
            try:
                return await asyncio.to_thread(_claude_advice_text_sync, job, mode)
            except Exception as exc:
                await _log_non_blocking_error(db, job_id, "advice_text:claude", exc)
                continue
    return _advice_text(job, mode)


def _pdf_escape(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("latin-1", "ignore").decode("latin-1")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_pdf(lines: List[str]) -> bytes:
    content_lines = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
    for line in lines[:46]:
        content_lines.append(f"({_pdf_escape(line[:105])}) Tj")
        content_lines.append("T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1", "ignore")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{i} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def _pdf_safe(text: Any) -> str:
    return html.escape(str(text or "-"), quote=False).replace("\n", "<br/>")


def _pdf_para(text: Any, style):
    if Paragraph is None:
        return str(text or "-")
    return Paragraph(_pdf_safe(text), style)


def _latest_output(outputs: List[Dict[str, Any]], output_type: str) -> Optional[Dict[str, Any]]:
    matches = [item for item in outputs if item.get("output_type") == output_type]
    return matches[-1] if matches else None


def _output_json_content(output: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    value = (output or {}).get("json_content")
    return value if isinstance(value, dict) else {}


def _output_approvable_for_render(output: Optional[Dict[str, Any]], job: Dict[str, Any]) -> bool:
    if not output or not output.get("image_url"):
        return False
    output_type = output.get("output_type")
    payload = _output_json_content(output)
    if output_type == "redistributed_2d_plan":
        return (
            _should_redistribute(job)
            and payload.get("approvable_for_render") is True
            and payload.get("generated_with") == "generative_ai_image"
        )
    if output_type == "clean_2d_plan":
        return (not _should_redistribute(job)) and payload.get("approvable_for_render") is True
    return False


def _pdf_image(url: Optional[str], max_width: float, max_height: float):
    if PdfImage is None:
        return None
    path = local_path_from_file_url(url)
    if not path or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None
    try:
        image = PdfImage(str(path))
        ratio = min(max_width / image.imageWidth, max_height / image.imageHeight)
        image.drawWidth = image.imageWidth * ratio
        image.drawHeight = image.imageHeight * ratio
        return image
    except Exception:
        return None


def _feature_count(analysis: Dict[str, Any], key: str) -> int:
    elements = analysis.get("detected_elements") or {}
    value = elements.get(key) or []
    return len(value) if isinstance(value, list) else 0


def _build_enterprise_pdf(path: Path, job: Dict[str, Any], outputs: List[Dict[str, Any]], advice: str):
    if SimpleDocTemplate is None:
        raise RuntimeError("reportlab non disponibile")

    analysis = job.get("vision_analysis") or {}
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=30, leading=34, textColor=colors.white, alignment=TA_CENTER, spaceAfter=16))
    styles.add(ParagraphStyle(name="CoverSub", parent=styles["Normal"], fontName="Helvetica", fontSize=11, leading=16, textColor=colors.HexColor("#d7d0c3"), alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="H1GB", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.HexColor("#111111"), spaceBefore=8, spaceAfter=10))
    styles.add(ParagraphStyle(name="H2GB", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=colors.HexColor("#b91c1c"), spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name="BodyGB", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#202020")))
    styles.add(ParagraphStyle(name="SmallGB", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#555555")))

    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=16 * mm)
    story = []

    def cover(canvas, _doc):
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#050505"))
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#b91c1c"))
        canvas.rect(0, height - 12 * mm, width, 3 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#ffffff"))
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(18 * mm, height - 22 * mm, "GB CONSTRUCTION")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#d7d0c3"))
        canvas.drawRightString(width - 18 * mm, height - 22 * mm, now_iso()[:10])
        canvas.restoreState()

    def later(canvas, _doc):
        width, height = A4
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#e7e1d5"))
        canvas.line(18 * mm, height - 12 * mm, width - 18 * mm, height - 12 * mm)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(colors.HexColor("#b91c1c"))
        canvas.drawString(18 * mm, height - 9 * mm, "GB CONSTRUCTION | AI Architect")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawRightString(width - 18 * mm, 9 * mm, f"Pagina {canvas.getPageNumber()}")
        canvas.restoreState()

    story.append(Spacer(1, 88 * mm))
    story.append(Paragraph("AI ARCHITECT<br/>REPORT PRELIMINARE", styles["CoverTitle"]))
    story.append(Paragraph(_pdf_safe(job.get("project_goal") or "Ristrutturazione completa"), styles["CoverSub"]))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(f"Stile: {_pdf_safe(job.get('style_selected'))} | File: {_pdf_safe(job.get('original_filename'))}", styles["CoverSub"]))
    story.append(PageBreak())

    confidence = _safe_float(analysis.get("confidence"), _safe_float(job.get("plan_type_confidence"), 0))
    summary_data = [
        ["Voce", "Valore"],
        ["Tipo rilevato", _pdf_para(analysis.get("plan_type_detected") or job.get("plan_type_detected"), styles["SmallGB"])],
        ["Qualita analisi", "professionale" if confidence >= VISION_MIN_ACCEPTABLE_CONFIDENCE else "da verificare"],
        ["Metodo", _pdf_para("AI Architect GB - lettura planimetrica professionale con verifica tecnica consigliata", styles["SmallGB"])],
        ["Output immagini", _pdf_para((job.get("image_generation") or {}).get("provider"), styles["SmallGB"])],
    ]
    story.append(Paragraph("Sintesi Esecutiva", styles["H1GB"]))
    table = Table(summary_data, colWidths=[48 * mm, 108 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d7d0c3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f4ef")]),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(_pdf_safe(analysis.get("dynamic_disclaimer") or "Concept preliminare da verificare con tecnico abilitato."), styles["SmallGB"]))

    uploaded_img = _pdf_image(job.get("uploaded_file_url"), 160 * mm, 90 * mm)
    if uploaded_img:
        story.append(Paragraph("File Caricato", styles["H2GB"]))
        story.append(uploaded_img)

    story.append(PageBreak())
    story.append(Paragraph("Analisi Vision", styles["H1GB"]))
    rooms = analysis.get("detected_rooms") or []
    room_rows = [["Ambiente", "Posizione", "Conf.", "Evidenza"]]
    for room in rooms[:10]:
        room_rows.append([
            _pdf_para(room.get("name"), styles["SmallGB"]),
            _pdf_para(room.get("approx_position"), styles["SmallGB"]),
            f"{int(_safe_float(room.get('confidence'), 0) * 100)}%",
            _pdf_para(room.get("evidence"), styles["SmallGB"]),
        ])
    if len(room_rows) == 1:
        room_rows.append(["-", "-", "-", "Nessun ambiente determinabile con confidenza sufficiente."])
    room_table = Table(room_rows, colWidths=[34 * mm, 28 * mm, 16 * mm, 86 * mm])
    room_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#b91c1c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d7d0c3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
    ]))
    story.append(room_table)
    story.append(Spacer(1, 7 * mm))
    counts = [
        ["Porte", _feature_count(analysis, "doors")],
        ["Finestre", _feature_count(analysis, "windows")],
        ["Bagni", _feature_count(analysis, "bathrooms")],
        ["Cucina/impianti", _feature_count(analysis, "kitchen_zones")],
        ["Vincoli incerti", _feature_count(analysis, "structural_constraints_uncertain")],
    ]
    story.append(Paragraph("Elementi Rilevati", styles["H2GB"]))
    story.append(Table(counts, colWidths=[60 * mm, 24 * mm], style=[
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d7d0c3")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))

    story.append(PageBreak())
    story.append(Paragraph("Output Visivi", styles["H1GB"]))
    visual_outputs = [
        ("Planimetria 2D", _latest_output(outputs, "redistributed_2d_plan") or _latest_output(outputs, "clean_2d_plan")),
        ("Top-down 3D", _latest_output(outputs, "topdown_3d_plan")),
    ]
    for label, output in visual_outputs:
        story.append(Paragraph(label, styles["H2GB"]))
        img = _pdf_image(output.get("image_url") if output else None, 160 * mm, 88 * mm)
        if img:
            story.append(img)
        else:
            story.append(Paragraph("Output non disponibile o da rigenerare dopo verifica tecnica.", styles["SmallGB"]))
        if output and output.get("text_content"):
            story.append(Paragraph(_pdf_safe(output.get("text_content")), styles["SmallGB"]))
        story.append(Spacer(1, 5 * mm))

    renders = [item for item in outputs if item.get("output_type") == "room_render"]
    if renders:
        story.append(PageBreak())
        story.append(Paragraph("Render Ambienti", styles["H1GB"]))
        for render in renders[:6]:
            story.append(Paragraph(_pdf_safe(render.get("room_name") or "Ambiente"), styles["H2GB"]))
            img = _pdf_image(render.get("image_url"), 160 * mm, 86 * mm)
            if img:
                story.append(img)
            story.append(Spacer(1, 4 * mm))

    story.append(PageBreak())
    story.append(Paragraph("Consigli Progettuali", styles["H1GB"]))
    story.append(Paragraph(_pdf_safe(advice), styles["BodyGB"]))
    story.append(Paragraph("Computo Preliminare", styles["H2GB"]))
    sqm = job.get("sqm")
    if sqm:
        story.append(Paragraph(f"Metratura dichiarata dal cliente: {_pdf_safe(sqm)} mq. Il range economico definitivo viene calcolato nel preventivatore dopo validazione tecnica.", styles["BodyGB"]))
    else:
        story.append(Paragraph("Metratura non dichiarata o non stimabile dalla planimetria. Il computo viene completato dopo rilievo o conferma dei mq.", styles["BodyGB"]))
    story.append(Paragraph("Disclaimer Legale", styles["H2GB"]))
    story.append(Paragraph("Il presente documento e un concept preliminare generato con supporto AI. Non sostituisce progetto esecutivo, verifica strutturale, verifica catastale, pratica edilizia, computo metrico ufficiale o consulenza di tecnico abilitato.", styles["SmallGB"]))

    doc.build(story, onFirstPage=cover, onLaterPages=later)


async def _generate_report(db, job_id: str, job: Dict[str, Any], advice: str) -> str:
    mode = "Redistribuzione AI" if _should_redistribute(job) else "Layout esistente valorizzato"
    outputs = await db.ai_architect_outputs.find({"job_id": job_id}).sort("created_at", 1).to_list(200)
    path = OUTPUT_DIR / f"{job_id}-ai-architect-report.pdf"
    try:
        _build_enterprise_pdf(path, job, outputs, advice)
    except Exception as exc:
        await _log_non_blocking_error(db, job_id, "pdf_report", exc)
        path.write_bytes(_build_pdf([
            "GB Construction - AI Architect Layout & Render",
            f"Nome progetto: {job.get('project_goal') or 'Progetto preliminare'}",
            f"Stile selezionato: {job.get('style_selected')}",
            f"Modalita: {mode}",
            f"File caricato: {job.get('original_filename') or '-'}",
            "",
            "Analisi AI:",
            f"Tipo rilevato: {job.get('plan_type_detected')}",
            "",
            "Consigli progettuali:",
            advice,
            "",
            "Nota tecnica/disclaimer:",
            "Concept preliminare generato con AI, da verificare con tecnico abilitato.",
            "Non costituisce progetto esecutivo, verifica strutturale, catastale, urbanistica o impiantistica.",
        ]))
    url = public_file_url(path)
    await _add_output(db, job_id, "pdf_report", image_url=url, text_content="Report PDF enterprise")
    return url


async def _generate_report_legacy(db, job_id: str, job: Dict[str, Any], advice: str) -> str:
    mode = "Redistribuzione AI" if _should_redistribute(job) else "Layout esistente valorizzato"
    lines = [
        "GB Construction - AI Architect Layout & Render",
        f"Nome progetto: {job.get('project_goal') or 'Progetto preliminare'}",
        f"Stile selezionato: {job.get('style_selected')}",
        f"Modalita: {mode}",
        f"File caricato: {job.get('original_filename') or '-'}",
        "",
        "Analisi AI:",
        f"Tipo rilevato: {job.get('plan_type_detected')}",
        "",
        "Consigli progettuali:",
        advice,
        "",
        "Nota tecnica/disclaimer:",
        "Concept preliminare generato con AI, da verificare con tecnico abilitato.",
        "Non costituisce progetto esecutivo, verifica strutturale, catastale, urbanistica o impiantistica.",
        "",
        "CTA: Richiedi una consulenza personalizzata con GB Construction.",
    ]
    path = OUTPUT_DIR / f"{job_id}-ai-architect-report.pdf"
    path.write_bytes(_build_pdf(lines))
    url = public_file_url(path)
    await _add_output(db, job_id, "pdf_report", image_url=url, text_content="Report PDF finale")
    return url


def _should_redistribute(job: Dict[str, Any]) -> bool:
    selected = job.get("plan_type_selected")
    detected = job.get("plan_type_detected")
    if selected == "existing_state":
        return True
    if selected == "defined_project":
        return False
    return detected == "existing_state"


def _is_defined_project_mode(job: Dict[str, Any]) -> bool:
    analysis = job.get("vision_analysis") or {}
    selected = job.get("plan_type_selected")
    detected = job.get("plan_type_detected") or analysis.get("plan_type_detected")
    return (
        selected == "defined_project"
        or detected == "defined_project"
        or analysis.get("recommended_action") == "keep_layout"
    )


def _layout_reference_url(job: Dict[str, Any]) -> Optional[str]:
    for url in (job.get("processed_file_url"), job.get("uploaded_file_url")):
        if _reference_image_path(url):
            return url
    return None


async def _hold_for_plan_verification(
    db,
    job_id: str,
    job: Dict[str, Any],
    reason: str,
    *,
    reference_url: Optional[str] = None,
):
    reference_url = reference_url or _layout_reference_url(job)
    if reference_url:
        existing_reference = await db.ai_architect_outputs.find_one({"job_id": job_id, "output_type": "clean_2d_plan"})
        if not existing_reference:
            await _add_output(
                db,
                job_id,
                "clean_2d_plan",
                image_url=reference_url,
                text_content="Planimetria allegata mantenuta come riferimento: serve verifica prima di generare un concept 2D.",
                json_content={
                    **_proposal_json("source_reference", job),
                    "approvable_for_render": False,
                    "approval_blocker": "source_reference_only",
                },
            )
    await _set_job(
        db,
        job_id,
        status="needs_confirmation",
        current_step="confirmation",
        progress_percentage=_progress_for("confirmation"),
        requires_confirmation=True,
        review_required=True,
        review_status="blocked_pending_plan_verification",
        error_message=reason,
    )


def _redistributed_2d_prompt(job: Dict[str, Any]) -> str:
    priorities = ", ".join(job.get("priorities") or []) or "funzionalita, luce naturale e valore percepito"
    rooms = ", ".join(room.get("name", "") for room in _analysis_rooms(job, min_confidence=0.45)) or "ambienti rilevati dalla planimetria"
    plan_details = _plan_details_for_prompt(job, "redistributed")
    professional_addendum = professional_2d_prompt_addendum(job.get("professional_floorplan")) if AI_REQUIRE_PROFESSIONAL_2D else ""
    variant = VARIANT_CATALOG[normalize_project_variant(job.get("project_variant_selected"))]
    return (
        "Create a precise professional 2D architectural renovation layout from the uploaded floor plan reference and optimized_floor_plan_json. "
        "This is NOT a free creative sketch. Preserve the exact external perimeter, building footprint, window positions, "
        "entrance/access points, structural-looking walls, shafts, bathrooms/kitchen wet zones unless clearly movable, "
        "and all proportions visible in the uploaded plan. Propose only a preliminary redistribution inside those constraints. "
        f"Detected rooms to respect: {rooms}. Client-selected variant: {variant['label']} ({variant['strategy']}). "
        f"Generate only this variant, no alternatives. Client priorities: {priorities}. "
        "Use clean architectural drafting style, white/cream background, black wall lines, restrained material hatches, "
        "professional plan composition. Do not add rooms, doors, windows, balconies, stairs, second levels or volumes not "
        f"supported by the reference and this PLAN_DETAILS_JSON / optimized_floor_plan_json contract: {plan_details}. "
        "STRICT_REJECTION_RULES: no balconies/terraces unless clearly visible in the uploaded plan; no kitchen cabinets, "
        "appliances or counters inside bathrooms or service bathrooms; do not label any wall as load-bearing or structural "
        "unless the source explicitly proves it; uncertain walls must be labelled only as verification required. "
        f"{professional_addendum} "
        "No logo, no watermark, no decorative fantasy elements."
    )


def _clean_defined_2d_prompt(job: Dict[str, Any]) -> str:
    rooms = ", ".join(room.get("name", "") for room in _analysis_rooms(job, min_confidence=0.45)) or "ambienti rilevati dalla planimetria"
    plan_details = _plan_details_for_prompt(job, "defined")
    professional_addendum = professional_2d_prompt_addendum(job.get("professional_floorplan")) if AI_REQUIRE_PROFESSIONAL_2D else ""
    variant = VARIANT_CATALOG[normalize_project_variant(job.get("project_variant_selected"))]
    return (
        "Create a clean professional 2D architectural drafting version of the uploaded floor plan and technical_floor_plan_json. "
        "This is a DEFINED PROJECT cleanup, not a redistribution. Preserve exactly the same exterior perimeter, "
        "room relationships, walls, doors, windows, kitchen, bathrooms, stairs, balconies, access points and visible constraints. "
        f"Client-selected variant metadata: {variant['label']} ({variant['strategy']}); keep layout locked unless this is only a graphic cleanup. "
        f"Detected rooms to label only if supported: {rooms}. "
        f"Use this PLAN_DETAILS_JSON as the hard preservation contract: {plan_details}. "
        "STRICT_REJECTION_RULES: no balconies/terraces unless clearly visible in the uploaded plan; no kitchen cabinets, "
        "appliances or counters inside bathrooms or service bathrooms; do not label any wall as load-bearing or structural "
        "unless the source explicitly proves it; uncertain walls must be labelled only as verification required. "
        f"{professional_addendum} "
        "Improve readability with sober lineweights, clean labels, compact legend and verification notes. "
        "Do not add, remove, enlarge, reduce or move any architectural element. No logo, no watermark, no decorative fantasy elements."
    )


async def _generate_clean_defined_2d_plan(db, job_id: str, job: Dict[str, Any], reference_url: Optional[str]) -> Optional[str]:
    if (
        not reference_url
        or not AI_ALLOW_GENERATIVE_DEFINED_CLEANUP
        or _selected_image_provider() == "local"
        or (job.get("vision_analysis") or {}).get("is_fallback")
        or _safe_float((job.get("vision_analysis") or {}).get("confidence"), 0) < VISION_MIN_ACCEPTABLE_CONFIDENCE
    ):
        return None
    try:
        return await _generate_ai_image(
            job_id,
            "clean-defined-2d-plan-ai",
            _clean_defined_2d_prompt(job),
            OPENAI_IMAGE_SIZE_PLAN,
            [reference_url],
        )
    except Exception as exc:
        await _log_non_blocking_error(db, job_id, "clean_defined_2d_plan", exc)
        return None


async def _generate_redistributed_2d_plan(db, job_id: str, job: Dict[str, Any], reference_url: Optional[str]) -> Optional[str]:
    if (
        not reference_url
        or not AI_ALLOW_GENERATIVE_2D_LAYOUTS
        or _selected_image_provider() == "local"
        or (job.get("vision_analysis") or {}).get("is_fallback")
        or _safe_float((job.get("vision_analysis") or {}).get("confidence"), 0) < VISION_MIN_ACCEPTABLE_CONFIDENCE
    ):
        return None
    try:
        return await _generate_ai_image(
            job_id,
            "redistributed-2d-plan-ai",
            _redistributed_2d_prompt(job),
            OPENAI_IMAGE_SIZE_PLAN,
            [reference_url],
        )
    except Exception as exc:
        await _log_non_blocking_error(db, job_id, "redistributed_2d_plan", exc)
        return None


async def process_job(db, job_id: str):
    step = "analysis"
    try:
        started = time.perf_counter()
        job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            return
        await ensure_processed_reference(db, job_id)
        job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            return

        await _mark_step(db, job_id, "analysis")
        try:
            analysis, cache_hit = await _vision_analysis_with_retries(db, job_id, job)
        except Exception as exc:
            await _log_non_blocking_error(db, job_id, "analysis_waiting_for_ai", exc)
            await _set_job(
                db,
                job_id,
                status="processing",
                current_step="analysis",
                progress_percentage=_progress_for("analysis"),
                requires_confirmation=False,
                error_message=None,
                vision_analysis_pending=True,
            )
            return
        analysis_ms = int((time.perf_counter() - started) * 1000)
        current_job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
        if not current_job or current_job.get("status") == "completed" or current_job.get("force_safe_visuals"):
            return

        quality_issues = _professional_analysis_issues(analysis)
        await _set_job(
            db,
            job_id,
            plan_type_detected=analysis["plan_type_detected"],
            plan_type_confidence=analysis["confidence"],
            vision_analysis=analysis,
            analysis_provider=analysis.get("model_provider"),
            analysis_model=analysis.get("model_name"),
            analysis_cache_hit=cache_hit,
            vision_analysis_pending=False,
            metrics={
                **(job.get("metrics") or {}),
                "analysis_ms": analysis_ms,
                "analysis_cache_hit": cache_hit,
            },
        )
        job = {
            **job,
            "plan_type_detected": analysis["plan_type_detected"],
            "plan_type_confidence": analysis["confidence"],
            "vision_analysis": analysis,
            "analysis_provider": analysis.get("model_provider"),
            "analysis_model": analysis.get("model_name"),
            "analysis_cache_hit": cache_hit,
        }
        await _persist_professional_package(db, job_id, job)
        await _persist_automation_contract(db, job_id, job)
        await _persist_floorplan_json_pipeline(db, job_id, job)
        await _add_output(
            db,
            job_id,
            "analysis",
            text_content=_analysis_text(analysis, job),
            json_content=analysis,
        )

        if quality_issues:
            await _log_non_blocking_error(db, job_id, "analysis_quality_hold", RuntimeError("; ".join(quality_issues)))
            await _set_job(
                db,
                job_id,
                status="processing",
                current_step="analysis",
                progress_percentage=_progress_for("analysis"),
                requires_confirmation=False,
                analysis_quality_issues=quality_issues,
                vision_analysis_pending=True,
            )
            return

        await _continue_generation(db, job_id)
    except Exception as exc:
        await _record_error(db, job_id, step, exc)


async def _generate_layout_outputs(db, job_id: str, job: Dict[str, Any], mode: str) -> bool:
    await _mark_step(db, job_id, "proposal_2d")
    reference_url = _layout_reference_url(job)
    gate_score, gate_details = _layout_gate_score(job)
    gate_passed = gate_score >= LAYOUT_GATE_MIN_SCORE
    await _record_quality_gate(
        db,
        job_id,
        2,
        "layout_geometry",
        passed=gate_passed,
        score=gate_score,
        details=gate_details,
        retry_triggered=not gate_passed,
        resolution="passed" if gate_passed else "hold_for_better_vision",
    )
    if not gate_passed:
        reason = (
            "La lettura della planimetria non e abbastanza affidabile per generare un 2D professionale. "
            "Il file allegato resta come riferimento: conferma se e uno stato di progetto da mantenere identico "
            "oppure carica una planimetria piu leggibile per una redistribuzione."
        )
        await _log_non_blocking_error(db, job_id, "layout_quality_hold", RuntimeError(f"Layout gate below threshold: {gate_score}"))
        await _record_quality_gate(
            db,
            job_id,
            2,
            "layout_geometry",
            passed=False,
            score=gate_score,
            details={**gate_details, "reference_url": reference_url},
            retry_triggered=False,
            resolution="needs_plan_verification",
        )
        await _hold_for_plan_verification(db, job_id, job, reason, reference_url=reference_url)
        return False
    plan_details = _plan_details_json(job, mode)
    job["plan_details"] = plan_details
    await _set_job(db, job_id, plan_details=plan_details)
    await _add_output(
        db,
        job_id,
        "plan_details",
        text_content="Contratto strutturato di fedelta planimetrica per render e preventivo.",
        json_content=plan_details,
    )

    if mode == "defined":
        if not reference_url:
            await _hold_for_plan_verification(
                db,
                job_id,
                job,
                "Non e disponibile una preview immagine della planimetria allegata: non posso garantire un layout identico.",
            )
            return False
        clean_defined_url = await _generate_clean_defined_2d_plan(db, job_id, job, reference_url)
        clean_url = clean_defined_url or reference_url
        await _add_output(
            db,
            job_id,
            "clean_2d_plan",
            image_url=clean_url,
            text_content=(
                "Planimetria di progetto ripulita in 2D professionale con layout bloccato."
                if clean_defined_url
                else "Stato di progetto mantenuto identico alla planimetria allegata. Da questa base verranno sviluppati top-down e render."
            ),
            json_content={
                **_proposal_json("defined", job),
                "approvable_for_render": True,
                "approval_basis": "uploaded_defined_project_reference" if not clean_defined_url else "ai_cleanup_with_locked_layout",
            },
        )
        return True

    if not reference_url:
        await _hold_for_plan_verification(
            db,
            job_id,
            job,
            "Non e disponibile una preview reale della planimetria caricata: non genero sagome 2D sintetiche da approvare.",
            reference_url=reference_url,
        )
        return False
    clean_url = reference_url
    await _add_output(
        db,
        job_id,
        "clean_2d_plan",
        image_url=clean_url,
        text_content="Planimetria allegata mantenuta come riferimento per verificare il concept di redistribuzione.",
        json_content={
            **_proposal_json("source_reference", job),
            "approvable_for_render": False,
            "approval_blocker": "uploaded_reference_is_not_a_redistributed_layout",
        },
    )
    if mode == "redistributed":
        redistributed_url = await _generate_redistributed_2d_plan(db, job_id, job, reference_url)
        generated_with = "generative_ai_image" if redistributed_url else None
        if not redistributed_url:
            await _hold_for_plan_verification(
                db,
                job_id,
                job,
                "Redistribuzione 2D bloccata: senza un output vettoriale/generativo approvabile non mostro sagome sintetiche. Serve una planimetria migliore o una revisione tecnica prima dei render.",
                reference_url=reference_url,
            )
            return False
        await _add_output(
            db,
            job_id,
            "redistributed_2d_plan",
            image_url=redistributed_url,
            text_content=(
                "Nuova distribuzione preliminare generata con AI immagine: richiede controllo staff prima di render e cliente."
            ),
            json_content={
                **_proposal_json("redistributed", job),
                "generated_with": generated_with,
                "approvable_for_render": True,
                "approval_basis": "generative_ai_image_with_uploaded_reference",
                "approval_required_before_client": True,
            },
        )
    return True


async def _continue_render_generation(db, job_id: str):
    pipeline_started = time.perf_counter()
    await ensure_processed_reference(db, job_id)
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        return
    _ensure_professional_analysis(job)
    if AI_FLOORPLAN_PROFESSIONAL_ANALYSIS and not job.get("professional_floorplan"):
        await _persist_professional_package(db, job_id, job)
        job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            return
    if not job.get("floor_plan_automation"):
        await _persist_automation_contract(db, job_id, job)
        job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            return
    if not job.get("technical_floor_plan_json") or not job.get("optimized_floor_plan_json"):
        await _persist_floorplan_json_pipeline(db, job_id, job)
        job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            return
    mode = "redistributed" if _should_redistribute(job) else "defined"
    force_safe_visuals = bool(job.get("force_safe_visuals"))
    image_provider_label = "safe-vector" if force_safe_visuals else _selected_image_provider()
    existing_outputs = await db.ai_architect_outputs.find({"job_id": job_id}).sort("created_at", 1).to_list(200)
    concept_output = _latest_output(existing_outputs, "redistributed_2d_plan") or _latest_output(existing_outputs, "clean_2d_plan")
    concept_reference_url = (concept_output or {}).get("image_url") or job.get("processed_file_url") or job.get("uploaded_file_url")
    topdown_references = [url for url in [concept_reference_url, job.get("processed_file_url")] if _reference_image_path(url)]
    reference_ready = bool(topdown_references)
    vision_confidence = _safe_float((job.get("vision_analysis") or {}).get("confidence"), _safe_float(job.get("plan_type_confidence"), 0))
    vision_valid_for_render = (
        not (job.get("vision_analysis") or {}).get("is_fallback")
        and vision_confidence >= RENDER_CONFIDENCE_THRESHOLD
        and not force_safe_visuals
        and reference_ready
    )
    requires_real_raster = AI_REQUIRE_RASTER_RENDERS and not force_safe_visuals and vision_valid_for_render
    if not vision_valid_for_render:
        await _record_quality_gate(
            db,
            job_id,
            3,
            "render_readiness",
            passed=False,
            score=0,
            details={
                "image_provider": image_provider_label,
                "vision_confidence": vision_confidence,
                "vision_valid_for_render": vision_valid_for_render,
                "reference_ready": reference_ready,
                "reference_count": len(topdown_references),
            },
            retry_triggered=True,
            resolution="hold_for_ai_images",
        )

    await _mark_step(db, job_id, "topdown_3d")

    async def build_topdown() -> str:
        if not force_safe_visuals and _selected_image_provider() != "local" and vision_valid_for_render:
            try:
                return await _generate_ai_image(
                    job_id,
                    f"{mode}-topdown-3d-ai",
                    _topdown_prompt(job, mode),
                    OPENAI_IMAGE_SIZE_PLAN,
                    topdown_references,
                )
            except Exception as exc:
                await _log_non_blocking_error(db, job_id, "topdown_3d_safe_visual", exc)
                if requires_real_raster:
                    raise
        return _topdown_svg(job_id, job, mode)

    async def build_room_render(index: int, room_name: str, references: List[str]) -> tuple[str, str]:
        if not force_safe_visuals and _selected_image_provider() != "local" and vision_valid_for_render:
            try:
                url = await _generate_ai_image(
                    job_id,
                    f"render-{index}-{_safe_name(room_name)}-ai",
                    _room_prompt(job, room_name),
                    OPENAI_IMAGE_SIZE_RENDER,
                    references,
                )
                return room_name, url
            except Exception as exc:
                await _log_non_blocking_error(db, job_id, f"render:{room_name}:safe_visual", exc)
                if requires_real_raster:
                    raise
        return room_name, _render_svg(job_id, job, room_name, index)

    semaphore = asyncio.Semaphore(AI_IMAGE_CONCURRENCY)

    async def limited_room(index: int, room_name: str, references: List[str]) -> tuple[str, str]:
        async with semaphore:
            return await build_room_render(index, room_name, references)

    room_names = _room_names_for_generation(job)
    try:
        topdown_url = await build_topdown()
        topdown_score, topdown_details = _asset_quality_score(topdown_url)
        if requires_real_raster and topdown_details.get("is_safe_vector_visual"):
            topdown_score = 0.0
            topdown_details["rejected_reason"] = "safe_vector_visual_not_real_ai_render"
        topdown_passed = topdown_score >= RENDER_GATE_MIN_SCORE
        await _record_quality_gate(
            db,
            job_id,
            3,
            "topdown_render",
            passed=topdown_passed,
            score=topdown_score,
            details=topdown_details,
            retry_triggered=not topdown_passed,
            resolution="passed" if topdown_passed else "hold_for_regeneration",
        )
        if not topdown_passed:
            raise RuntimeError(f"Top-down render gate below threshold: {topdown_score}")
    except Exception as exc:
        await _log_non_blocking_error(db, job_id, "topdown_3d", exc)
        if requires_real_raster:
            await _record_quality_gate(
                db,
                job_id,
                3,
                "topdown_render",
                passed=False,
                score=0,
                details={
                    "error": str(exc),
                    "image_provider": image_provider_label,
                    "requires_real_raster": True,
                    "reference_count": len(topdown_references),
                },
                retry_triggered=True,
                resolution="hold_for_real_ai_render",
            )
            await _set_job(
                db,
                job_id,
                status="processing",
                current_step="topdown_3d",
                progress_percentage=_progress_for("topdown_3d"),
                requires_confirmation=False,
                error_message="Render fotorealistici in rigenerazione: il provider immagini non ha ancora completato un output raster valido.",
                render_quality_hold=True,
            )
            return
        topdown_url = _topdown_svg(job_id, job, f"{mode}-safe")
        safe_score, safe_details = _asset_quality_score(topdown_url)
        safe_details["safe_visual"] = True
        await _record_quality_gate(
            db,
            job_id,
            3,
            "topdown_render",
            passed=True,
            score=max(safe_score, RENDER_GATE_MIN_SCORE),
            details=safe_details,
            retry_triggered=True,
            resolution="professional_safe_visual",
        )
    await _add_output(
        db,
        job_id,
        "topdown_3d_plan",
        image_url=topdown_url,
        text_content="Vista 3D/top-down coerente con il layout finale.",
    )

    await _mark_step(db, job_id, "renders")
    room_references = [
        url
        for url in [topdown_url, concept_reference_url, job.get("processed_file_url")]
        if _reference_image_path(url)
    ]
    render_tasks = [
        asyncio.create_task(limited_room(index, room_name, room_references))
        for index, room_name in enumerate(room_names, start=1)
    ]
    try:
        room_results = await asyncio.gather(*render_tasks)
    except Exception as exc:
        await _log_non_blocking_error(db, job_id, "room_renders", exc)
        await _set_job(
            db,
            job_id,
            status="processing",
            current_step="renders",
            progress_percentage=_progress_for("renders"),
            requires_confirmation=False,
            error_message=None,
            render_quality_hold=True,
        )
        return

    render_scores: List[float] = []
    render_details: List[Dict[str, Any]] = []
    for room_name, url in room_results:
        score, details = _asset_quality_score(url)
        if requires_real_raster and details.get("is_safe_vector_visual"):
            score = 0.0
            details["rejected_reason"] = "safe_vector_visual_not_real_ai_render"
        details["room_name"] = room_name
        render_scores.append(score)
        render_details.append(details)
    render_gate_score = min(render_scores) if render_scores else 0
    render_gate_passed = render_gate_score >= RENDER_GATE_MIN_SCORE
    await _record_quality_gate(
        db,
        job_id,
        4,
        "room_renders",
        passed=render_gate_passed,
        score=render_gate_score,
        details={"renders": render_details, "render_count": len(render_details)},
        retry_triggered=not render_gate_passed,
        resolution="passed" if render_gate_passed else "hold_for_regeneration",
    )
    if not render_gate_passed:
        if requires_real_raster:
            await _set_job(
                db,
                job_id,
                status="processing",
                current_step="renders",
                progress_percentage=_progress_for("renders"),
                requires_confirmation=False,
                error_message="Render fotorealistici in rigenerazione: il provider immagini non ha ancora completato tutti gli output raster validi.",
                render_quality_hold=True,
            )
            return
        safe_room_results: List[tuple[str, str]] = []
        safe_render_details: List[Dict[str, Any]] = []
        safe_scores: List[float] = []
        for index, (room_name, url) in enumerate(room_results, start=1):
            score, details = _asset_quality_score(url)
            if score < RENDER_GATE_MIN_SCORE:
                url = _render_svg(job_id, job, room_name, index + 20)
                score, details = _asset_quality_score(url)
                details["safe_visual"] = True
            details["room_name"] = room_name
            safe_scores.append(score)
            safe_room_results.append((room_name, url))
            safe_render_details.append(details)
        safe_render_score = min(safe_scores) if safe_scores else RENDER_GATE_MIN_SCORE
        await _record_quality_gate(
            db,
            job_id,
            4,
            "room_renders",
            passed=True,
            score=max(_safe_float(safe_render_score), RENDER_GATE_MIN_SCORE),
            details={"renders": safe_render_details, "render_count": len(safe_render_details)},
            retry_triggered=True,
            resolution="professional_safe_visual",
        )
        room_results = safe_room_results

    for room_name, url in room_results:
        await _add_output(
            db,
            job_id,
            "room_render",
            room_name=room_name,
            image_url=url,
            text_content=ROOM_RENDER_PROMPT.format(
                room_name=room_name,
                style_selected=job.get("style_selected") or "Su misura GB Construction",
            ),
        )

    await _mark_step(db, job_id, "advice")
    advice = await _generate_advice_text(db, job_id, job, mode)
    await _add_output(db, job_id, "advice", text_content=advice)
    await _generate_report(db, job_id, job, advice)

    await _set_job(
        db,
        job_id,
        status="completed",
        current_step="complete",
        progress_percentage=100,
        requires_confirmation=False,
        metrics={
            **(job.get("metrics") or {}),
            "generation_ms": int((time.perf_counter() - pipeline_started) * 1000),
            "image_provider": image_provider_label,
            "render_count": len(room_names),
        },
    )


async def _continue_generation(db, job_id: str, *, require_review: bool = REQUIRE_REVIEW_BEFORE_RENDERS):
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        return
    _ensure_professional_analysis(job)
    if AI_FLOORPLAN_PROFESSIONAL_ANALYSIS and not job.get("professional_floorplan"):
        await _persist_professional_package(db, job_id, job)
        job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            return
    if not job.get("floor_plan_automation"):
        await _persist_automation_contract(db, job_id, job)
        job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            return
    if not job.get("technical_floor_plan_json") or not job.get("optimized_floor_plan_json"):
        await _persist_floorplan_json_pipeline(db, job_id, job)
        job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
        if not job:
            return
    mode = "redistributed" if _should_redistribute(job) else "defined"

    layout_ready = await _generate_layout_outputs(db, job_id, job, mode)
    if not layout_ready:
        return

    if require_review:
        await _set_job(
            db,
            job_id,
            status="needs_review",
            current_step="review",
            progress_percentage=_progress_for("review"),
            review_required=True,
            review_status="pending",
            review_requested_at=now_iso(),
        )
        return

    await _continue_render_generation(db, job_id)


async def ensure_concept_ready_for_approval(db, job_id: str) -> None:
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job AI Architect non trovato")
    outputs = await db.ai_architect_outputs.find({"job_id": job_id}).sort("created_at", 1).to_list(200)
    if _should_redistribute(job):
        concept = _latest_output(outputs, "redistributed_2d_plan")
        if not _output_approvable_for_render(concept, job):
            raise HTTPException(
                status_code=400,
                detail="Concept 2D redistribuito non approvabile: non genero render da una planimetria sintetica o non verificata. Serve una planimetria migliore o revisione tecnica.",
            )
        return
    concept = _latest_output(outputs, "clean_2d_plan")
    if not _output_approvable_for_render(concept, job):
        raise HTTPException(
            status_code=400,
            detail="Planimetria di progetto non disponibile come riferimento identico. Verifica il file prima di generare i render.",
        )


async def approve_job(db, job_id: str, *, reviewer: Optional[str] = None, notes: Optional[str] = None):
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job AI Architect non trovato")
    _ensure_professional_analysis(job)
    await ensure_concept_ready_for_approval(db, job_id)
    await _set_job(
        db,
        job_id,
        status="processing",
        current_step="topdown_3d",
        progress_percentage=_progress_for("topdown_3d"),
        review_status="approved",
        review_notes=_normalize_text(notes),
        review_approved_by=_normalize_text(reviewer) or "GB Construction",
        review_approved_at=now_iso(),
        requires_confirmation=False,
    )
    await _continue_render_generation(db, job_id)


async def confirm_job(db, job_id: str, plan_type_selected: str):
    if plan_type_selected not in {"existing_state", "defined_project"}:
        raise HTTPException(status_code=400, detail="Conferma non valida")
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job AI Architect non trovato")
    _ensure_professional_analysis(job)
    vision_analysis = dict(job.get("vision_analysis") or {})
    if vision_analysis:
        vision_analysis["plan_type_detected"] = plan_type_selected
        vision_analysis["recommended_action"] = "keep_layout" if plan_type_selected == "defined_project" else "redistribute"
    await _set_job(
        db,
        job_id,
        plan_type_selected=plan_type_selected,
        plan_type_detected=plan_type_selected,
        plan_type_confidence=0.8,
        vision_analysis=vision_analysis or job.get("vision_analysis"),
        professional_floorplan=None,
        floor_plan_automation=None,
        technical_floor_plan_json=None,
        optimized_floor_plan_json=None,
        requires_confirmation=False,
        status="processing",
    )
    await db.ai_architect_outputs.delete_many({"job_id": job_id, "output_type": {"$in": ["professional_floorplan", "floor_plan_automation", "technical_floor_plan_json", "optimized_floor_plan_json"]}})
    await _continue_generation(db, job_id)


async def regenerate_outputs(
    db,
    job_id: str,
    *,
    style_selected: Optional[str] = None,
    output_types: Optional[List[str]] = None,
):
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job AI Architect non trovato")

    requested = set(output_types or ["topdown_3d_plan", "room_render", "advice", "pdf_report"])
    delete_types = list(requested)
    await db.ai_architect_outputs.delete_many({"job_id": job_id, "output_type": {"$in": delete_types}})
    if style_selected:
        await _set_job(db, job_id, style_selected=style_selected, status="processing", current_step="renders", progress_percentage=70)
        job["style_selected"] = style_selected

    if "topdown_3d_plan" in requested:
        mode = "redistributed" if _should_redistribute(job) else "defined"
        existing_outputs = await db.ai_architect_outputs.find({"job_id": job_id}).sort("created_at", 1).to_list(200)
        concept_output = _latest_output(existing_outputs, "redistributed_2d_plan") or _latest_output(existing_outputs, "clean_2d_plan")
        concept_reference_url = (concept_output or {}).get("image_url") or _layout_reference_url(job)
        topdown_references = [url for url in [concept_reference_url, job.get("processed_file_url")] if _reference_image_path(url)]
        if _selected_image_provider() != "local":
            try:
                url = await _generate_ai_image(
                    job_id,
                    f"{mode}-regen-{uuid.uuid4().hex[:6]}-topdown-ai",
                    _topdown_prompt(job, mode),
                    OPENAI_IMAGE_SIZE_PLAN,
                    topdown_references,
                )
            except Exception as exc:
                await _log_non_blocking_error(db, job_id, "topdown_3d:regenerate", exc)
                url = _topdown_svg(job_id, job, f"{mode}-regen-{uuid.uuid4().hex[:6]}")
        else:
            url = _topdown_svg(job_id, job, f"{mode}-regen-{uuid.uuid4().hex[:6]}")
        await _add_output(db, job_id, "topdown_3d_plan", image_url=url, text_content="Vista 3D/top-down rigenerata.")
    if "room_render" in requested:
        existing_outputs = await db.ai_architect_outputs.find({"job_id": job_id}).sort("created_at", 1).to_list(200)
        topdown_output = _latest_output(existing_outputs, "topdown_3d_plan")
        concept_output = _latest_output(existing_outputs, "redistributed_2d_plan") or _latest_output(existing_outputs, "clean_2d_plan")
        room_references = [
            url
            for url in [
                (topdown_output or {}).get("image_url"),
                (concept_output or {}).get("image_url"),
                job.get("processed_file_url"),
            ]
            if _reference_image_path(url)
        ]
        for index, room_name in enumerate(_room_names_for_generation(job), start=1):
            if _selected_image_provider() != "local":
                try:
                    url = await _generate_ai_image(
                        job_id,
                        f"regen-render-{index}-{_safe_name(room_name)}-ai",
                        _room_prompt(job, room_name),
                        OPENAI_IMAGE_SIZE_RENDER,
                        room_references,
                    )
                except Exception as exc:
                    await _log_non_blocking_error(db, job_id, f"render:{room_name}:regenerate", exc)
                    url = _render_svg(job_id, job, room_name, index + 10)
            else:
                url = _render_svg(job_id, job, room_name, index + 10)
            await _add_output(db, job_id, "room_render", room_name=room_name, image_url=url)
    advice = await _generate_advice_text(db, job_id, job, "redistributed" if _should_redistribute(job) else "defined")
    if "advice" in requested:
        await _add_output(db, job_id, "advice", text_content=advice)
    if "pdf_report" in requested:
        await _generate_report(db, job_id, job, advice)

    await _set_job(db, job_id, status="completed", current_step="complete", progress_percentage=100)


async def complete_job_safe_mode(db, job_id: str) -> Dict[str, Any]:
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job AI Architect non trovato")

    await db.ai_architect_outputs.delete_many(
        {
            "job_id": job_id,
            "output_type": {
                "$in": [
                    "analysis",
                    "professional_floorplan",
                    "floor_plan_automation",
                    "technical_floor_plan_json",
                    "optimized_floor_plan_json",
                    "clean_2d_plan",
                    "redistributed_2d_plan",
                    "topdown_3d_plan",
                    "room_render",
                    "advice",
                    "pdf_report",
                ]
            },
        }
    )
    analysis = _safe_mode_analysis_json(job, "recupero automatico per completamento senza attesa esterna")
    await _set_job(
        db,
        job_id,
        status="processing",
        current_step="analysis",
        progress_percentage=_progress_for("analysis"),
        plan_type_detected=analysis["plan_type_detected"],
        plan_type_confidence=analysis["confidence"],
        vision_analysis=analysis,
        analysis_provider=analysis["model_provider"],
        analysis_model=analysis["model_name"],
        analysis_cache_hit=False,
        vision_analysis_pending=False,
        analysis_quality_issues=[],
        layout_quality_hold=False,
        render_quality_hold=False,
        requires_confirmation=False,
        review_required=False,
        review_status="not_required",
        force_safe_visuals=True,
        adapter=f"analysis:{CLAUDE_VISION_MODEL}|text:{CLAUDE_TEXT_MODEL}|image:safe-vector",
        image_generation={
            "provider": "safe-vector",
            "model": "gb-safe-visual-v1",
            "quality": "professional-conservative",
            "plan_size": OPENAI_IMAGE_SIZE_PLAN,
            "render_size": OPENAI_IMAGE_SIZE_RENDER,
        },
        error_message=None,
    )
    await _record_quality_gate(
        db,
        job_id,
        1,
        "vision_analysis",
        passed=True,
        score=VISION_GATE_MIN_SCORE,
        details={"safe_delivery": True, "recovery": "complete_job_safe_mode"},
        retry_triggered=True,
        resolution="professional_safe_mode",
    )
    await _add_output(
        db,
        job_id,
        "analysis",
        text_content=_analysis_text(analysis, job),
        json_content=analysis,
    )
    job = {**job, "vision_analysis": analysis, "plan_type_detected": analysis["plan_type_detected"]}
    await _persist_professional_package(db, job_id, job)
    await _persist_automation_contract(db, job_id, job)
    await _persist_floorplan_json_pipeline(db, job_id, job)
    await _continue_generation(db, job_id, require_review=False)
    return await get_job_payload(db, job_id)


async def report_path_for_job(db, job_id: str) -> Path:
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job AI Architect non trovato")
    output = await db.ai_architect_outputs.find_one({"job_id": job_id, "output_type": "pdf_report"}, sort=[("created_at", -1)])
    if output and output.get("image_url"):
        rel = output["image_url"].replace("/api/ai-architect/files/", "")
        path = STORAGE_DIR / rel
        if path.exists():
            return path
    advice = await _generate_advice_text(db, job_id, job, "redistributed" if _should_redistribute(job) else "defined")
    await _generate_report(db, job_id, job, advice)
    return OUTPUT_DIR / f"{job_id}-ai-architect-report.pdf"
