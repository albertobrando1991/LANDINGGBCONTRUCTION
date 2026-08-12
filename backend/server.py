from dotenv import load_dotenv
from pathlib import Path
import os
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR.parent / '.env')
load_dotenv(ROOT_DIR / '.env', override=True)

import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Any, Dict, Literal

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends, Query, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr, TypeAdapter, ValidationError
from document_id import ObjectId
from document_store import PostgresDocumentDatabase
import json

import auth as authlib
from predictive_engine import calcola_preventivo, lead_score
from predictive_data import COEFFICIENTI, voci_as_dicts
import seed_data
import ai_service
import ai_architect_service
import ai_credit_service
import email_service
import meta_leads_service
import api_security
import boq_service
import lead_bridge
import report_service
import db as db_pg
import tenancy
from edilos_routes import register_edilos_routes
from financial_routes import register_financial_routes
from contextlib import asynccontextmanager

# Il runtime documentale storico vive ora nello schema private di Supabase.
# L'adapter conserva l'API usata dai servizi durante il cutover, senza una
# seconda fonte dati e senza dipendenze Mongo nel processo applicativo.
db = PostgresDocumentDatabase(
    db_pg,
    os.environ.get("DEFAULT_TENANT_SLUG", "gbconstruction"),
)

app = FastAPI(title="GB Construction Lead Engine")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gb")

PIPELINE_STATI = [
    ("nuovo", "Nuovo"), ("qualificato", "Qualificato"),
    ("sopralluogo_fissato", "Sopralluogo fissato"), ("sopralluogo_fatto", "Sopralluogo fatto"),
    ("preventivo_preparazione", "Preventivo preparazione"), ("preventivo_inviato", "Preventivo inviato"),
    ("follow_up", "Follow-up"), ("in_trattativa", "In trattativa"),
    ("chiuso_vinto", "Chiuso vinto"), ("chiuso_perso", "Chiuso perso"),
]
STATO_LABELS = dict(PIPELINE_STATI)
VALID_LEVELS = {"essenziale", "premium", "luxury"}
CANTIERE_STATI = {"attivo", "in_pausa", "completato"}
CANTIERE_FASE_STATI = {"completata", "in_corso", "da_iniziare"}
DEFAULT_CANTIERE_FASI = [
    {"nome": "Demolizioni", "stato": "da_iniziare"},
    {"nome": "Impianti", "stato": "da_iniziare"},
    {"nome": "Massetti", "stato": "da_iniziare"},
    {"nome": "Pavimenti", "stato": "da_iniziare"},
    {"nome": "Finiture", "stato": "da_iniziare"},
    {"nome": "Consegna", "stato": "da_iniziare"},
]
DEFAULT_CORS_ORIGIN_REGEX = (
    r"https?://("
    r"localhost|127\.0\.0\.1|"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}"
    r"):3000"
    r"|https://(?:(?:www|app)\.)?gbconstruction\.it"
)

AUTH_LOGIN_MAX_PER_15_MIN = max(1, int(os.getenv("AUTH_LOGIN_MAX_PER_15_MIN", "10")))
PUBLIC_LEAD_MAX_PER_HOUR = max(1, int(os.getenv("PUBLIC_LEAD_MAX_PER_HOUR", "10")))
PUBLIC_BOOKING_MAX_PER_HOUR = max(1, int(os.getenv("PUBLIC_BOOKING_MAX_PER_HOUR", "10")))
EMAIL_ADDRESS_ADAPTER = TypeAdapter(EmailStr)
MAX_EMAIL_ATTACHMENT_BYTES = 15 * 1024 * 1024
MAX_EMAIL_TOTAL_ATTACHMENT_BYTES = 25 * 1024 * 1024
RENDER_SERVICE_PRICE_EUR = 300

# ----------------------- Helpers -----------------------
def serialize(doc: dict) -> dict:
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
        doc.pop("_id", None)
    return doc


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def normalize_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(cfg)
    if cfg.get("livello") not in VALID_LEVELS:
        cfg["livello"] = "premium"
    try:
        cfg["mq"] = max(1, int(cfg.get("mq") or 80))
    except (TypeError, ValueError):
        cfg["mq"] = 80
    return cfg


def object_id_or_400(value: str, label: str = "ID") -> ObjectId:
    if not value or not ObjectId.is_valid(str(value)):
        raise HTTPException(status_code=400, detail=f"{label} non valido")
    return ObjectId(str(value))


async def current_user(request: Request) -> dict:
    return await authlib.get_current_user(request, db)


async def require_admin(request: Request) -> dict:
    user = await authlib.get_current_user(request, db)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Accesso riservato agli amministratori")
    return user


async def optional_current_user(request: Request) -> Optional[dict]:
    try:
        return await authlib.get_current_user(request, db)
    except HTTPException:
        return None


# ----------------------- Models -----------------------
class LoginBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class LeadConfig(BaseModel):
    tipo_immobile: str = "appartamento"
    mq: int = Field(default=80, ge=1, le=2000)
    livello: str = "premium"
    bagni: int = 1
    camere: int = 2
    cucina: bool = True
    ambienti: List[str] = Field(default_factory=list)
    redistribuzione: Optional[bool] = None
    rifacimento_elettrico: Optional[bool] = None
    rifacimento_idrico: Optional[bool] = None
    rifacimento_termico: Optional[bool] = None
    controsoffitto: Optional[bool] = None
    clima: Optional[str] = None
    infissi: Optional[str] = None
    forniture_incluse: Optional[bool] = None
    stile: str = "Moderno minimal"
    tempistiche: str = "Sto valutando"
    has_files: bool = False
    ai_architect_job_id: Optional[str] = None
    ai_architect_summary: Optional[str] = None


class LeadCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    telefono: str = Field(min_length=6, max_length=32)
    citta: str = Field(min_length=1, max_length=120)
    indirizzo: Optional[str] = Field(default="", max_length=300)
    privacy: Literal[True]
    newsletter: bool = False
    tracking: Dict[str, Any] = Field(default_factory=dict)
    config: LeadConfig


class StaffPreventivoCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    telefono: str = Field(min_length=6, max_length=32)
    citta: str = Field(min_length=1, max_length=120)
    indirizzo: Optional[str] = Field(default="", max_length=300)
    config: LeadConfig


class EstimateBody(BaseModel):
    config: LeadConfig


class CallbackBody(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    telefono: str = Field(min_length=6, max_length=32)
    messaggio: Optional[str] = Field(default="", max_length=2000)


class UnlockEmailBody(BaseModel):
    email: str


class SopralluogoSlotCreate(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    end: str = Field(pattern=r"^\d{2}:\d{2}$")
    tecnico: Optional[str] = Field(default=None, max_length=120)


class SopralluogoBook(BaseModel):
    slot_id: str
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    telefono: str = Field(min_length=6, max_length=32)
    citta: Optional[str] = Field(default="", max_length=120)
    indirizzo: Optional[str] = Field(default="", max_length=300)
    lead_id: Optional[str] = None
    note: Optional[str] = Field(default="", max_length=2000)


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[List[str]] = None
    note_cliente: Optional[str] = None
    prossima_azione: Optional[str] = None


class TimelineEvent(BaseModel):
    tipo: str
    testo: str


class StaffCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: Literal["admin", "staff", "operations"] = "staff"


class AiCreditPackGrant(BaseModel):
    credits: int
    amount_eur: Optional[float] = None
    label: Optional[str] = None
    notes: Optional[str] = None


class AiArchitectConfirm(BaseModel):
    plan_type_selected: str


class AiArchitectApprove(BaseModel):
    reviewer: Optional[str] = "GB Construction"
    notes: Optional[str] = None


class AiArchitectRegenerate(BaseModel):
    output_types: Optional[List[str]] = None
    style_selected: Optional[str] = None
    correction_notes: Optional[str] = None


class AiArchitectRefineRegion(BaseModel):
    x: float
    y: float
    width: float
    height: float


class AiArchitectRefine(BaseModel):
    instruction: str
    region: Optional[AiArchitectRefineRegion] = None
    reviewer: Optional[str] = "Dashboard staff"


class AiProjectQuoteCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    telefono: str = Field(min_length=6, max_length=32)
    citta: str = Field(min_length=1, max_length=120)
    indirizzo: Optional[str] = Field(default="", max_length=300)
    privacy: Literal[True]
    newsletter: bool = False
    tracking: Dict[str, Any] = Field(default_factory=dict)
    ai_architect_job_id: str
    config: LeadConfig


class CantiereFase(BaseModel):
    nome: str
    stato: str = "da_iniziare"


class CantiereCreate(BaseModel):
    cliente: Optional[str] = ""
    telefono: Optional[str] = Field(default=None, max_length=40)
    indirizzo: Optional[str] = ""
    avanzamento: int = Field(default=0, ge=0, le=100)
    milestone: Optional[str] = ""
    milestone_data: Optional[str] = None
    capocantiere: Optional[str] = ""
    importo: float = Field(default=0, ge=0)
    criticita: Optional[str] = None
    fasi: List[CantiereFase] = Field(default_factory=list)
    stato: str = "attivo"
    lead_id: Optional[str] = None
    note: Optional[str] = ""


class CantiereUpdate(BaseModel):
    cliente: Optional[str] = None
    telefono: Optional[str] = Field(default=None, max_length=40)
    indirizzo: Optional[str] = None
    avanzamento: Optional[int] = Field(default=None, ge=0, le=100)
    milestone: Optional[str] = None
    milestone_data: Optional[str] = None
    capocantiere: Optional[str] = None
    importo: Optional[float] = Field(default=None, ge=0)
    criticita: Optional[str] = None
    fasi: Optional[List[CantiereFase]] = None
    stato: Optional[str] = None
    lead_id: Optional[str] = None
    note: Optional[str] = None


# ----------------------- Auth routes -----------------------
@api.post("/auth/login")
async def login(request: Request, body: LoginBody, response: Response):
    await api_security.enforce_rate_limit(
        db,
        scope="auth_login",
        identity=_client_ip(request),
        limit=AUTH_LOGIN_MAX_PER_15_MIN,
        window_seconds=15 * 60,
        detail="Troppi tentativi di accesso. Riprova tra qualche minuto.",
    )
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if (
        not user
        or user.get("disabled")
        or not authlib.verify_password(body.password, user["password_hash"])
    ):
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    uid = str(user["_id"])
    access = authlib.create_access_token(uid, email, user["role"])
    refresh = authlib.create_refresh_token(uid)
    authlib.set_auth_cookies(response, access, refresh)
    return {"id": uid, "email": email, "name": user["name"], "role": user["role"]}


@api.post("/auth/logout")
async def logout(response: Response):
    authlib.clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(request: Request):
    return await current_user(request)


@api.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Nessun refresh token")
    import jwt
    try:
        payload = jwt.decode(token, authlib.get_jwt_secret(), algorithms=[authlib.JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token non valido")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="Utente non trovato")
        access = authlib.create_access_token(str(user["_id"]), user["email"], user["role"])
        flags = authlib._cookie_flags()
        response.set_cookie("access_token", access, max_age=43200, **flags)
        return {"ok": True}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token non valido")


# ----------------------- Public routes -----------------------
@api.get("/")
async def root():
    return {"service": "GB Construction Lead Engine", "status": "ok"}


@api.get("/webhooks/meta")
@app.get("/webhooks/meta")
async def verify_meta_webhook(request: Request):
    verify_token = os.environ.get("META_VERIFY_TOKEN")
    if not verify_token:
        raise HTTPException(status_code=503, detail="META_VERIFY_TOKEN non configurato")
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == verify_token and challenge:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verifica webhook Meta non autorizzata")


@api.post("/webhooks/meta")
@app.post("/webhooks/meta")
async def receive_meta_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    app_secret = os.environ.get("META_APP_SECRET")
    try:
        signature_ok = meta_leads_service.verify_meta_signature(
            raw_body,
            request.headers.get("x-hub-signature-256"),
            app_secret,
        )
    except meta_leads_service.MetaLeadConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if not signature_ok:
        raise HTTPException(status_code=403, detail="Firma webhook Meta non valida")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload Meta non valido")

    events = meta_leads_service.extract_leadgen_events(payload)
    received_at = now_iso()
    for event in events:
        event_id = f"meta_leadgen:{event['leadgen_id']}"
        await db.meta_webhook_events.update_one(
            {"_id": event_id},
            {
                "$setOnInsert": {
                    "_id": event_id,
                    **event,
                    "payload_object": payload.get("object"),
                    "status": "pending",
                    "received_at": received_at,
                    "attempts": 0,
                },
                "$set": {"last_received_at": received_at},
            },
            upsert=True,
        )
        background_tasks.add_task(
            meta_leads_service.process_meta_webhook_event,
            db,
            event_id,
            meta_leads_service.get_meta_page_token(),
            os.environ.get("META_GRAPH_API_VERSION", "v23.0"),
        )
    return {"ok": True, "received": len(events)}


@api.get("/integrations/meta/status")
async def meta_integration_status(user: dict = Depends(current_user)):
    last_event = await db.meta_webhook_events.find({}).sort("last_received_at", -1).to_list(1)
    failed_count = await db.meta_webhook_events.count_documents({"status": "failed"})
    meta_leads = await db.leads.count_documents({"$or": [{"origine": "meta_ads"}, {"fonti": "meta_ads"}]})
    return {
        "configured": {
            "verify_token": bool(os.environ.get("META_VERIFY_TOKEN")),
            "app_secret": bool(os.environ.get("META_APP_SECRET")),
            "page_access_token": bool(meta_leads_service.get_meta_page_token()),
        },
        "graph_version": os.environ.get("META_GRAPH_API_VERSION", "v23.0"),
        "meta_leads": meta_leads,
        "failed_events": failed_count,
        "last_event": serialize(last_event[0]) if last_event else None,
    }


@api.post("/integrations/meta/retry-failed")
async def retry_failed_meta_events(background_tasks: BackgroundTasks, user: dict = Depends(require_admin)):
    events = await db.meta_webhook_events.find({"status": "failed"}).sort("failed_at", -1).to_list(50)
    for event in events:
        background_tasks.add_task(
            meta_leads_service.process_meta_webhook_event,
            db,
            event["_id"],
            meta_leads_service.get_meta_page_token(),
            os.environ.get("META_GRAPH_API_VERSION", "v23.0"),
        )
    return {"queued": len(events)}


@api.post("/estimate")
async def estimate(body: EstimateBody):
    return calcola_preventivo(normalize_config(body.config.model_dump()))


@api.get("/projects")
async def projects():
    return seed_data.DEMO_PROJECTS


# Email con generazioni preventivo illimitate (bypass del limite "uno per email").
QUOTE_UNLIMITED_EMAILS = {
    meta_leads_service.normalize_email(value)
    for value in os.getenv("QUOTE_UNLIMITED_EMAILS", "").split(",")
    if value.strip()
}


def _email_has_unlimited_quotes(email: str) -> bool:
    norm = meta_leads_service.normalize_email(email)
    return bool(norm) and norm in QUOTE_UNLIMITED_EMAILS


async def _existing_lead_for_email(email: str) -> Optional[Dict[str, Any]]:
    """Lead attivo per questa email (un solo preventivo per email).

    Esclude i lead 'sbloccati' dallo staff (dedup_released) cosi una nuova
    generazione e consentita senza cancellare lo storico CRM.
    """
    norm = meta_leads_service.normalize_email(email)
    if not norm:
        return None
    return await db.leads.find_one({"email_norm": norm, "dedup_released": {"$ne": True}})


def _duplicate_email_error(existing: Dict[str, Any]) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "email_already_used",
            "message": "Esiste gia un preventivo associato a questa email. E possibile generare un solo preventivo per indirizzo email.",
            "lead_id": str(existing.get("_id")),
        },
    )


@api.post("/leads")
async def create_lead(request: Request, body: LeadCreate, background_tasks: BackgroundTasks):
    await api_security.enforce_rate_limit(
        db,
        scope="public_lead",
        identity=_client_ip(request),
        limit=PUBLIC_LEAD_MAX_PER_HOUR,
        window_seconds=60 * 60,
        detail="Troppe richieste inviate. Riprova più tardi o contattaci telefonicamente.",
    )
    if not _email_has_unlimited_quotes(body.email):
        existing = await _existing_lead_for_email(body.email)
        if existing:
            raise _duplicate_email_error(existing)
    cfg = normalize_config(body.config.model_dump())
    if cfg.get("ai_architect_job_id") and not ObjectId.is_valid(str(cfg["ai_architect_job_id"])):
        cfg["ai_architect_job_id"] = None
    est = calcola_preventivo(cfg)
    score = lead_score(cfg, cfg.get("has_files", False))
    pkg = est["pacchetti"][cfg["livello"]]
    tags = []
    if score >= 75:
        tags.append("Caldo")
    if cfg["livello"] in ("premium", "luxury"):
        tags.append(cfg["livello"].capitalize())
    if "subito" in (cfg.get("tempistiche") or "").lower():
        tags.append("Subito")
    if cfg.get("has_files"):
        tags.append("File caricati")
    if cfg.get("ai_architect_job_id"):
        tags.append("AI Architect")
    doc = {
        "nome": body.nome, "email": body.email.lower(), "telefono": body.telefono,
        "email_norm": meta_leads_service.normalize_email(body.email),
        "phone_norm": meta_leads_service.normalize_phone(body.telefono),
        "citta": body.citta, "indirizzo": (body.indirizzo or "").strip(), "newsletter": body.newsletter,
        "privacy": body.privacy,
        "tipo_immobile": cfg["tipo_immobile"], "mq": cfg["mq"], "livello": cfg["livello"],
        "bagni": cfg["bagni"], "camere": cfg["camere"], "cucina": cfg["cucina"],
        "ambienti": cfg["ambienti"], "stile": cfg["stile"], "tempistiche": cfg["tempistiche"],
        "origine": "landing", "status": "nuovo", "owner": None, "score": score,
        "fonti": ["landing"],
        "tags": tags, "has_files": cfg.get("has_files", False), "note_cliente": "",
        "ai_architect_job_id": cfg.get("ai_architect_job_id"),
        "ai_architect_summary": cfg.get("ai_architect_summary"),
        "tracking": meta_leads_service.filter_tracking_payload(body.tracking),
        "range_basso": pkg["range_basso"], "range_alto": pkg["range_alto"],
        "estimate": est, "prossima_azione": "",
        "timeline": [{"id": "ev-" + uuid.uuid4().hex[:8], "tipo": "lead_ricevuto",
                      "testo": f"Lead ricevuto dalla landing - {cfg['tipo_immobile']} {cfg['mq']}mq a {body.citta}",
                      "ts": now_iso()}],
        "created_at": now_iso(), "last_contact": now_iso(), "status_changed_at": now_iso(),
    }
    res = await db.leads.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    if cfg.get("ai_architect_job_id"):
        await db.ai_architect_jobs.update_one(
            {"_id": ObjectId(cfg["ai_architect_job_id"])},
            {"$set": {"lead_id": str(res.inserted_id), "updated_at": now_iso()}},
        )
    email_service.enqueue_lead_emails(background_tasks, doc, "landing_quote")
    return {"id": str(res.inserted_id), "estimate": est, "score": score}


@api.post("/callback")
async def callback(request: Request, body: CallbackBody, background_tasks: BackgroundTasks):
    await api_security.enforce_rate_limit(
        db,
        scope="public_callback",
        identity=_client_ip(request),
        limit=PUBLIC_LEAD_MAX_PER_HOUR,
        window_seconds=60 * 60,
        detail="Troppe richieste inviate. Riprova più tardi o contattaci telefonicamente.",
    )
    email = body.email.lower() if body.email else ""
    doc = {
        "nome": body.nome, "email": email, "telefono": body.telefono, "citta": "",
        "email_norm": meta_leads_service.normalize_email(email), "phone_norm": meta_leads_service.normalize_phone(body.telefono),
        "tipo_immobile": "-", "mq": 0, "livello": "premium", "bagni": 0, "camere": 0,
        "ambienti": [], "stile": "-", "tempistiche": "Sto valutando", "origine": "callback",
        "fonti": ["callback"],
        "status": "nuovo", "owner": None, "score": 50, "tags": ["Richiamo"],
        "has_files": False, "note_cliente": body.messaggio or "", "range_basso": 0, "range_alto": 0,
        "estimate": None, "prossima_azione": "Richiamare il cliente entro 2 ore",
        "timeline": [{"id": "ev-" + uuid.uuid4().hex[:8], "tipo": "lead_ricevuto",
                      "testo": "Richiesta di richiamo dalla landing", "ts": now_iso()}],
        "created_at": now_iso(), "last_contact": now_iso(), "status_changed_at": now_iso(),
    }
    res = await db.leads.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    email_service.enqueue_lead_emails(background_tasks, doc, "callback")
    return {"id": str(res.inserted_id), "ok": True}


# ----------------------- AI Architect Layout & Render -----------------------
def _parse_priorities(raw: str) -> List[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return [str(v) for v in value if str(v).strip()]
    except Exception:
        pass
    return [p.strip() for p in raw.split(",") if p.strip()]


def _client_ip(request: Request) -> Optional[str]:
    forwarded_for = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        first_hop = forwarded_for.split(",", 1)[0].strip()
        if first_hop:
            return first_hop
    return request.client.host if request.client else None


async def _create_manual_render_request(
    request: Request,
    *,
    planimetria: UploadFile,
    plan_type_selected: str,
    project_variant_selected: str,
    style_selected: str,
    project_goal: str,
    priorities: str,
    requested_rooms: str,
    sqm: Optional[float],
    residents: Optional[int],
    budget: Optional[str],
    notes: Optional[str],
    lead_id: Optional[str],
):
    if not lead_id or not ObjectId.is_valid(lead_id):
        raise HTTPException(
            status_code=422,
            detail="Completa prima la stima personalizzata.",
        )

    linked_lead_id = str(lead_id)
    lead = await db.leads.find_one({"_id": ObjectId(linked_lead_id)})
    if not lead:
        raise HTTPException(status_code=404, detail="Stima cliente non trovata.")

    requested_room_list = [
        room[:80]
        for room in _parse_priorities(requested_rooms)
        if room.strip()
    ][:12]
    render_room_limit = max(
        len(requested_room_list),
        ai_architect_service.AI_RENDER_MAX_ROOMS_STAFF,
    )

    await ai_architect_service.enforce_upload_rate_limit(db, _client_ip(request))
    job = await ai_architect_service.create_job(
        db,
        upload=planimetria,
        plan_type_selected=plan_type_selected,
        project_variant_selected=project_variant_selected,
        style_selected=style_selected,
        project_goal=project_goal,
        priorities=_parse_priorities(priorities),
        sqm=sqm,
        residents=residents,
        budget=budget,
        notes=notes,
        lead_id=linked_lead_id,
        usage_context="staff",
        created_by_role="client",
        created_by_name=lead.get("nome"),
        created_by_email=lead.get("email"),
    )

    requested_at = now_iso()
    await db.ai_architect_jobs.update_one(
        {"_id": ObjectId(job["id"])},
        {
            "$set": {
                "status": "requested",
                "current_step": "awaiting_staff",
                "progress_percentage": 0,
                "processing_mode": "manual_staff_fulfillment",
                "request_source": "customer_paid_upsell",
                "service_type": "personalized_room_renders",
                "service_price_eur": RENDER_SERVICE_PRICE_EUR,
                "requested_rooms": requested_room_list,
                "render_room_limit": render_room_limit,
                "payment_status": "pending_staff_confirmation",
                "requested_at": requested_at,
                "updated_at": requested_at,
            }
        },
    )
    await db.leads.update_one(
        {"_id": ObjectId(linked_lead_id)},
        {
            "$set": {
                "ai_architect_job_id": job["id"],
                "render_request_id": job["id"],
                "has_files": True,
                "prossima_azione": (
                    "Contattare il cliente per confermare il servizio render da EUR 300"
                ),
                "updated_at": requested_at,
            },
            "$addToSet": {"tags": "Render personalizzati"},
            "$push": {
                "timeline": {
                    "id": "ev-" + uuid.uuid4().hex[:8],
                    "tipo": "render_richiesti",
                    "testo": "Richiesto servizio render personalizzati da EUR 300",
                    "ts": requested_at,
                }
            },
        },
    )

    # La richiesta entra nella coda staff: nessuna generazione viene avviata
    # dalla sessione cliente e nessun credito AI viene consumato.
    return {
        "id": job["id"],
        "status": "requested",
        "price_eur": RENDER_SERVICE_PRICE_EUR,
        "payment_status": "pending_staff_confirmation",
        "message": "Richiesta inviata allo staff GB Construction.",
    }


@api.post("/render-requests")
async def create_render_request(
    request: Request,
    planimetria: UploadFile = File(...),
    plan_type_selected: str = Form(...),
    project_variant_selected: str = Form("premium_suite"),
    style_selected: str = Form(...),
    project_goal: str = Form(...),
    priorities: str = Form("[]"),
    requested_rooms: str = Form("[]"),
    sqm: Optional[float] = Form(None),
    residents: Optional[int] = Form(None),
    budget: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    lead_id: str = Form(...),
):
    return await _create_manual_render_request(
        request,
        planimetria=planimetria,
        plan_type_selected=plan_type_selected,
        project_variant_selected=project_variant_selected,
        style_selected=style_selected,
        project_goal=project_goal,
        priorities=priorities,
        requested_rooms=requested_rooms,
        sqm=sqm,
        residents=residents,
        budget=budget,
        notes=notes,
        lead_id=lead_id,
    )


@api.post("/ai-architect/staff/jobs")
async def create_staff_ai_architect_job(
    background_tasks: BackgroundTasks,
    planimetria: UploadFile = File(...),
    plan_type_selected: str = Form(...),
    project_variant_selected: str = Form("premium_suite"),
    style_selected: str = Form(...),
    project_goal: str = Form(...),
    priorities: str = Form("[]"),
    sqm: Optional[float] = Form(None),
    residents: Optional[int] = Form(None),
    budget: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    lead_id: Optional[str] = Form(None),
    user: dict = Depends(current_user),
):
    await ai_credit_service.require_available_for_generation(
        db,
        ai_credit_service.RATE_CARD["ai_architect_preliminary"]["credits"],
        user=user,
    )
    linked_lead_id = lead_id if (lead_id and ObjectId.is_valid(lead_id)) else None
    job = await ai_architect_service.create_job(
        db,
        upload=planimetria,
        plan_type_selected=plan_type_selected,
        project_variant_selected=project_variant_selected,
        style_selected=style_selected,
        project_goal=project_goal,
        priorities=_parse_priorities(priorities),
        sqm=sqm,
        residents=residents,
        budget=budget,
        notes=notes,
        lead_id=linked_lead_id,
        user_id=user.get("id"),
        usage_context="staff",
        created_by_role=user.get("role"),
        created_by_name=user.get("name") or user.get("email"),
        created_by_email=user.get("email"),
    )
    if linked_lead_id:
        await db.leads.update_one(
            {"_id": ObjectId(linked_lead_id)},
            {"$set": {
                "ai_architect_job_id": job["id"],
                "has_files": True,
                "updated_at": now_iso(),
            },
             "$addToSet": {"tags": "AI Architect"}},
        )
    background_tasks.add_task(ai_architect_service.process_job, db, job["id"])
    return await ai_architect_service.get_job_payload(db, job["id"])


@api.get("/ai-architect/jobs")
async def list_ai_architect_jobs(
    status: Optional[str] = None,
    q: Optional[str] = None,
    user: dict = Depends(current_user),
):
    query: Dict[str, Any] = {}
    if status and status != "tutti":
        query["status"] = status
    if q:
        pattern = re.escape(q.strip())
        query["$or"] = [
            {"original_filename": {"$regex": pattern, "$options": "i"}},
            {"project_goal": {"$regex": pattern, "$options": "i"}},
            {"style_selected": {"$regex": pattern, "$options": "i"}},
            {"plan_type_detected": {"$regex": pattern, "$options": "i"}},
            {"created_by_name": {"$regex": pattern, "$options": "i"}},
            {"created_by_email": {"$regex": pattern, "$options": "i"}},
        ]

    docs = await db.ai_architect_jobs.find(query).sort("updated_at", -1).to_list(250)
    job_ids = [str(doc["_id"]) for doc in docs]
    outputs_by_job: Dict[str, Dict[str, Any]] = {}
    output_counts: Dict[str, int] = {}
    if job_ids:
        outputs = await db.ai_architect_outputs.find({"job_id": {"$in": job_ids}}).sort("created_at", 1).to_list(1500)
        for output in outputs:
            jid = output["job_id"]
            output_counts[jid] = output_counts.get(jid, 0) + 1
            by_type = outputs_by_job.setdefault(jid, {})
            by_type[output.get("output_type")] = serialize(output)

    items = []
    for doc in docs:
        item = serialize(doc)
        jid = item["id"]
        item["output_count"] = output_counts.get(jid, 0)
        item["latest_outputs"] = outputs_by_job.get(jid, {})
        items.append(item)
    return items


@api.get("/ai-architect/jobs/{job_id}")
async def get_ai_architect_job(job_id: str):
    return await ai_architect_service.get_job_payload(db, job_id)


@api.post("/ai-architect/jobs/{job_id}/reanalyze")
async def reanalyze_ai_architect_job(job_id: str, request: Request, background_tasks: BackgroundTasks):
    user = await optional_current_user(request)
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Progetto AI Architect non trovato")
    await ai_credit_service.require_available_for_generation(
        db,
        ai_credit_service.RATE_CARD["ai_architect_preliminary"]["credits"],
        user=user,
        job=job,
        public_message=user is None,
    )
    await ai_architect_service.ensure_processed_reference(db, job_id)
    await db.ai_architect_outputs.delete_many({
        "job_id": job_id,
        "output_type": {"$in": [
            "analysis",
            "professional_floorplan",
            "floor_plan_automation",
            "technical_floor_plan_json",
            "optimized_floor_plan_json",
            "plan_details",
            "clean_2d_plan",
            "redistributed_2d_plan",
            "topdown_3d_plan",
            "room_render",
            "advice",
            "pdf_report",
        ]},
    })
    await db.ai_architect_quality_logs.delete_many({"job_id": job_id})
    await db.ai_architect_errors.delete_many({"job_id": job_id})
    await db.ai_architect_jobs.update_one(
        {"_id": ObjectId(job_id)},
        {
            "$set": {
                "status": "processing",
                "current_step": "analysis",
                "progress_percentage": 18,
                "requires_confirmation": False,
                "review_status": "pending",
                "review_required": ai_architect_service.REQUIRE_REVIEW_BEFORE_RENDERS,
                "vision_analysis": None,
                "professional_floorplan": None,
                "floor_plan_automation": None,
                "technical_floor_plan_json": None,
                "optimized_floor_plan_json": None,
                "adapter": f"analysis:{ai_architect_service.CLAUDE_VISION_MODEL}|text:{ai_architect_service.CLAUDE_TEXT_MODEL}|image:{ai_architect_service._selected_image_provider()}",
                "analysis_provider": "anthropic" if ai_architect_service._anthropic_api_key() else ("openrouter" if ai_architect_service._openrouter_api_key() else "professional-safe-mode"),
                "analysis_model": ai_architect_service.CLAUDE_VISION_MODEL if ai_architect_service._anthropic_api_key() else (ai_architect_service.OPENROUTER_VISION_MODEL if ai_architect_service._openrouter_api_key() else "gb-safe-delivery-v1"),
                "image_generation": {
                    "provider": ai_architect_service._selected_image_provider(),
                    "model": ai_architect_service.FAL_IMAGE_MODEL if ai_architect_service._selected_image_provider() == "fal" else (ai_architect_service.OPENAI_IMAGE_MODEL if ai_architect_service._openai_images_available() else "local-concept-v1"),
                    "quality": ai_architect_service.OPENAI_IMAGE_QUALITY,
                    "plan_size": ai_architect_service.OPENAI_IMAGE_SIZE_PLAN,
                    "render_size": ai_architect_service.OPENAI_IMAGE_SIZE_RENDER,
                },
                "updated_at": now_iso(),
            },
            "$unset": {
                "force_safe_visuals": "",
                "analysis_quality_issues": "",
                "layout_quality_hold": "",
                "render_quality_hold": "",
                "vision_analysis_pending": "",
                "error_message": "",
            },
        },
    )
    background_tasks.add_task(ai_architect_service.process_job, db, job_id)
    return await ai_architect_service.get_job_payload(db, job_id)


@api.post("/ai-architect/jobs/{job_id}/complete-safe")
async def complete_safe_ai_architect_job(job_id: str):
    return await ai_architect_service.complete_job_safe_mode(db, job_id)


@api.post("/ai-architect/jobs/{job_id}/confirm")
async def confirm_ai_architect_job(job_id: str, body: AiArchitectConfirm, background_tasks: BackgroundTasks):
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job AI Architect non trovato")
    await ai_credit_service.require_available_for_generation(
        db,
        ai_credit_service.RATE_CARD["ai_architect_preliminary"]["credits"],
        job=job,
        public_message=True,
    )
    await db.ai_architect_jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {
            "status": "processing",
            "current_step": "proposal_2d",
            "progress_percentage": 34,
            "requires_confirmation": False,
            "updated_at": now_iso(),
        }},
    )
    background_tasks.add_task(ai_architect_service.confirm_job, db, job_id, body.plan_type_selected)
    return await ai_architect_service.get_job_payload(db, job_id)


@api.post("/ai-architect/jobs/{job_id}/approve")
async def approve_ai_architect_job(job_id: str, request: Request, body: AiArchitectApprove, background_tasks: BackgroundTasks):
    user = await optional_current_user(request)
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job AI Architect non trovato")
    await ai_credit_service.require_available_for_generation(
        db,
        ai_credit_service.render_stage_credits(job),
        user=user,
        job=job,
        public_message=user is None,
    )
    await ai_architect_service.ensure_concept_ready_for_approval(db, job_id)
    await db.ai_architect_jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {
            "status": "processing",
            "current_step": "topdown_3d",
            "progress_percentage": 62,
            "adapter": f"analysis:{ai_architect_service.CLAUDE_VISION_MODEL}|text:{ai_architect_service.CLAUDE_TEXT_MODEL}|image:{ai_architect_service._selected_image_provider()}",
            "image_generation": {
                "provider": ai_architect_service._selected_image_provider(),
                "model": ai_architect_service.FAL_IMAGE_MODEL if ai_architect_service._selected_image_provider() == "fal" else (ai_architect_service.OPENAI_IMAGE_MODEL if ai_architect_service._openai_images_available() else "local-concept-v1"),
                "quality": ai_architect_service.OPENAI_IMAGE_QUALITY,
                "plan_size": ai_architect_service.OPENAI_IMAGE_SIZE_PLAN,
                "render_size": ai_architect_service.OPENAI_IMAGE_SIZE_RENDER,
            },
            "review_status": "approved",
            "review_notes": body.notes,
            "review_approved_by": body.reviewer or "GB Construction",
            "review_approved_at": now_iso(),
            "updated_at": now_iso(),
        }},
    )
    background_tasks.add_task(
        ai_architect_service.approve_job,
        db,
        job_id,
        reviewer=body.reviewer,
        notes=body.notes,
    )
    return await ai_architect_service.get_job_payload(db, job_id)


@api.post("/ai-architect/jobs/{job_id}/regenerate")
async def regenerate_ai_architect_job(job_id: str, request: Request, body: AiArchitectRegenerate, background_tasks: BackgroundTasks):
    user = await optional_current_user(request)
    job = await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job AI Architect non trovato")
    await ai_credit_service.require_available_for_generation(
        db,
        ai_credit_service.regeneration_credits(job, body.output_types),
        user=user,
        job=job,
        public_message=user is None,
    )
    requested = set(body.output_types or [])
    is_concept_regeneration = bool(
        requested & {"concept_2d", "clean_2d_plan", "redistributed_2d_plan"}
    )
    if is_concept_regeneration:
        await ai_architect_service.reserve_concept_2d_regeneration(db, job_id)
    await db.ai_architect_jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {
            "status": "processing",
            "current_step": "proposal_2d" if is_concept_regeneration else "renders",
            "progress_percentage": 34 if is_concept_regeneration else 70,
            "adapter": f"analysis:{ai_architect_service.CLAUDE_VISION_MODEL}|text:{ai_architect_service.CLAUDE_TEXT_MODEL}|image:{ai_architect_service._selected_image_provider()}",
            "image_generation": {
                "provider": ai_architect_service._selected_image_provider(),
                "model": ai_architect_service.FAL_IMAGE_MODEL if ai_architect_service._selected_image_provider() == "fal" else (ai_architect_service.OPENAI_IMAGE_MODEL if ai_architect_service._openai_images_available() else "local-concept-v1"),
                "quality": ai_architect_service.OPENAI_IMAGE_QUALITY,
                "plan_size": ai_architect_service.OPENAI_IMAGE_SIZE_PLAN,
                "render_size": ai_architect_service.OPENAI_IMAGE_SIZE_RENDER,
            },
            "updated_at": now_iso(),
        }},
    )
    background_tasks.add_task(
        ai_architect_service.regenerate_outputs,
        db,
        job_id,
        style_selected=body.style_selected,
        output_types=body.output_types,
        correction_notes=body.correction_notes,
        charge_id=uuid.uuid4().hex,
    )
    return await ai_architect_service.get_job_payload(db, job_id)


@api.post("/ai-architect/jobs/{job_id}/outputs/{output_id}/refine")
async def refine_ai_architect_output(
    job_id: str,
    output_id: str,
    request: Request,
    body: AiArchitectRefine,
    background_tasks: BackgroundTasks,
):
    if not ai_architect_service.AI_REFINE_ENABLED:
        raise HTTPException(status_code=403, detail="Ritocco interattivo non abilitato")
    instruction = (body.instruction or "").strip()
    if len(instruction) < 4:
        raise HTTPException(status_code=422, detail="Descrivi la correzione da applicare all'immagine")
    job_oid = object_id_or_400(job_id, "Job AI Architect")
    output_oid = object_id_or_400(output_id, "Immagine")
    user = await optional_current_user(request)
    job = await db.ai_architect_jobs.find_one({"_id": job_oid})
    if not job:
        raise HTTPException(status_code=404, detail="Job AI Architect non trovato")
    output = await db.ai_architect_outputs.find_one({"_id": output_oid, "job_id": job_id})
    if not output:
        raise HTTPException(status_code=404, detail="Immagine da correggere non trovata")
    output_type = output.get("output_type")
    if output_type not in ai_architect_service.AI_REFINABLE_OUTPUT_TYPES:
        raise HTTPException(status_code=422, detail="Questo output non e ritoccabile")
    action_key = ai_architect_service.AI_REFINABLE_OUTPUT_TYPES[output_type]
    await ai_credit_service.require_available_for_generation(
        db,
        ai_credit_service.action_credits(action_key),
        user=user,
        job=job,
        public_message=user is None,
    )
    previous_status = job.get("status") or "completed"
    await db.ai_architect_jobs.update_one(
        {"_id": job_oid},
        {"$set": {
            "status": "processing",
            "current_step": "refine",
            "refine_in_progress": True,
            "updated_at": now_iso(),
        }},
    )
    background_tasks.add_task(
        ai_architect_service.refine_output,
        db,
        job_id,
        output_id,
        instruction=instruction,
        region=body.region.dict() if body.region else None,
        reviewer=body.reviewer,
        charge_id=uuid.uuid4().hex,
        previous_status=previous_status,
    )
    return await ai_architect_service.get_job_payload(db, job_id)


@api.get("/ai-architect/refinement-memories")
async def list_ai_architect_refinement_memories(job_id: Optional[str] = Query(None)):
    return await ai_architect_service.list_refinement_memories(db, job_id=job_id)


class AiArchitectMemoryToggle(BaseModel):
    enabled: bool


@api.patch("/ai-architect/refinement-memories/{memory_id}")
async def toggle_ai_architect_refinement_memory(memory_id: str, body: AiArchitectMemoryToggle):
    memory_oid = object_id_or_400(memory_id, "Memoria")
    updated = await ai_architect_service.set_refinement_memory_enabled(db, str(memory_oid), body.enabled)
    if not updated:
        raise HTTPException(status_code=404, detail="Memoria non trovata")
    return updated


@api.get("/ai-architect/jobs/{job_id}/report")
async def ai_architect_report(job_id: str):
    path = await ai_architect_service.report_path_for_job(db, job_id)
    return FileResponse(path, media_type="application/pdf", filename=f"GB-AI-Architect-{job_id}.pdf")


@api.post("/quote/from-ai-project")
async def quote_from_ai_project(
    request: Request,
    body: AiProjectQuoteCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(current_user),
):
    if user.get("role") not in {"admin", "staff", "operations"}:
        raise HTTPException(status_code=403, detail="Accesso staff richiesto")
    await api_security.enforce_rate_limit(
        db,
        scope="public_ai_quote",
        identity=_client_ip(request),
        limit=PUBLIC_LEAD_MAX_PER_HOUR,
        window_seconds=60 * 60,
        detail="Troppe richieste inviate. Riprova più tardi o contattaci telefonicamente.",
    )
    ai_job_oid = object_id_or_400(body.ai_architect_job_id, "Progetto AI Architect")
    job = await db.ai_architect_jobs.find_one({"_id": ai_job_oid})
    if not job:
        raise HTTPException(status_code=404, detail="Progetto AI Architect non trovato")

    if not _email_has_unlimited_quotes(body.email):
        existing = await _existing_lead_for_email(body.email)
        # Consenti il collegamento se il lead esistente e proprio quello gia legato a questo job;
        # blocca invece un secondo preventivo con la stessa email su un job diverso.
        if existing and str(existing.get("ai_architect_job_id") or "") != body.ai_architect_job_id:
            raise _duplicate_email_error(existing)

    cfg = normalize_config(body.config.model_dump())
    cfg["has_files"] = True
    cfg["ai_architect_job_id"] = body.ai_architect_job_id
    est = calcola_preventivo(cfg)
    score = max(85, lead_score(cfg, True))
    pkg = est["pacchetti"][cfg["livello"]]
    summary = (
        f"AI Architect: {job.get('project_goal')} - {job.get('style_selected')} - "
        f"{job.get('plan_type_detected') or job.get('plan_type_selected')}"
    )
    doc = {
        "nome": body.nome, "email": body.email.lower(), "telefono": body.telefono,
        "email_norm": meta_leads_service.normalize_email(body.email),
        "phone_norm": meta_leads_service.normalize_phone(body.telefono),
        "citta": body.citta, "indirizzo": (body.indirizzo or "").strip(), "newsletter": body.newsletter,
        "privacy": body.privacy,
        "tipo_immobile": cfg["tipo_immobile"], "mq": cfg["mq"], "livello": cfg["livello"],
        "bagni": cfg["bagni"], "camere": cfg["camere"], "cucina": cfg["cucina"],
        "ambienti": cfg["ambienti"], "stile": cfg["stile"], "tempistiche": cfg["tempistiche"],
        "origine": "ai_architect", "status": "nuovo", "owner": None, "score": score,
        "fonti": ["ai_architect"],
        "tags": ["AI Architect", "Progetto AI", cfg["livello"].capitalize()],
        "has_files": True, "note_cliente": job.get("notes") or "",
        "ai_architect_job_id": body.ai_architect_job_id,
        "ai_architect_summary": summary,
        "tracking": meta_leads_service.filter_tracking_payload(body.tracking),
        "range_basso": pkg["range_basso"], "range_alto": pkg["range_alto"],
        "estimate": est, "prossima_azione": "Contattare cliente e proporre consulenza su progetto AI Architect",
        "timeline": [
            {"id": "ev-" + uuid.uuid4().hex[:8], "tipo": "lead_ricevuto",
             "testo": f"Richiesta preventivo da AI Architect - {cfg['tipo_immobile']} {cfg['mq']}mq a {body.citta}",
             "ts": now_iso()},
            {"id": "ev-" + uuid.uuid4().hex[:8], "tipo": "ai_architect",
             "testo": summary, "ts": now_iso()},
        ],
        "created_at": now_iso(), "last_contact": now_iso(), "status_changed_at": now_iso(),
    }
    res = await db.leads.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    await db.ai_architect_jobs.update_one(
        {"_id": ai_job_oid},
        {"$set": {"lead_id": str(res.inserted_id), "updated_at": now_iso()}},
    )
    email_service.enqueue_lead_emails(background_tasks, doc, "ai_quote")
    return {"id": str(res.inserted_id), "estimate": est, "score": score, "ai_architect_job_id": body.ai_architect_job_id}


# ----------------------- Staff: leads -----------------------
@api.get("/leads")
async def list_leads(request: Request, status: Optional[str] = None,
                     q: Optional[str] = None, owner: Optional[str] = None,
                     origine: Optional[str] = None,
                     user: dict = Depends(current_user)):
    query: Dict[str, Any] = {}
    and_conditions: List[Dict[str, Any]] = []

    if status and status != "tutti":
        if status == "preventivi":
            query["status"] = {"$in": ["preventivo_preparazione", "preventivo_inviato"]}
        elif status == "da_contattare":
            query["status"] = {"$in": ["nuovo", "qualificato"]}
        elif status == "sopralluogo":
            query["status"] = {"$in": ["sopralluogo_fissato", "sopralluogo_fatto"]}
        elif status == "persi":
            query["status"] = "chiuso_perso"
        else:
            query["status"] = status
    if owner:
        query["owner"] = owner
    if origine and origine != "tutte":
        and_conditions.append({"$or": [{"origine": origine}, {"fonti": origine}]})
    if q:
        and_conditions.append({"$or": [
            {"nome": {"$regex": q, "$options": "i"}},
            {"citta": {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]})

    if and_conditions:
        if len(and_conditions) == 1:
            query["$or"] = and_conditions[0]["$or"]
        else:
            query["$and"] = and_conditions

    docs = await db.leads.find(query).sort("created_at", -1).to_list(500)
    return [serialize(d) for d in docs]


@api.get("/leads/counts")
async def lead_counts(user: dict = Depends(current_user)):
    docs = await db.leads.find({}, {"status": 1}).to_list(1000)
    counts: Dict[str, int] = {}
    for d in docs:
        counts[d.get("status", "nuovo")] = counts.get(d.get("status", "nuovo"), 0) + 1
    return {"counts": counts, "totale": len(docs)}


@api.post("/leads/unlock-email")
async def unlock_email(body: UnlockEmailBody, user: dict = Depends(current_user)):
    """Sblocca un'email: consente una nuova generazione preventivo senza cancellare lo storico.

    I lead esistenti restano nel CRM ma marcati dedup_released, cosi il limite
    'uno per email' non li conta piu come blocco.
    """
    norm = meta_leads_service.normalize_email(body.email)
    if not norm:
        raise HTTPException(status_code=400, detail="Email non valida")
    event = {
        "id": "ev-" + uuid.uuid4().hex[:8],
        "tipo": "nota",
        "testo": f"Email sbloccata da {user.get('name') or 'staff'}: consentita nuova generazione preventivo.",
        "ts": now_iso(),
        "autore": user.get("name"),
    }
    res = await db.leads.update_many(
        {"email_norm": norm},
        {
            "$set": {"dedup_released": True, "dedup_released_at": now_iso(), "updated_at": now_iso()},
            "$addToSet": {"tags": "Email sbloccata"},
            "$push": {"timeline": event},
        },
    )
    return {"email": norm, "unlocked": res.modified_count}


@api.get("/leads/{lead_id}")
async def get_lead(lead_id: str, user: dict = Depends(current_user)):
    doc = await db.leads.find_one({"_id": ObjectId(lead_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Lead non trovato")
    return serialize(doc)


@api.patch("/leads/{lead_id}")
async def update_lead(
    request: Request,
    lead_id: str,
    body: LeadUpdate,
    user: dict = Depends(current_user),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nessun campo da aggiornare")
    events = []
    existing = await db.leads.find_one({"_id": ObjectId(lead_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Lead non trovato")
    if "status" in updates and updates["status"] != existing.get("status"):
        updates["status_changed_at"] = now_iso()
        if existing.get("status") == "nuovo" and updates["status"] != "nuovo" and not existing.get("first_response_at"):
            updates["first_response_at"] = now_iso()
        events.append({"id": "ev-" + uuid.uuid4().hex[:8], "tipo": "cambio_stato",
                       "testo": f"Stato aggiornato a «{STATO_LABELS.get(updates['status'], updates['status'])}» da {user['name']}",
                       "ts": now_iso()})
    if "owner" in updates:
        events.append({"id": "ev-" + uuid.uuid4().hex[:8], "tipo": "assegnazione",
                       "testo": f"Lead assegnato a {updates['owner']}", "ts": now_iso()})
    op: Dict[str, Any] = {"$set": updates}
    if events:
        op["$push"] = {"timeline": {"$each": events, "$position": 0}}
    await db.leads.update_one({"_id": ObjectId(lead_id)}, op)
    doc = await db.leads.find_one({"_id": ObjectId(lead_id)})
    try:
        async with get_tenant_conn(request, user) as (conn, tenant):
            await lead_bridge.sync_existing_postgres_lead(
                conn, tenant["id"], doc
            )
    except Exception as exc:
        # Il mirror viene creato solo quando il lead entra nei flussi EdilOS.
        # Inbox/Pipeline restano disponibili anche durante un guasto Postgres.
        logger.warning("Mirror Postgres lead %s non aggiornato: %s", lead_id, exc)
    return serialize(doc)


@api.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, user: dict = Depends(require_admin)):
    oid = object_id_or_400(lead_id, "Lead")
    existing = await db.leads.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Lead non trovato")
    await db.leads.delete_one({"_id": oid})
    # Libera eventuali slot sopralluogo collegati e scollega i job AI.
    await db.sopralluogo_slots.update_many(
        {"lead_id": lead_id},
        {"$set": {"status": "free", "lead_id": None, "booked_name": None,
                  "booked_email": None, "booked_phone": None, "updated_at": now_iso()}},
    )
    await db.ai_architect_jobs.update_many({"lead_id": lead_id}, {"$set": {"lead_id": None}})
    return {"ok": True, "deleted": str(oid)}


class LeadsCleanupBody(BaseModel):
    keep_emails: List[str] = Field(default_factory=list)


@api.post("/leads/cleanup-test")
async def cleanup_test_leads(body: LeadsCleanupBody, user: dict = Depends(require_admin)):
    """Elimina tutti i lead tranne quelli con le email da conservare (default: whitelist illimitata).

    Pensato per ripulire i lead di esempio/test lasciando solo i lead reali.
    """
    keep = {meta_leads_service.normalize_email(e) for e in body.keep_emails if e.strip()}
    keep |= QUOTE_UNLIMITED_EMAILS
    keep = {e for e in keep if e}
    kept_docs = await db.leads.find({"email_norm": {"$in": list(keep)}}).to_list(500)
    kept_ids = {str(d["_id"]) for d in kept_docs}
    res = await db.leads.delete_many({"email_norm": {"$nin": list(keep)}})
    # Libera slot e scollega job dei lead eliminati.
    await db.sopralluogo_slots.update_many(
        {"lead_id": {"$nin": list(kept_ids)}, "status": "booked"},
        {"$set": {"status": "free", "lead_id": None, "booked_name": None,
                  "booked_email": None, "booked_phone": None, "updated_at": now_iso()}},
    )
    return {"ok": True, "deleted": res.deleted_count, "kept": len(kept_ids), "kept_emails": list(keep)}


@api.get("/email/status")
async def email_status(user: dict = Depends(current_user)):
    return {
        "configured": email_service.is_configured(),
        "transport": email_service.transport_name(),
    }


@api.post("/leads/{lead_id}/email")
async def send_lead_email(
    lead_id: str,
    subject: str = Form(...),
    body: str = Form(...),
    to: Optional[str] = Form(None),
    attachments: List[UploadFile] = File(default=[]),
    user: dict = Depends(current_user),
):
    """Invio email manuale dallo staff al cliente dall'email ufficiale, con allegati."""
    lead = await db.leads.find_one({"_id": object_id_or_400(lead_id, "Lead")})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead non trovato")
    to_email = (to or lead.get("email") or "").strip()
    if not to_email:
        raise HTTPException(status_code=400, detail="Email destinatario mancante")
    try:
        to_email = str(EMAIL_ADDRESS_ADAPTER.validate_python(to_email))
    except ValidationError:
        raise HTTPException(status_code=400, detail="Email destinatario non valida")
    subject = subject.strip()
    body = body.strip()
    if not subject or len(subject) > 200:
        raise HTTPException(status_code=400, detail="Oggetto email non valido")
    if not body or len(body) > 10000:
        raise HTTPException(status_code=400, detail="Messaggio email non valido")
    if len(attachments or []) > 10:
        raise HTTPException(status_code=400, detail="Puoi allegare al massimo 10 file")
    files_payload = []
    total_attachment_bytes = 0
    for upload in attachments or []:
        content = await upload.read()
        if not content:
            continue
        if len(content) > MAX_EMAIL_ATTACHMENT_BYTES:
            raise HTTPException(status_code=400, detail=f"Allegato troppo grande: {upload.filename}")
        total_attachment_bytes += len(content)
        if total_attachment_bytes > MAX_EMAIL_TOTAL_ATTACHMENT_BYTES:
            raise HTTPException(status_code=400, detail="Gli allegati superano il limite totale di 25 MB")
        files_payload.append({
            "filename": upload.filename or "allegato",
            "content": content,
            "mime": upload.content_type or "application/octet-stream",
        })
    try:
        await asyncio.to_thread(
            email_service.send_custom_email,
            to_email=to_email,
            subject=subject,
            body_text=body,
            attachments=files_payload,
            reply_to=email_service._notification_email(),
        )
    except Exception as exc:
        logger.exception("Invio email lead %s non riuscito: %s", lead_id, exc)
        raise HTTPException(status_code=502, detail="Invio email non riuscito. Riprova più tardi.")
    event = {
        "id": "ev-" + uuid.uuid4().hex[:8], "tipo": "messaggio",
        "testo": f"Email inviata a {to_email} da {user.get('name') or 'staff'}: {subject}"
                 + (f" ({len(files_payload)} allegati)" if files_payload else ""),
        "ts": now_iso(), "autore": user.get("name"),
    }
    await db.leads.update_one(
        {"_id": lead["_id"]},
        {"$set": {"last_contact": now_iso(), "updated_at": now_iso()},
         "$push": {"timeline": {"$each": [event], "$position": 0}}},
    )
    return {"ok": True, "to": to_email, "attachments": len(files_payload)}


@api.post("/leads/{lead_id}/timeline")
async def add_timeline(lead_id: str, body: TimelineEvent, user: dict = Depends(current_user)):
    ev = {"id": "ev-" + uuid.uuid4().hex[:8], "tipo": body.tipo,
          "testo": body.testo, "ts": now_iso(), "autore": user["name"]}
    lead = await db.leads.find_one({"_id": ObjectId(lead_id)})
    set_fields = {"last_contact": now_iso()}
    if lead and not lead.get("first_response_at") and body.tipo in ("chiamata", "whatsapp", "email"):
        set_fields["first_response_at"] = now_iso()
    await db.leads.update_one(
        {"_id": ObjectId(lead_id)},
        {"$push": {"timeline": {"$each": [ev], "$position": 0}},
         "$set": set_fields})
    return ev


@api.post("/leads/{lead_id}/suggest")
async def suggest_action(lead_id: str, user: dict = Depends(current_user)):
    doc = await db.leads.find_one({"_id": ObjectId(lead_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Lead non trovato")
    await ai_credit_service.require_available_for_generation(
        db,
        ai_credit_service.RATE_CARD["lead_suggestion"]["credits"],
        user=user,
    )
    try:
        suggestion = await ai_service.suggest_next_action(serialize(doc))
    except Exception as e:
        logger.exception("AI suggest failed")
        raise HTTPException(status_code=502, detail=f"Servizio AI non disponibile: {e}")
    await db.leads.update_one({"_id": ObjectId(lead_id)}, {"$set": {"prossima_azione": suggestion}})
    await ai_credit_service.charge_credits(
        db,
        action_key="lead_suggestion",
        idempotency_key=f"lead_suggestion:{lead_id}:{uuid.uuid4().hex}",
        user=user,
        lead_id=lead_id,
        metadata={"lead_nome": doc.get("nome")},
    )
    return {"suggestion": suggestion}


# ----------------------- Dashboard -----------------------
def _giorni_da(iso_str: str) -> int:
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 0


@api.get("/dashboard/today")
async def dashboard_today(user: dict = Depends(current_user)):
    leads = await db.leads.find({}).sort("created_at", -1).to_list(1000)
    leads = [serialize(d) for d in leads]
    now = datetime.now(timezone.utc)
    nuovi = [l for l in leads if l.get("status") == "nuovo"]
    nuovi_caldi = sorted(nuovi, key=lambda x: x.get("score", 0), reverse=True)[:3]
    followup = [l for l in leads if l.get("status") in ("follow_up", "in_trattativa")][:5]
    preventivi = [l for l in leads if l.get("status") == "preventivo_inviato"]
    prev_attesa = []
    for l in preventivi:
        g = _giorni_da(l.get("status_changed_at", l.get("created_at")))
        prev_attesa.append({**l, "giorni_silenzio": g})
    alert = []
    for l in nuovi:
        try:
            dt = datetime.fromisoformat(l.get("created_at"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            sla_due = l.get("sla_due_at")
            sla_expired = False
            if sla_due:
                due_dt = datetime.fromisoformat(sla_due)
                if due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=timezone.utc)
                sla_expired = now > due_dt
            meta_expired = l.get("origine") == "meta_ads" and (now - dt) > timedelta(minutes=15)
            standard_expired = (now - dt) > timedelta(hours=18)
            if not l.get("first_response_at") and (sla_expired or meta_expired or standard_expired):
                alert.append(l)
        except Exception:
            pass
    sopralluoghi = [l for l in leads if l.get("status") in ("sopralluogo_fissato", "sopralluogo_fatto")]
    return {
        "nuovi_count": len(nuovi), "nuovi_caldi": nuovi_caldi,
        "followup": followup, "followup_count": len(followup),
        "preventivi_attesa": prev_attesa,
        "sopralluoghi_count": len(sopralluoghi),
        "alert": alert,
    }


# Stati da cui una prenotazione sopralluogo può promuovere automaticamente il lead.
SOPRALLUOGO_AUTO_PROMOTE_FROM = {None, "nuovo", "qualificato", "sopralluogo_fissato"}


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _slot_appointment_payload(slot: dict) -> dict:
    return {
        "slot_id": str(slot.get("_id") or slot.get("id") or ""),
        "date": slot.get("date"),
        "start": slot.get("start"),
        "end": slot.get("end"),
        "tecnico": slot.get("tecnico"),
        "status": slot.get("status") or "booked",
    }


async def _booked_appointments_by_lead() -> Dict[str, dict]:
    """Mappa lead_id → appuntamento più imminente (o più recente se tutti passati)."""
    slots = await db.sopralluogo_slots.find(
        {"status": "booked", "lead_id": {"$nin": [None, ""]}}
    ).sort([("date", 1), ("start", 1)]).to_list(1000)
    today = _today_iso()
    by_lead: Dict[str, dict] = {}
    for slot in slots:
        lead_id = str(slot.get("lead_id") or "").strip()
        if not lead_id:
            continue
        appt = _slot_appointment_payload(slot)
        existing = by_lead.get(lead_id)
        if not existing:
            by_lead[lead_id] = appt
            continue
        # Preferisci appuntamenti futuri/oggi; a parità, il più vicino.
        existing_future = (existing.get("date") or "") >= today
        candidate_future = (appt.get("date") or "") >= today
        if candidate_future and not existing_future:
            by_lead[lead_id] = appt
        elif candidate_future == existing_future:
            if (appt.get("date"), appt.get("start")) < (existing.get("date"), existing.get("start")):
                by_lead[lead_id] = appt
    return by_lead


async def _sync_lead_with_sopralluogo_slot(lead: dict, slot: dict) -> dict:
    """Allinea stato pipeline e campo sopralluogo sul lead quando c'è uno slot booked."""
    if not lead or not slot:
        return lead
    lead_id = lead.get("_id") or lead.get("id")
    if not lead_id:
        return lead
    oid = lead_id if isinstance(lead_id, ObjectId) else (
        ObjectId(str(lead_id)) if ObjectId.is_valid(str(lead_id)) else None
    )
    if not oid:
        return lead

    appt = _slot_appointment_payload(slot)
    set_fields: Dict[str, Any] = {
        "sopralluogo": appt,
        "updated_at": now_iso(),
    }
    current_status = lead.get("status")
    if current_status in SOPRALLUOGO_AUTO_PROMOTE_FROM and current_status != "sopralluogo_fatto":
        if current_status != "sopralluogo_fissato":
            set_fields["status"] = "sopralluogo_fissato"
            set_fields["status_changed_at"] = now_iso()
            set_fields["prossima_azione"] = (
                f"Sopralluogo il {appt.get('date')} alle {appt.get('start') or ''}".strip()
            )

    push_op = None
    if set_fields.get("status") == "sopralluogo_fissato":
        push_op = {
            "timeline": {
                "id": "ev-" + uuid.uuid4().hex[:8],
                "tipo": "sopralluogo",
                "testo": (
                    f"Pipeline aggiornata: sopralluogo fissato "
                    f"({appt.get('date')} {appt.get('start')}-{appt.get('end')})"
                ),
                "ts": now_iso(),
            }
        }

    op: Dict[str, Any] = {"$set": set_fields, "$addToSet": {"tags": "Sopralluogo"}}
    if push_op:
        op["$push"] = push_op
    await db.leads.update_one({"_id": oid}, op)
    updated = await db.leads.find_one({"_id": oid})
    return updated or lead


@api.get("/pipeline")
async def pipeline(user: dict = Depends(current_user)):
    leads = await db.leads.find({}).sort("status_changed_at", -1).to_list(1000)
    appointments = await _booked_appointments_by_lead()

    # Auto-sync: se esiste un appuntamento booked, il lead deve comparire in pipeline
    # come "sopralluogo fissato" (salvo stati già più avanzati).
    synced_leads = []
    for raw in leads:
        lead = raw
        lead_id = str(raw.get("_id"))
        appt = appointments.get(lead_id)
        if appt and raw.get("status") in (None, "nuovo", "qualificato"):
            # Ricostruisci uno slot minimo per il sync DB
            slot_doc = {
                "_id": appt.get("slot_id"),
                "date": appt.get("date"),
                "start": appt.get("start"),
                "end": appt.get("end"),
                "tecnico": appt.get("tecnico"),
                "status": "booked",
            }
            lead = await _sync_lead_with_sopralluogo_slot(raw, slot_doc)
        serialized = serialize(lead)
        if appt:
            # Fonte di verità calendario: arricchisce sempre la card pipeline
            serialized["sopralluogo"] = {
                **(serialized.get("sopralluogo") or {}),
                **appt,
            }
            serialized["has_sopralluogo"] = True
        else:
            serialized["has_sopralluogo"] = bool(serialized.get("sopralluogo"))
        synced_leads.append(serialized)

    cols = []
    for key, label in PIPELINE_STATI:
        items = [l for l in synced_leads if l.get("status") == key]
        for it in items:
            it["giorni_in_stato"] = _giorni_da(it.get("status_changed_at", it.get("created_at")))
        valore = sum((l.get("range_alto", 0) + l.get("range_basso", 0)) / 2 for l in items)
        cols.append({"key": key, "label": label, "count": len(items),
                     "valore": round(valore), "leads": items})
    return {"columns": cols}


@api.get("/sopralluoghi")
async def sopralluoghi(user: dict = Depends(current_user)):
    """Appuntamenti reali: slot prenotati dal calendario, arricchiti col lead collegato."""
    slots = await db.sopralluogo_slots.find({"status": "booked"}).sort([("date", 1), ("start", 1)]).to_list(500)
    out = []
    for slot in slots:
        lead = None
        if slot.get("lead_id") and ObjectId.is_valid(str(slot["lead_id"])):
            lead = await db.leads.find_one({"_id": ObjectId(str(slot["lead_id"]))})
        lead = serialize(lead) if lead else {}
        out.append({
            "id": str(slot["_id"]),
            "lead_id": slot.get("lead_id"),
            "cliente": lead.get("nome") or slot.get("booked_name"),
            "telefono": lead.get("telefono") or slot.get("booked_phone"),
            "email": lead.get("email") or slot.get("booked_email"),
            "citta": lead.get("citta"),
            "indirizzo": lead.get("indirizzo") or lead.get("citta") or "",
            "tipo_immobile": lead.get("tipo_immobile"),
            "mq": lead.get("mq"),
            "tecnico": slot.get("tecnico") or lead.get("owner") or "Da assegnare",
            "data": slot["date"],
            "ora": slot.get("start"),
            "ora_fine": slot.get("end"),
            "completato": lead.get("status") == "sopralluogo_fatto",
            "pipeline_status": lead.get("status"),
            "estimate": lead.get("estimate"),
        })
    return out


# ----------------------- Calendario sopralluoghi (slot) -----------------------
@api.get("/sopralluoghi/slots")
async def list_sopralluogo_slots(user: dict = Depends(current_user)):
    docs = await db.sopralluogo_slots.find({}).sort([("date", 1), ("start", 1)]).to_list(1000)
    return [serialize(d) for d in docs]


@api.post("/sopralluoghi/slots")
async def create_sopralluogo_slot(body: SopralluogoSlotCreate, user: dict = Depends(current_user)):
    try:
        slot_date = datetime.strptime(body.date, "%Y-%m-%d").date()
        start_time = datetime.strptime(body.start, "%H:%M").time()
        end_time = datetime.strptime(body.end, "%H:%M").time()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Data o orario non validi (attesi YYYY-MM-DD e HH:MM)",
        )
    if slot_date < datetime.now().date():
        raise HTTPException(status_code=400, detail="Non puoi creare uno slot nel passato")
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="L'orario di fine deve essere successivo all'inizio")
    duplicate = await db.sopralluogo_slots.find_one({"date": body.date, "start": body.start})
    if duplicate:
        raise HTTPException(status_code=409, detail="Esiste gia uno slot in questa data e orario")
    doc = {
        "date": body.date, "start": body.start, "end": body.end,
        "tecnico": (body.tecnico or "").strip() or None,
        "status": "free", "lead_id": None,
        "booked_name": None, "booked_email": None, "booked_phone": None,
        "created_by": user.get("name"), "created_at": now_iso(), "updated_at": now_iso(),
    }
    res = await db.sopralluogo_slots.insert_one(doc)
    doc["id"] = str(res.inserted_id)
    return serialize(doc)


@api.delete("/sopralluoghi/slots/{slot_id}")
async def delete_sopralluogo_slot(slot_id: str, user: dict = Depends(current_user)):
    oid = object_id_or_400(slot_id, "Slot")
    slot = await db.sopralluogo_slots.find_one({"_id": oid})
    if not slot:
        raise HTTPException(status_code=404, detail="Slot non trovato")
    if slot.get("status") == "booked":
        raise HTTPException(status_code=400, detail="Slot gia prenotato: gestiscilo dalla scheda del lead.")
    await db.sopralluogo_slots.delete_one({"_id": oid})
    return {"ok": True}


@api.get("/public/sopralluoghi/slots")
async def public_sopralluogo_slots():
    docs = await db.sopralluogo_slots.find(
        {"status": "free", "date": {"$gte": _today_iso()}}
    ).sort([("date", 1), ("start", 1)]).to_list(500)
    return [
        {"id": str(d["_id"]), "date": d["date"], "start": d["start"], "end": d["end"]}
        for d in docs
    ]


@api.post("/public/sopralluoghi/book")
async def public_book_sopralluogo(
    request: Request,
    body: SopralluogoBook,
    background_tasks: BackgroundTasks,
):
    await api_security.enforce_rate_limit(
        db,
        scope="public_booking",
        identity=_client_ip(request),
        limit=PUBLIC_BOOKING_MAX_PER_HOUR,
        window_seconds=60 * 60,
        detail="Troppe prenotazioni inviate. Riprova più tardi o contattaci telefonicamente.",
    )
    oid = object_id_or_400(body.slot_id, "Slot")
    # Claim atomico: solo se lo slot e ancora libero.
    claim = await db.sopralluogo_slots.update_one(
        {"_id": oid, "status": "free"},
        {"$set": {
            "status": "booked",
            "booked_name": body.nome,
            "booked_email": body.email.lower(),
            "booked_phone": body.telefono,
            "updated_at": now_iso(),
        }},
    )
    if claim.modified_count == 0:
        raise HTTPException(status_code=409, detail="Slot non piu disponibile. Scegli un altro orario.")
    slot = await db.sopralluogo_slots.find_one({"_id": oid})
    norm = meta_leads_service.normalize_email(body.email)
    sopr = {
        "slot_id": str(oid), "date": slot["date"], "start": slot["start"],
        "end": slot["end"], "tecnico": slot.get("tecnico"),
    }
    event = {
        "id": "ev-" + uuid.uuid4().hex[:8], "tipo": "sopralluogo",
        "testo": f"Sopralluogo prenotato dal cliente: {slot['date']} {slot['start']}-{slot['end']}",
        "ts": now_iso(),
    }
    # Anti-IDOR: onora lead_id solo se l'email della prenotazione coincide col lead indicato,
    # cosi un lead_id altrui non puo essere dirottato da un POST pubblico. Il match per sola
    # email collega comunque, ma senza mai sovrascrivere dati sensibili gia presenti.
    lead = None
    if body.lead_id and ObjectId.is_valid(body.lead_id) and norm:
        candidate = await db.leads.find_one({"_id": ObjectId(body.lead_id)})
        if candidate and candidate.get("email_norm") == norm:
            lead = candidate
    if not lead and norm:
        lead = await db.leads.find_one({"email_norm": norm})
    if lead:
        set_fields: Dict[str, Any] = {
            "sopralluogo": sopr,
            "updated_at": now_iso(),
        }
        # Non far retrocedere un lead gia avanzato: fissa lo stato solo da fasi iniziali.
        # Collega automaticamente la pipeline al modulo sopralluoghi.
        if lead.get("status") in SOPRALLUOGO_AUTO_PROMOTE_FROM:
            set_fields["status"] = "sopralluogo_fissato"
            if lead.get("status") != "sopralluogo_fissato":
                set_fields["status_changed_at"] = now_iso()
            set_fields["prossima_azione"] = (
                f"Sopralluogo il {slot['date']} alle {slot.get('start') or ''}".strip()
            )
        # Mai sovrascrivere l'indirizzo di un cliente esistente da endpoint pubblico: solo se mancante.
        if body.indirizzo and not (lead.get("indirizzo") or "").strip():
            set_fields["indirizzo"] = body.indirizzo.strip()
        await db.leads.update_one(
            {"_id": lead["_id"]},
            {"$set": set_fields, "$push": {"timeline": event}, "$addToSet": {"tags": "Sopralluogo"}},
        )
        lead_id = str(lead["_id"])
        email_lead = {**lead, **set_fields, "id": lead_id}
    else:
        doc = {
            "nome": body.nome, "email": body.email.lower(), "telefono": body.telefono,
            "email_norm": norm, "phone_norm": meta_leads_service.normalize_phone(body.telefono),
            "citta": body.citta or "", "indirizzo": (body.indirizzo or "").strip(),
            "tipo_immobile": "-", "mq": 0, "livello": "premium", "bagni": 0, "camere": 0,
            "ambienti": [], "stile": "-", "tempistiche": "Sto valutando",
            "origine": "sopralluogo", "fonti": ["sopralluogo"],
            "status": "sopralluogo_fissato", "owner": None, "score": 60, "tags": ["Sopralluogo"],
            "has_files": False, "note_cliente": body.note or "", "range_basso": 0, "range_alto": 0,
            "estimate": None, "prossima_azione": "Confermare il sopralluogo e preparare il rilievo",
            "sopralluogo": sopr,
            "timeline": [event],
            "created_at": now_iso(), "last_contact": now_iso(), "status_changed_at": now_iso(),
        }
        res = await db.leads.insert_one(doc)
        lead_id = str(res.inserted_id)
        doc["id"] = lead_id
        email_lead = doc
    await db.sopralluogo_slots.update_one({"_id": oid}, {"$set": {"lead_id": lead_id}})
    # Conferma sopralluogo al cliente + notifica staff, sia per lead nuovo che esistente.
    email_service.enqueue_lead_emails(background_tasks, email_lead, "sopralluogo")
    return {
        "ok": True, "lead_id": lead_id,
        "slot": {"date": slot["date"], "start": slot["start"], "end": slot["end"]},
        "pipeline_status": "sopralluogo_fissato",
    }


@api.post("/sopralluoghi/{slot_id}/complete")
async def complete_sopralluogo(slot_id: str, user: dict = Depends(current_user)):
    """Segna il sopralluogo come svolto e avanza la pipeline a «Sopralluogo fatto»."""
    oid = object_id_or_400(slot_id, "Slot")
    slot = await db.sopralluogo_slots.find_one({"_id": oid})
    if not slot:
        raise HTTPException(status_code=404, detail="Slot non trovato")
    if slot.get("status") != "booked":
        raise HTTPException(status_code=400, detail="Lo slot non risulta prenotato")

    lead = None
    lead_id = slot.get("lead_id")
    if lead_id and ObjectId.is_valid(str(lead_id)):
        lead = await db.leads.find_one({"_id": ObjectId(str(lead_id))})
    if not lead:
        raise HTTPException(
            status_code=400,
            detail="Slot senza lead collegato: apri la scheda e collega il cliente.",
        )

    # Non toccare lead già oltre la fase sopralluogo (preventivo / trattativa / chiuso).
    advanced = {
        "preventivo_preparazione",
        "preventivo_inviato",
        "follow_up",
        "in_trattativa",
        "chiuso_vinto",
        "chiuso_perso",
        "sopralluogo_fatto",
    }
    set_fields: Dict[str, Any] = {
        "sopralluogo": {
            **_slot_appointment_payload(slot),
            "completato": True,
            "completato_at": now_iso(),
            "completato_da": user.get("name"),
        },
        "updated_at": now_iso(),
        "last_contact": now_iso(),
    }
    if lead.get("status") not in advanced:
        set_fields["status"] = "sopralluogo_fatto"
        set_fields["status_changed_at"] = now_iso()
        set_fields["prossima_azione"] = "Preparare il preventivo post-sopralluogo"

    event = {
        "id": "ev-" + uuid.uuid4().hex[:8],
        "tipo": "sopralluogo",
        "testo": (
            f"Sopralluogo completato ({slot.get('date')} {slot.get('start')}-{slot.get('end')}) "
            f"da {user.get('name')}"
        ),
        "ts": now_iso(),
    }
    await db.leads.update_one(
        {"_id": lead["_id"]},
        {"$set": set_fields, "$push": {"timeline": event}, "$addToSet": {"tags": "Sopralluogo fatto"}},
    )
    await db.sopralluogo_slots.update_one(
        {"_id": oid},
        {"$set": {"completed": True, "completed_at": now_iso(), "updated_at": now_iso()}},
    )
    updated = await db.leads.find_one({"_id": lead["_id"]})
    return {
        "ok": True,
        "lead_id": str(lead["_id"]),
        "pipeline_status": (updated or {}).get("status") or set_fields.get("status"),
        "slot_id": str(oid),
    }


@api.post("/preventivi")
async def create_preventivo(body: StaffPreventivoCreate, user: dict = Depends(current_user)):
    """Preventivo creato manualmente dallo staff (cliente da telefono/sportello).

    Calcola la stima col motore predittivo e crea un lead in fase preventivo,
    intestato allo staff. Niente email automatica: lo staff invia manualmente.
    """
    cfg = normalize_config(body.config.model_dump())
    if cfg.get("ai_architect_job_id") and not ObjectId.is_valid(str(cfg["ai_architect_job_id"])):
        cfg["ai_architect_job_id"] = None
    est = calcola_preventivo(cfg)
    score = lead_score(cfg, cfg.get("has_files", False))
    pkg = est["pacchetti"][cfg["livello"]]
    tags = ["Staff"]
    if cfg["livello"] in ("premium", "luxury"):
        tags.append(cfg["livello"].capitalize())
    doc = {
        "nome": body.nome, "email": body.email.lower(), "telefono": body.telefono,
        "email_norm": meta_leads_service.normalize_email(body.email),
        "phone_norm": meta_leads_service.normalize_phone(body.telefono),
        "citta": body.citta, "indirizzo": (body.indirizzo or "").strip(),
        "newsletter": False, "privacy": False,
        "tipo_immobile": cfg["tipo_immobile"], "mq": cfg["mq"], "livello": cfg["livello"],
        "bagni": cfg["bagni"], "camere": cfg["camere"], "cucina": cfg["cucina"],
        "ambienti": cfg["ambienti"], "stile": cfg["stile"], "tempistiche": cfg["tempistiche"],
        "origine": "staff", "fonti": ["staff"], "status": "preventivo_preparazione",
        "owner": user.get("name"), "score": score, "tags": tags,
        "has_files": False, "note_cliente": "",
        "range_basso": pkg["range_basso"], "range_alto": pkg["range_alto"],
        "estimate": est, "prossima_azione": "Verificare i dati e inviare il preventivo al cliente",
        "timeline": [{"id": "ev-" + uuid.uuid4().hex[:8], "tipo": "lead_ricevuto",
                      "testo": f"Preventivo creato da {user.get('name') or 'staff'} - "
                               f"{cfg['tipo_immobile']} {cfg['mq']}mq a {body.citta}",
                      "ts": now_iso(), "autore": user.get("name")}],
        "created_at": now_iso(), "last_contact": now_iso(), "status_changed_at": now_iso(),
    }
    res = await db.leads.insert_one(doc)
    return {"id": str(res.inserted_id), "estimate": est, "score": score}


@api.get("/preventivi")
async def preventivi(request: Request, user: dict = Depends(current_user)):
    pg_preventivi = []
    tenant_slug = tenancy.DEFAULT_TENANT_SLUG
    if db_pg.pool_ready():
        async with get_tenant_conn(request, user) as (conn, tenant):
            tenant_slug = tenant["slug"]
            pg_preventivi = await boq_service.lista_preventivi(conn, tenant["id"])

    # I documenti runtime appartengono alla sola GB Construction. Per gli
    # altri tenant mostrarli sarebbe una fuga dati cross-tenant.
    if tenant_slug != tenancy.DEFAULT_TENANT_SLUG:
        return pg_preventivi

    leads = await db.leads.find({"status": {"$in": [
        "preventivo_preparazione", "preventivo_inviato", "follow_up", "in_trattativa",
        "chiuso_vinto", "chiuso_perso"]}}).sort("status_changed_at", -1).to_list(500)
    out = []
    for d in leads:
        d = serialize(d)
        out.append({
            "id": d["id"], "cliente": d["nome"], "citta": d.get("citta"),
            "livello": d.get("livello"), "range_basso": d.get("range_basso"),
            "range_alto": d.get("range_alto"), "status": d.get("status"),
            "giorni_silenzio": _giorni_da(d.get("status_changed_at", d.get("created_at"))),
            "telefono": d.get("telefono"), "email": d.get("email"),
        })
    return pg_preventivi + out


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _default_cantiere_fasi() -> List[Dict[str, str]]:
    return [dict(fase) for fase in DEFAULT_CANTIERE_FASI]


def _validate_cantiere_stato(stato: Optional[str]) -> str:
    clean = _clean_text(stato) or "attivo"
    if clean not in CANTIERE_STATI:
        raise HTTPException(status_code=400, detail="Stato cantiere non valido")
    return clean


def _normalize_cantiere_fasi(fasi: Optional[List[CantiereFase]]) -> List[Dict[str, str]]:
    if not fasi:
        return _default_cantiere_fasi()
    out = []
    for fase in fasi:
        raw = fase.model_dump() if hasattr(fase, "model_dump") else dict(fase)
        nome = _clean_text(raw.get("nome"))
        stato = _clean_text(raw.get("stato")) or "da_iniziare"
        if not nome:
            continue
        if stato not in CANTIERE_FASE_STATI:
            raise HTTPException(status_code=400, detail=f"Stato fase non valido: {stato}")
        out.append({"nome": nome, "stato": stato})
    if not out:
        raise HTTPException(status_code=400, detail="Inserisci almeno una fase")
    return out


def _lead_importo_medio(lead: Optional[Dict[str, Any]]) -> float:
    if not lead:
        return 0
    basso = float(lead.get("range_basso") or 0)
    alto = float(lead.get("range_alto") or 0)
    return round((basso + alto) / 2) if basso or alto else 0


async def _hydrate_cantiere_telefoni(
    docs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    missing_by_lead: Dict[str, List[Dict[str, Any]]] = {}
    for doc in docs:
        if _clean_text(doc.get("telefono")):
            continue
        lead_id = _clean_text(doc.get("lead_id"))
        if not lead_id or not ObjectId.is_valid(lead_id):
            continue
        missing_by_lead.setdefault(lead_id, []).append(doc)
    if not missing_by_lead:
        return docs

    leads = await db.leads.find(
        {"_id": {"$in": [ObjectId(lead_id) for lead_id in missing_by_lead]}},
        {"telefono": 1},
    ).to_list(len(missing_by_lead))
    for lead in leads:
        telefono = _clean_text(lead.get("telefono"))
        if not telefono:
            continue
        for doc in missing_by_lead.get(str(lead.get("_id")), []):
            doc["telefono"] = telefono
    return docs


async def _load_cantiere_lead(lead_id: Optional[str]) -> Optional[Dict[str, Any]]:
    lead_id = _clean_text(lead_id)
    if not lead_id:
        return None
    oid = object_id_or_400(lead_id, "Lead")
    lead = await db.leads.find_one({"_id": oid})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead collegato non trovato")
    return lead


def _build_cantiere_doc(body: CantiereCreate, lead: Optional[Dict[str, Any]], user: dict) -> Dict[str, Any]:
    data = body.model_dump()
    cliente = _clean_text(data.get("cliente")) or _clean_text(lead.get("nome") if lead else "")
    if not cliente:
        raise HTTPException(status_code=400, detail="Cliente obbligatorio")
    indirizzo = _clean_text(data.get("indirizzo"))
    if not indirizzo and lead:
        indirizzo = _clean_text(lead.get("indirizzo")) or _clean_text(lead.get("citta"))
    capocantiere = _clean_text(data.get("capocantiere"))
    if not capocantiere and lead:
        capocantiere = _clean_text(lead.get("owner"))
    doc = {
        "cliente": cliente,
        "telefono": _clean_text(data.get("telefono"))
        or _clean_text(lead.get("telefono") if lead else "")
        or None,
        "indirizzo": indirizzo,
        "avanzamento": int(data.get("avanzamento") or 0),
        "milestone": _clean_text(data.get("milestone")) or "Apertura cantiere",
        "milestone_data": _clean_text(data.get("milestone_data")) or None,
        "capocantiere": capocantiere or "Da assegnare",
        "importo": float(data.get("importo") or _lead_importo_medio(lead)),
        "criticita": _clean_text(data.get("criticita")) or None,
        "fasi": _normalize_cantiere_fasi(body.fasi),
        "stato": _validate_cantiere_stato(data.get("stato")),
        "lead_id": _clean_text(data.get("lead_id")) or None,
        "note": _clean_text(data.get("note")),
        "created_by": user.get("name") or user.get("email"),
        "updated_by": user.get("name") or user.get("email"),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    if doc["stato"] == "completato":
        doc["completed_at"] = now_iso()
        doc["avanzamento"] = 100
    return doc


async def _mark_lead_as_cantiere(lead: Dict[str, Any], cantiere_id: str, user: dict):
    event = {
        "id": "ev-" + uuid.uuid4().hex[:8],
        "tipo": "cantiere",
        "testo": f"Cantiere avviato da {user.get('name') or 'staff'}",
        "ts": now_iso(),
        "autore": user.get("name"),
    }
    set_fields = {
        "cantiere_id": cantiere_id,
        "last_contact": now_iso(),
        "updated_at": now_iso(),
    }
    if lead.get("status") != "chiuso_vinto":
        set_fields["status"] = "chiuso_vinto"
        set_fields["status_changed_at"] = now_iso()
    await db.leads.update_one(
        {"_id": lead["_id"]},
        {
            "$set": set_fields,
            "$addToSet": {"tags": "Cantiere"},
            "$push": {"timeline": {"$each": [event], "$position": 0}},
        },
    )


@api.get("/cantieri")
async def cantieri(stato: Optional[str] = "attivo", user: dict = Depends(current_user)):
    query: Dict[str, Any] = {}
    if stato and stato != "tutti":
        clean_stato = _validate_cantiere_stato(stato)
        if clean_stato == "attivo":
            query["$or"] = [{"stato": "attivo"}, {"stato": {"$exists": False}}]
        else:
            query["stato"] = clean_stato
    docs = await db.cantieri.find(query).sort([("milestone_data", 1), ("updated_at", -1)]).to_list(500)
    await _hydrate_cantiere_telefoni(docs)
    return [serialize(d) for d in docs]


@api.get("/cantieri/{cantiere_id}")
async def get_cantiere(cantiere_id: str, user: dict = Depends(current_user)):
    """Restituisce un singolo cantiere per la schermata operativa dedicata."""
    oid = object_id_or_400(cantiere_id, "Cantiere")
    doc = await db.cantieri.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Cantiere non trovato")
    await _hydrate_cantiere_telefoni([doc])
    return serialize(doc)


@api.post("/cantieri")
async def create_cantiere(body: CantiereCreate, user: dict = Depends(current_user)):
    lead = await _load_cantiere_lead(body.lead_id)
    lead_id = _clean_text(body.lead_id)
    if lead_id:
        duplicate = await db.cantieri.find_one({"lead_id": lead_id, "stato": {"$ne": "completato"}})
        if duplicate:
            raise HTTPException(status_code=409, detail="Esiste gia un cantiere attivo collegato a questo lead")
    doc = _build_cantiere_doc(body, lead, user)
    res = await db.cantieri.insert_one(doc)
    cantiere_id = str(res.inserted_id)
    if lead:
        await _mark_lead_as_cantiere(lead, cantiere_id, user)
    saved = await db.cantieri.find_one({"_id": res.inserted_id})
    return serialize(saved)


@api.patch("/cantieri/{cantiere_id}")
async def update_cantiere(cantiere_id: str, body: CantiereUpdate, user: dict = Depends(current_user)):
    oid = object_id_or_400(cantiere_id, "Cantiere")
    existing = await db.cantieri.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Cantiere non trovato")
    data = body.model_dump(exclude_unset=True)
    updates: Dict[str, Any] = {}

    for field in ("indirizzo", "milestone", "capocantiere", "note"):
        if field in data:
            updates[field] = _clean_text(data.get(field))
    if "cliente" in data:
        cliente = _clean_text(data.get("cliente"))
        if not cliente:
            raise HTTPException(status_code=400, detail="Cliente obbligatorio")
        updates["cliente"] = cliente
    if "telefono" in data:
        updates["telefono"] = _clean_text(data.get("telefono")) or None
    if "criticita" in data:
        updates["criticita"] = _clean_text(data.get("criticita")) or None
    if "milestone_data" in data:
        updates["milestone_data"] = _clean_text(data.get("milestone_data")) or None
    if "avanzamento" in data and data.get("avanzamento") is not None:
        updates["avanzamento"] = int(data["avanzamento"])
    if "importo" in data and data.get("importo") is not None:
        updates["importo"] = float(data["importo"])
    if "fasi" in data:
        updates["fasi"] = _normalize_cantiere_fasi(body.fasi)
    if "stato" in data:
        updates["stato"] = _validate_cantiere_stato(data.get("stato"))
        if updates["stato"] == "completato":
            updates["avanzamento"] = 100
            updates["completed_at"] = now_iso()
    if "lead_id" in data:
        lead = await _load_cantiere_lead(data.get("lead_id"))
        updates["lead_id"] = _clean_text(data.get("lead_id")) or None
        if lead:
            if not _clean_text(existing.get("telefono")):
                updates["telefono"] = _clean_text(lead.get("telefono")) or None
            await _mark_lead_as_cantiere(lead, cantiere_id, user)

    if not updates:
        return serialize(existing)
    updates["updated_at"] = now_iso()
    updates["updated_by"] = user.get("name") or user.get("email")
    await db.cantieri.update_one({"_id": oid}, {"$set": updates})
    saved = await db.cantieri.find_one({"_id": oid})
    await _hydrate_cantiere_telefoni([saved])
    return serialize(saved)


@api.delete("/cantieri/{cantiere_id}")
async def delete_cantiere(cantiere_id: str, user: dict = Depends(require_admin)):
    oid = object_id_or_400(cantiere_id, "Cantiere")
    existing = await db.cantieri.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Cantiere non trovato")
    res = await db.cantieri.delete_one({"_id": oid})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cantiere non trovato")

    lead_id = _clean_text(existing.get("lead_id"))
    if lead_id and ObjectId.is_valid(lead_id):
        event = {
            "id": "ev-" + uuid.uuid4().hex[:8],
            "tipo": "cantiere",
            "testo": f"Cantiere eliminato da {user.get('name') or 'amministratore'}",
            "ts": now_iso(),
            "autore": user.get("name"),
        }
        await db.leads.update_one(
            {"_id": ObjectId(lead_id), "cantiere_id": cantiere_id},
            {
                "$unset": {"cantiere_id": ""},
                "$set": {"last_contact": event["ts"], "updated_at": event["ts"]},
                "$push": {"timeline": {"$each": [event], "$position": 0}},
            },
        )
    return {"ok": True, "deleted": cantiere_id}


REPORT_PERIOD = Literal["30d", "90d", "180d", "365d", "all"]


async def _sales_report(period: REPORT_PERIOD) -> dict:
    # Nessun limite artificiale: il precedente to_list(1000) rendeva i KPI
    # incompleti appena lo storico superava mille lead. La collection e gia
    # filtrata per tenant dall'adapter Postgres.
    projection = {
        "nome": 1,
        "citta": 1,
        "tipo_immobile": 1,
        "livello": 1,
        "status": 1,
        "range_basso": 1,
        "range_alto": 1,
        "created_at": 1,
        "status_changed_at": 1,
    }
    leads = await db.leads.find({}, projection).to_list(None)
    return report_service.build_sales_report(
        [serialize(document) for document in leads],
        period=period,
    )


@api.get("/reports")
async def reports(
    period: REPORT_PERIOD = Query("all"),
    user: dict = Depends(require_admin),
):
    return await _sales_report(period)


@api.post("/reports/insights")
async def reports_insights(
    period: REPORT_PERIOD = Query("all"),
    user: dict = Depends(require_admin),
):
    rep = await _sales_report(period)
    provider_available = ai_service.ai_available()
    if provider_available:
        await ai_credit_service.require_available_for_generation(
            db,
            ai_credit_service.RATE_CARD["report_insights"]["credits"],
            user=user,
        )
    try:
        text, source = await ai_service.generate_insights(
            {
                **rep["kpi"],
                "period_label": rep.get("meta", {}).get("period_label"),
            }
        )
    except Exception as e:
        logger.exception("insights failed")
        raise HTTPException(status_code=502, detail=f"Servizio AI non disponibile: {e}")
    if source == "ai":
        await ai_credit_service.charge_credits(
            db,
            action_key="report_insights",
            idempotency_key=f"report_insights:{user.get('id')}:{uuid.uuid4().hex}",
            user=user,
            metadata={"kpi": rep.get("kpi"), "period": period},
        )
    return {"insights": text, "source": source}


# ----------------------- AI credits -----------------------
@api.get("/ai-credits")
async def ai_credits_summary(user: dict = Depends(current_user)):
    return await ai_credit_service.summary(db, user=user)


@api.post("/ai-credits/packs")
async def grant_ai_credit_pack(body: AiCreditPackGrant, user: dict = Depends(require_admin)):
    pack = await ai_credit_service.grant_pack(
        db,
        credits=body.credits,
        amount_eur=body.amount_eur,
        label=body.label,
        notes=body.notes,
        user=user,
    )
    return {"pack": pack, "summary": await ai_credit_service.summary(db, user=user)}


# ----------------------- Settings / admin -----------------------
@api.get("/coefficienti")
async def get_coefficienti(user: dict = Depends(current_user)):
    return COEFFICIENTI


@api.get("/voci")
async def get_voci(user: dict = Depends(current_user)):
    return voci_as_dicts()


@api.get("/staff")
async def list_staff(user: dict = Depends(current_user)):
    docs = await db.users.find({}, {"password_hash": 0}).to_list(100)
    return [serialize(d) for d in docs]


@api.post("/staff")
async def create_staff(body: StaffCreate, user: dict = Depends(require_admin)):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email gia' registrata")
    doc = {"email": email, "password_hash": authlib.hash_password(body.password),
           "name": body.nome, "role": body.role, "created_at": now_iso()}
    res = await db.users.insert_one(doc)
    return {"id": str(res.inserted_id), "email": email, "name": body.nome, "role": body.role}


# ----------------------- Startup -----------------------
@asynccontextmanager
async def get_tenant_conn(request: Request, user: dict):
    """Apre una connessione Postgres con RLS tenant, se il pool è configurato.

    Supporta JWT Supabase e staff legacy GB (claim sintetici + membership seed).
    Tenant di default: gbconstruction (landing su dominio GB attuale).
    """
    if not db_pg.pool_ready():
        raise HTTPException(
            status_code=503,
            detail="Database Supabase non configurato (CONNECTION_STRING_SUPABASE / SUPABASE_DB_URL)",
        )
    from legacy_tenant import claims_for_user, map_legacy_user

    user = map_legacy_user(user)
    if user.get("auth_provider") == "supabase" and user.get("access_token"):
        token = user["access_token"]
        try:
            async with db_pg.tenant_conn(token) as conn:
                tenant = await tenancy.current_tenant(request, user, conn=conn)
                yield conn, tenant
            return
        except Exception:
            # fallback a claim sintetici se JWKS/claim incompleti
            pass

    claims = claims_for_user(user)
    async with db_pg.tenant_conn_claims(claims) as conn:
        tenant = await tenancy.current_tenant(request, user, conn=conn)
        yield conn, tenant


register_edilos_routes(api, db, get_tenant_conn)
register_financial_routes(api, db, get_tenant_conn)


_payment_reminders_task: asyncio.Task | None = None


async def _payment_reminders_loop() -> None:
    """Processa la coda senza dipendere da una richiesta aperta nel browser."""
    while True:
        try:
            from system_jobs.payment_reminders import run as run_payment_reminders

            result = await run_payment_reminders()
            if result.get("candidate"):
                logger.info("Promemoria economici processati: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Promemoria economici non processati: %s", exc)
        await asyncio.sleep(15 * 60)


@app.on_event("startup")
async def startup():
    global _payment_reminders_task
    authlib.validate_production_security_configuration()
    await db_pg.init_pool()
    if not db_pg.pool_ready():
        raise RuntimeError(
            "Supabase non configurato: imposta CONNECTION_STRING_SUPABASE o SUPABASE_DB_URL"
        )
    await db.startup()
    logger.info("Postgres pool ready; Supabase is the canonical runtime store")
    try:
        from system_jobs.sync_campania_prezzario import run as sync_campania

        sync_result = await sync_campania()
        logger.info("Prezzario Campania 2026 verificato: %s", sync_result)
    except Exception as sync_exc:
        logger.warning("Sync Prezzario Campania non eseguito: %s", sync_exc)
    _payment_reminders_task = asyncio.create_task(
        _payment_reminders_loop(), name="payment-reminders"
    )
    await db.users.create_index("email", unique=True)
    await db.leads.create_index("origine")
    await db.leads.create_index("email_norm")
    await db.leads.create_index("phone_norm")
    await db.leads.create_index(
        "external_ids.meta_leadgen_id",
        unique=True,
        partialFilterExpression={"external_ids.meta_leadgen_id": {"$type": "string"}},
    )
    await db.meta_webhook_events.create_index("leadgen_id", unique=True)
    await db.meta_webhook_events.create_index([("status", 1), ("last_received_at", -1)])
    await db.sopralluogo_slots.create_index([("date", 1), ("start", 1)])
    await db.sopralluogo_slots.create_index("status")
    await db.cantieri.create_index("stato")
    await db.cantieri.create_index("lead_id")
    await db.ai_architect_jobs.create_index("created_at")
    await db.ai_architect_jobs.create_index("lead_id")
    await db.ai_architect_jobs.create_index("file_hash")
    await db.ai_architect_outputs.create_index([("job_id", 1), ("created_at", 1)])
    await db.ai_architect_errors.create_index([("job_id", 1), ("created_at", -1)])
    await db.ai_architect_quality_logs.create_index([("job_id", 1), ("gate_id", 1), ("timestamp", -1)])
    await ai_architect_service.ensure_upload_rate_limit_indexes(db)
    await db.ai_architect_cache.create_index(
        [("cache_type", 1), ("file_hash", 1), ("schema_version", 1), ("provider", 1), ("model", 1)],
        unique=True,
    )
    await db.ai_credit_buckets.create_index("key", unique=True)
    await db.ai_credit_buckets.create_index([("account_id", 1), ("bucket_type", 1), ("expires_at", 1)])
    await db.ai_credit_ledger.create_index("idempotency_key", unique=True)
    await db.ai_credit_ledger.create_index([("account_id", 1), ("created_at", -1)])
    await db.ai_usage_events.create_index([("account_id", 1), ("created_at", -1)])
    await api_security.ensure_rate_limit_indexes(db)
    await ai_credit_service.ensure_base_credit_pack(db)
    await authlib.seed_users(db)
    await authlib.disable_legacy_demo_users(db)
    demo_seed_enabled = os.getenv("ENABLE_DEMO_SEED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if demo_seed_enabled:
        if await db.leads.count_documents({}) == 0:
            await db.leads.insert_many(seed_data.build_demo_leads())
            logger.info("Seeded demo leads")
        if await db.cantieri.count_documents({}) == 0:
            await db.cantieri.insert_many(seed_data.build_demo_cantieri())
            logger.info("Seeded demo cantieri")
    await db.cantieri.update_many(
        {"stato": {"$exists": False}},
        {"$set": {"stato": "attivo", "updated_at": now_iso()}},
    )


@app.on_event("shutdown")
async def shutdown():
    global _payment_reminders_task
    if _payment_reminders_task:
        _payment_reminders_task.cancel()
        try:
            await _payment_reminders_task
        except asyncio.CancelledError:
            pass
        _payment_reminders_task = None
    await db_pg.close_pool()


app.include_router(api)
app.mount(
    "/api/ai-architect/files",
    StaticFiles(directory=str(ai_architect_service.STORAGE_DIR)),
    name="ai_architect_files",
)


@app.middleware("http")
async def ai_architect_staff_access(request: Request, call_next):
    is_ai_architect_path = request.url.path.startswith("/api/ai-architect/")
    if is_ai_architect_path and request.method.upper() != "OPTIONS":
        try:
            user = await current_user(request)
            if user.get("role") not in {"admin", "staff", "operations"}:
                raise HTTPException(status_code=403, detail="Accesso staff richiesto")
        except HTTPException:
            return JSONResponse(
                status_code=404,
                content={
                    "detail": "AI Architect e disponibile solo allo staff."
                },
            )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=(), payment=()",
    )
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip() and origin.strip() != "*"
    ],
    allow_origin_regex=os.environ.get("CORS_ORIGIN_REGEX", DEFAULT_CORS_ORIGIN_REGEX),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Slug"],
)
