from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR.parent / '.env')
load_dotenv(ROOT_DIR / '.env', override=True)

import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends, Query, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
import json

import auth as authlib
from predictive_engine import calcola_preventivo, lead_score
from predictive_data import COEFFICIENTI, voci_as_dicts
import seed_data
import ai_service
import ai_architect_service
import meta_leads_service

mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'gb_construction')]

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


# ----------------------- Models -----------------------
class LoginBody(BaseModel):
    email: EmailStr
    password: str


class LeadConfig(BaseModel):
    tipo_immobile: str = "appartamento"
    mq: int = 80
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
    stile: str = "Moderno minimal"
    tempistiche: str = "Sto valutando"
    has_files: bool = False
    ai_architect_job_id: Optional[str] = None
    ai_architect_summary: Optional[str] = None


class LeadCreate(BaseModel):
    nome: str
    email: EmailStr
    telefono: str
    citta: str
    privacy: bool = True
    newsletter: bool = False
    tracking: Dict[str, Any] = Field(default_factory=dict)
    config: LeadConfig


class EstimateBody(BaseModel):
    config: LeadConfig


class CallbackBody(BaseModel):
    nome: str
    telefono: str
    messaggio: Optional[str] = ""


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
    nome: str
    email: EmailStr
    password: str
    role: str = "staff"


class AiArchitectConfirm(BaseModel):
    plan_type_selected: str


class AiArchitectApprove(BaseModel):
    reviewer: Optional[str] = "GB Construction"
    notes: Optional[str] = None


class AiArchitectRegenerate(BaseModel):
    output_types: Optional[List[str]] = None
    style_selected: Optional[str] = None


class AiProjectQuoteCreate(BaseModel):
    nome: str
    email: EmailStr
    telefono: str
    citta: str
    privacy: bool = True
    newsletter: bool = False
    tracking: Dict[str, Any] = Field(default_factory=dict)
    ai_architect_job_id: str
    config: LeadConfig


# ----------------------- Auth routes -----------------------
@api.post("/auth/login")
async def login(body: LoginBody, response: Response):
    email = body.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not authlib.verify_password(body.password, user["password_hash"]):
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
        response.set_cookie("access_token", access, httponly=True, secure=False,
                            samesite="lax", max_age=43200, path="/")
        return {"ok": True}
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token non valido")


# ----------------------- Public routes -----------------------
@api.get("/")
async def root():
    return {"service": "GB Construction Lead Engine", "status": "ok"}


@api.get("/webhooks/meta")
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
            os.environ.get("META_PAGE_ACCESS_TOKEN"),
            os.environ.get("META_GRAPH_API_VERSION", "v23.0"),
        )
    return {"ok": True, "received": len(events)}


@api.get("/integrations/meta/status")
async def meta_integration_status(user: dict = Depends(current_user)):
    last_event = await db.meta_webhook_events.find({}).sort("last_received_at", -1).to_list(1)
    failed_count = await db.meta_webhook_events.count_documents({"status": "failed"})
    meta_leads = await db.leads.count_documents({"origine": "meta_ads"})
    return {
        "configured": {
            "verify_token": bool(os.environ.get("META_VERIFY_TOKEN")),
            "app_secret": bool(os.environ.get("META_APP_SECRET")),
            "page_access_token": bool(os.environ.get("META_PAGE_ACCESS_TOKEN")),
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
            os.environ.get("META_PAGE_ACCESS_TOKEN"),
            os.environ.get("META_GRAPH_API_VERSION", "v23.0"),
        )
    return {"queued": len(events)}


@api.post("/estimate")
async def estimate(body: EstimateBody):
    return calcola_preventivo(normalize_config(body.config.model_dump()))


@api.get("/projects")
async def projects():
    return seed_data.DEMO_PROJECTS


@api.post("/leads")
async def create_lead(body: LeadCreate):
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
        "citta": body.citta, "newsletter": body.newsletter,
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
    if cfg.get("ai_architect_job_id"):
        await db.ai_architect_jobs.update_one(
            {"_id": ObjectId(cfg["ai_architect_job_id"])},
            {"$set": {"lead_id": str(res.inserted_id), "updated_at": now_iso()}},
        )
    return {"id": str(res.inserted_id), "estimate": est, "score": score}


@api.post("/callback")
async def callback(body: CallbackBody):
    doc = {
        "nome": body.nome, "email": "", "telefono": body.telefono, "citta": "",
        "email_norm": "", "phone_norm": meta_leads_service.normalize_phone(body.telefono),
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


@api.post("/ai-architect/jobs")
async def create_ai_architect_job(
    background_tasks: BackgroundTasks,
    planimetria: UploadFile = File(...),
    plan_type_selected: str = Form(...),
    style_selected: str = Form(...),
    project_goal: str = Form(...),
    priorities: str = Form("[]"),
    sqm: Optional[float] = Form(None),
    residents: Optional[int] = Form(None),
    budget: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
):
    job = await ai_architect_service.create_job(
        db,
        upload=planimetria,
        plan_type_selected=plan_type_selected,
        style_selected=style_selected,
        project_goal=project_goal,
        priorities=_parse_priorities(priorities),
        sqm=sqm,
        residents=residents,
        budget=budget,
        notes=notes,
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
async def reanalyze_ai_architect_job(job_id: str, background_tasks: BackgroundTasks):
    if not await db.ai_architect_jobs.find_one({"_id": ObjectId(job_id)}):
        raise HTTPException(status_code=404, detail="Progetto AI Architect non trovato")
    await ai_architect_service.ensure_processed_reference(db, job_id)
    await db.ai_architect_outputs.delete_many({
        "job_id": job_id,
        "output_type": {"$in": [
            "analysis",
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
async def approve_ai_architect_job(job_id: str, body: AiArchitectApprove, background_tasks: BackgroundTasks):
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
async def regenerate_ai_architect_job(job_id: str, body: AiArchitectRegenerate, background_tasks: BackgroundTasks):
    await db.ai_architect_jobs.update_one(
        {"_id": ObjectId(job_id)},
        {"$set": {
            "status": "processing",
            "current_step": "renders",
            "progress_percentage": 70,
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
    )
    return await ai_architect_service.get_job_payload(db, job_id)


@api.get("/ai-architect/jobs/{job_id}/report")
async def ai_architect_report(job_id: str):
    path = await ai_architect_service.report_path_for_job(db, job_id)
    return FileResponse(path, media_type="application/pdf", filename=f"GB-AI-Architect-{job_id}.pdf")


@api.post("/quote/from-ai-project")
async def quote_from_ai_project(body: AiProjectQuoteCreate):
    ai_job_oid = object_id_or_400(body.ai_architect_job_id, "Progetto AI Architect")
    job = await db.ai_architect_jobs.find_one({"_id": ai_job_oid})
    if not job:
        raise HTTPException(status_code=404, detail="Progetto AI Architect non trovato")

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
        "citta": body.citta, "newsletter": body.newsletter,
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
    await db.ai_architect_jobs.update_one(
        {"_id": ai_job_oid},
        {"$set": {"lead_id": str(res.inserted_id), "updated_at": now_iso()}},
    )
    return {"id": str(res.inserted_id), "estimate": est, "score": score, "ai_architect_job_id": body.ai_architect_job_id}


# ----------------------- Staff: leads -----------------------
@api.get("/leads")
async def list_leads(request: Request, status: Optional[str] = None,
                     q: Optional[str] = None, owner: Optional[str] = None,
                     origine: Optional[str] = None,
                     user: dict = Depends(current_user)):
    query: Dict[str, Any] = {}
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
        query["origine"] = origine
    if q:
        query["$or"] = [{"nome": {"$regex": q, "$options": "i"}},
                        {"citta": {"$regex": q, "$options": "i"}},
                        {"email": {"$regex": q, "$options": "i"}}]
    docs = await db.leads.find(query).sort("created_at", -1).to_list(500)
    return [serialize(d) for d in docs]


@api.get("/leads/counts")
async def lead_counts(user: dict = Depends(current_user)):
    docs = await db.leads.find({}, {"status": 1}).to_list(1000)
    counts: Dict[str, int] = {}
    for d in docs:
        counts[d.get("status", "nuovo")] = counts.get(d.get("status", "nuovo"), 0) + 1
    return {"counts": counts, "totale": len(docs)}


@api.get("/leads/{lead_id}")
async def get_lead(lead_id: str, user: dict = Depends(current_user)):
    doc = await db.leads.find_one({"_id": ObjectId(lead_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Lead non trovato")
    return serialize(doc)


@api.patch("/leads/{lead_id}")
async def update_lead(lead_id: str, body: LeadUpdate, user: dict = Depends(current_user)):
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
    return serialize(doc)


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
    try:
        suggestion = await ai_service.suggest_next_action(serialize(doc))
    except Exception as e:
        logger.exception("AI suggest failed")
        raise HTTPException(status_code=502, detail=f"Servizio AI non disponibile: {e}")
    await db.leads.update_one({"_id": ObjectId(lead_id)}, {"$set": {"prossima_azione": suggestion}})
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


@api.get("/pipeline")
async def pipeline(user: dict = Depends(current_user)):
    leads = await db.leads.find({}).sort("status_changed_at", -1).to_list(1000)
    leads = [serialize(d) for d in leads]
    cols = []
    for key, label in PIPELINE_STATI:
        items = [l for l in leads if l.get("status") == key]
        for it in items:
            it["giorni_in_stato"] = _giorni_da(it.get("status_changed_at", it.get("created_at")))
        valore = sum((l.get("range_alto", 0) + l.get("range_basso", 0)) / 2 for l in items)
        cols.append({"key": key, "label": label, "count": len(items),
                     "valore": round(valore), "leads": items})
    return {"columns": cols}


@api.get("/sopralluoghi")
async def sopralluoghi(user: dict = Depends(current_user)):
    leads = await db.leads.find({"status": {"$in": ["sopralluogo_fissato", "sopralluogo_fatto"]}}).to_list(500)
    out = []
    base = datetime.now(timezone.utc)
    for i, d in enumerate(leads):
        d = serialize(d)
        data = (base + timedelta(days=(i + 1), hours=9 + (i % 3) * 2)).replace(minute=0, second=0, microsecond=0)
        out.append({
            "id": d["id"], "cliente": d["nome"], "telefono": d.get("telefono"),
            "citta": d.get("citta"), "indirizzo": f"{d.get('citta')}",
            "tipo_immobile": d.get("tipo_immobile"), "mq": d.get("mq"),
            "tecnico": d.get("owner") or "Giovanni Brancale",
            "data": data.isoformat(),
            "completato": d.get("status") == "sopralluogo_fatto",
            "estimate": d.get("estimate"),
        })
    return out


@api.get("/preventivi")
async def preventivi(user: dict = Depends(current_user)):
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
    return out


@api.get("/cantieri")
async def cantieri(user: dict = Depends(current_user)):
    docs = await db.cantieri.find({}).to_list(100)
    return [serialize(d) for d in docs]


@api.get("/reports")
async def reports(user: dict = Depends(require_admin)):
    leads = await db.leads.find({}).to_list(1000)
    leads = [serialize(d) for d in leads]
    total = len(leads)
    qualificati = len([l for l in leads if l.get("status") not in ("nuovo",)])
    sopr = len([l for l in leads if l.get("status") in ("sopralluogo_fissato", "sopralluogo_fatto")])
    prev = len([l for l in leads if l.get("status") in ("preventivo_inviato", "follow_up", "in_trattativa", "chiuso_vinto", "chiuso_perso")])
    vinti = [l for l in leads if l.get("status") == "chiuso_vinto"]
    persi = [l for l in leads if l.get("status") == "chiuso_perso"]
    conv = round((len(vinti) / total * 100) if total else 0, 1)
    aperti = [l for l in leads if l.get("status") not in ("chiuso_vinto", "chiuso_perso")]
    valore_pipeline = round(sum((l.get("range_alto", 0) + l.get("range_basso", 0)) / 2 for l in aperti))
    valore_chiuso = round(sum((l.get("range_alto", 0) + l.get("range_basso", 0)) / 2 for l in vinti))

    # distribuzione pacchetti
    pac = {}
    for l in leads:
        pac[l.get("livello", "premium")] = pac.get(l.get("livello", "premium"), 0) + 1
    distribuzione = [{"name": k.capitalize(), "value": v} for k, v in pac.items()]

    # provenienza geografica
    geo = {}
    for l in leads:
        c = l.get("citta") or "Altro"
        geo[c] = geo.get(c, 0) + 1
    geografia = sorted([{"citta": k, "lead": v} for k, v in geo.items()], key=lambda x: x["lead"], reverse=True)

    # funnel
    funnel = [
        {"step": "Lead", "value": total},
        {"step": "Qualificati", "value": qualificati},
        {"step": "Sopralluoghi", "value": sopr},
        {"step": "Preventivi", "value": prev},
        {"step": "Vinti", "value": len(vinti)},
    ]

    # lead nel tempo (ultimi 6 mesi semplificato per giorno arrivo)
    serie = {}
    for l in leads:
        day = (l.get("created_at") or "")[:10]
        serie[day] = serie.get(day, 0) + 1
    timeline = sorted([{"data": k, "lead": v} for k, v in serie.items() if k], key=lambda x: x["data"])

    return {
        "kpi": {
            "lead_ricevuti": total, "lead_qualificati": qualificati,
            "sopralluoghi": sopr, "preventivi": prev,
            "chiusi_vinti": len(vinti), "chiusi_persi": len(persi),
            "conversione": conv, "valore_pipeline": valore_pipeline,
            "valore_chiuso": valore_chiuso,
        },
        "distribuzione": distribuzione, "geografia": geografia,
        "funnel": funnel, "timeline": timeline,
        "persi": [{"nome": l["nome"], "citta": l.get("citta"), "livello": l.get("livello"),
                   "range": l.get("range_alto")} for l in persi],
    }


@api.post("/reports/insights")
async def reports_insights(user: dict = Depends(require_admin)):
    rep = await reports(user)
    try:
        text = await ai_service.generate_insights(rep["kpi"])
    except Exception as e:
        logger.exception("insights failed")
        raise HTTPException(status_code=502, detail=f"Servizio AI non disponibile: {e}")
    return {"insights": text}


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
@app.on_event("startup")
async def startup():
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
    await db.ai_architect_jobs.create_index("created_at")
    await db.ai_architect_jobs.create_index("lead_id")
    await db.ai_architect_jobs.create_index("file_hash")
    await db.ai_architect_outputs.create_index([("job_id", 1), ("created_at", 1)])
    await db.ai_architect_errors.create_index([("job_id", 1), ("created_at", -1)])
    await db.ai_architect_quality_logs.create_index([("job_id", 1), ("gate_id", 1), ("timestamp", -1)])
    await db.ai_architect_cache.create_index(
        [("cache_type", 1), ("file_hash", 1), ("schema_version", 1), ("provider", 1), ("model", 1)],
        unique=True,
    )
    await authlib.seed_users(db)
    if await db.leads.count_documents({}) == 0:
        await db.leads.insert_many(seed_data.build_demo_leads())
        logger.info("Seeded demo leads")
    if await db.cantieri.count_documents({}) == 0:
        await db.cantieri.insert_many(seed_data.build_demo_cantieri())
        logger.info("Seeded demo cantieri")


@app.on_event("shutdown")
async def shutdown():
    client.close()


app.include_router(api)
app.mount(
    "/api/ai-architect/files",
    StaticFiles(directory=str(ai_architect_service.STORAGE_DIR)),
    name="ai_architect_files",
)
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
    allow_origin_regex=(
        r"https?://("
        r"localhost|127\.0\.0\.1|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|"
        r"192\.168\.\d{1,3}\.\d{1,3}"
        r"):3000"
    ),
    allow_methods=["*"],
    allow_headers=["*"],
)
