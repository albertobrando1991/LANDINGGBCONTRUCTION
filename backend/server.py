from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, Depends, Query
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId

import auth as authlib
from predictive_engine import calcola_preventivo, lead_score
from predictive_data import COEFFICIENTI, voci_as_dicts
import seed_data
import ai_service

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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


class LeadCreate(BaseModel):
    nome: str
    email: EmailStr
    telefono: str
    citta: str
    privacy: bool = True
    newsletter: bool = False
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


@api.post("/estimate")
async def estimate(body: EstimateBody):
    return calcola_preventivo(body.config.model_dump())


@api.get("/projects")
async def projects():
    return seed_data.DEMO_PROJECTS


@api.post("/leads")
async def create_lead(body: LeadCreate):
    cfg = body.config.model_dump()
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
    doc = {
        "nome": body.nome, "email": body.email.lower(), "telefono": body.telefono,
        "citta": body.citta, "newsletter": body.newsletter,
        "tipo_immobile": cfg["tipo_immobile"], "mq": cfg["mq"], "livello": cfg["livello"],
        "bagni": cfg["bagni"], "camere": cfg["camere"], "cucina": cfg["cucina"],
        "ambienti": cfg["ambienti"], "stile": cfg["stile"], "tempistiche": cfg["tempistiche"],
        "origine": "landing", "status": "nuovo", "owner": None, "score": score,
        "tags": tags, "has_files": cfg.get("has_files", False), "note_cliente": "",
        "range_basso": pkg["range_basso"], "range_alto": pkg["range_alto"],
        "estimate": est, "prossima_azione": "",
        "timeline": [{"id": "ev-" + uuid.uuid4().hex[:8], "tipo": "lead_ricevuto",
                      "testo": f"Lead ricevuto dalla landing - {cfg['tipo_immobile']} {cfg['mq']}mq a {body.citta}",
                      "ts": now_iso()}],
        "created_at": now_iso(), "last_contact": now_iso(), "status_changed_at": now_iso(),
    }
    res = await db.leads.insert_one(doc)
    return {"id": str(res.inserted_id), "estimate": est, "score": score}


@api.post("/callback")
async def callback(body: CallbackBody):
    doc = {
        "nome": body.nome, "email": "", "telefono": body.telefono, "citta": "",
        "tipo_immobile": "-", "mq": 0, "livello": "premium", "bagni": 0, "camere": 0,
        "ambienti": [], "stile": "-", "tempistiche": "Sto valutando", "origine": "callback",
        "status": "nuovo", "owner": None, "score": 50, "tags": ["Richiamo"],
        "has_files": False, "note_cliente": body.messaggio or "", "range_basso": 0, "range_alto": 0,
        "estimate": None, "prossima_azione": "Richiamare il cliente entro 2 ore",
        "timeline": [{"id": "ev-" + uuid.uuid4().hex[:8], "tipo": "lead_ricevuto",
                      "testo": "Richiesta di richiamo dalla landing", "ts": now_iso()}],
        "created_at": now_iso(), "last_contact": now_iso(), "status_changed_at": now_iso(),
    }
    res = await db.leads.insert_one(doc)
    return {"id": str(res.inserted_id), "ok": True}


# ----------------------- Staff: leads -----------------------
@api.get("/leads")
async def list_leads(request: Request, status: Optional[str] = None,
                     q: Optional[str] = None, owner: Optional[str] = None,
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
    await db.leads.update_one(
        {"_id": ObjectId(lead_id)},
        {"$push": {"timeline": {"$each": [ev], "$position": 0}},
         "$set": {"last_contact": now_iso()}})
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
            if (now - dt) > timedelta(hours=18):
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
            "tecnico": d.get("owner") or "Salvatore Bianco",
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
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
