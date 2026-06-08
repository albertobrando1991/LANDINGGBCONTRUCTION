"""GB Construction - ledger crediti AI.

Il credito e un micro-credito commerciale: 1.000 crediti = 1 EUR + IVA.
Gli addebiti sono idempotenti quando viene fornita una idempotency_key.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError


ACCOUNT_ID = os.getenv("AI_CREDITS_ACCOUNT_ID", "gb_construction")
CREDITS_PER_EUR = int(os.getenv("AI_CREDITS_PER_EUR", "1000"))
MONTHLY_INCLUDED_CREDITS = int(os.getenv("AI_MONTHLY_INCLUDED_CREDITS", "30000"))
PACK_EXPIRY_MONTHS = int(os.getenv("AI_CREDIT_PACK_EXPIRY_MONTHS", "12"))
LOW_BALANCE_THRESHOLD_CREDITS = int(os.getenv("AI_CREDITS_LOW_THRESHOLD", "10000"))
BASE_PACK_ENABLED = os.getenv("AI_BASE_CREDIT_PACK_ENABLED", "true").strip().lower() not in {"0", "false", "no"}
BASE_PACK_CREDITS = int(os.getenv("AI_BASE_CREDIT_PACK_CREDITS", "20000"))
BASE_PACK_LABEL = os.getenv("AI_BASE_CREDIT_PACK_LABEL", "Pacchetto base attivo")

PUBLIC_RENDER_ROOM_LIMIT = max(1, int(os.getenv("AI_RENDER_MAX_ROOMS_PUBLIC", "2")))
STAFF_RENDER_ROOM_LIMIT = max(1, int(os.getenv("AI_RENDER_MAX_ROOMS_STAFF", "4")))


def _normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


UNLIMITED_GENERATION_EMAILS = {
    _normalize_email(value)
    for value in os.getenv("AI_CREDITS_UNLIMITED_EMAILS", "info@alantis.it").split(",")
    if value.strip()
}


RATE_CARD: Dict[str, Dict[str, Any]] = {
    "lead_suggestion": {
        "label": "Suggerimento prossima azione lead",
        "credits": 5,
        "estimated_provider_cost_eur": 0.003,
    },
    "report_insights": {
        "label": "Insight AI report/dashboard",
        "credits": 10,
        "estimated_provider_cost_eur": 0.007,
    },
    "ai_architect_preliminary": {
        "label": "AI Architect preliminare: analisi + concept 2D",
        "credits": 900,
        "estimated_provider_cost_eur": 0.600,
    },
    "ai_architect_render_public": {
        "label": "Render finali utente: top-down + 2 ambienti",
        "credits": 1450,
        "estimated_provider_cost_eur": 0.955,
    },
    "ai_architect_render_staff": {
        "label": "Render finali staff: top-down + 4 ambienti",
        "credits": 2500,
        "estimated_provider_cost_eur": 1.650,
    },
    "ai_architect_regen_2d": {
        "label": "Rigenerazione 2D",
        "credits": 450,
        "estimated_provider_cost_eur": 0.300,
    },
    "ai_architect_regen_topdown": {
        "label": "Rigenerazione top-down",
        "credits": 450,
        "estimated_provider_cost_eur": 0.300,
    },
    "ai_architect_regen_room_render": {
        "label": "Rigenerazione singolo render ambiente",
        "credits": 450,
        "estimated_provider_cost_eur": 0.300,
    },
    "ai_architect_advice_text": {
        "label": "Testo advice/report",
        "credits": 80,
        "estimated_provider_cost_eur": 0.055,
    },
    "ai_architect_regeneration": {
        "label": "Rigenerazione output AI Architect",
        "credits": 0,
        "estimated_provider_cost_eur": 0.0,
    },
}

PACK_PRESETS = [
    {"key": "starter_20", "label": "Starter 20", "amount_eur": 20, "credits": 20000},
    {"key": "plus_25", "label": "Plus 25", "amount_eur": 25, "credits": 25000},
    {"key": "growth_50", "label": "Growth 50", "amount_eur": 50, "credits": 50000},
    {"key": "pro_100", "label": "Pro 100", "amount_eur": 100, "credits": 100000},
    {"key": "scale_250", "label": "Scale 250", "amount_eur": 250, "credits": 250000},
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _month_period(dt: Optional[datetime] = None) -> str:
    current = dt or datetime.now(timezone.utc)
    return f"{current.year:04d}-{current.month:02d}"


def _add_months(dt: datetime, months: int) -> datetime:
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    day = min(dt.day, 28)
    return dt.replace(year=year, month=month, day=day)


def _to_eur(credits: int) -> float:
    return round(float(credits) / CREDITS_PER_EUR, 3)


def email_has_unlimited_generations(email: Any) -> bool:
    normalized = _normalize_email(email)
    return bool(normalized) and normalized in UNLIMITED_GENERATION_EMAILS


def _object_id(value: Any) -> Optional[ObjectId]:
    try:
        if value and ObjectId.is_valid(str(value)):
            return ObjectId(str(value))
    except Exception:
        return None
    return None


async def has_unlimited_generation_access(
    db,
    *,
    user: Optional[Dict[str, Any]] = None,
    lead_id: Optional[str] = None,
    job_id: Optional[str] = None,
    job: Optional[Dict[str, Any]] = None,
) -> bool:
    if email_has_unlimited_generations((user or {}).get("email")):
        return True

    job_doc = job
    if job_doc:
        if email_has_unlimited_generations(job_doc.get("created_by_email")):
            return True
        lead_id = lead_id or job_doc.get("lead_id")

    if lead_id:
        oid = _object_id(lead_id)
        if oid:
            lead = await db.leads.find_one({"_id": oid})
            if lead and email_has_unlimited_generations(lead.get("email_norm") or lead.get("email")):
                return True

    if job_id and not job_doc:
        oid = _object_id(job_id)
        if oid:
            job_doc = await db.ai_architect_jobs.find_one({"_id": oid})
            if job_doc:
                if email_has_unlimited_generations(job_doc.get("created_by_email")):
                    return True
                linked_lead_id = job_doc.get("lead_id")
                if linked_lead_id and linked_lead_id != lead_id:
                    return await has_unlimited_generation_access(db, lead_id=linked_lead_id)

    return False


def _rate_card_list() -> List[Dict[str, Any]]:
    return [
        {
            "key": key,
            "label": value["label"],
            "credits": value["credits"],
            "value_eur": _to_eur(value["credits"]),
            "estimated_provider_cost_eur": value["estimated_provider_cost_eur"],
        }
        for key, value in RATE_CARD.items()
    ]


def is_staff_context(job: Dict[str, Any]) -> bool:
    context = str(job.get("usage_context") or job.get("created_via") or "").strip().lower()
    role = str(job.get("created_by_role") or "").strip().lower()
    return context in {"staff", "staff_dashboard", "internal", "admin", "operations"} or role in {
        "staff",
        "operations",
        "admin",
    }


def render_room_limit(job: Dict[str, Any]) -> int:
    explicit = job.get("render_room_limit")
    if isinstance(explicit, int) and explicit > 0:
        return explicit
    if isinstance(explicit, str) and explicit.isdigit():
        return max(1, int(explicit))
    return STAFF_RENDER_ROOM_LIMIT if is_staff_context(job) else PUBLIC_RENDER_ROOM_LIMIT


def render_stage_action_key(job: Dict[str, Any]) -> str:
    return "ai_architect_render_staff" if is_staff_context(job) else "ai_architect_render_public"


def render_stage_credits(job: Dict[str, Any]) -> int:
    return int(RATE_CARD[render_stage_action_key(job)]["credits"])


def regeneration_credits(job: Dict[str, Any], output_types: Optional[List[str]]) -> int:
    requested = set(output_types or ["topdown_3d_plan", "room_render", "advice", "pdf_report"])
    if requested & {"concept_2d", "clean_2d_plan", "redistributed_2d_plan"}:
        return int(RATE_CARD["ai_architect_regen_2d"]["credits"])

    credits = 0
    if "topdown_3d_plan" in requested:
        credits += int(RATE_CARD["ai_architect_regen_topdown"]["credits"])
    if "room_render" in requested:
        credits += render_room_limit(job) * int(RATE_CARD["ai_architect_regen_room_render"]["credits"])
    if requested & {"advice", "pdf_report"}:
        credits += int(RATE_CARD["ai_architect_advice_text"]["credits"])
    return credits


async def ensure_monthly_bucket(db, account_id: str = ACCOUNT_ID) -> Dict[str, Any]:
    period = _month_period()
    key = f"{account_id}:monthly:{period}"
    existing = await db.ai_credit_buckets.find_one({"key": key})
    if existing:
        return existing
    now = datetime.now(timezone.utc)
    doc = {
        "key": key,
        "account_id": account_id,
        "bucket_type": "monthly",
        "period": period,
        "label": f"Crediti mensili inclusi {period}",
        "credits_total": MONTHLY_INCLUDED_CREDITS,
        "remaining_credits": MONTHLY_INCLUDED_CREDITS,
        "used_credits": 0,
        "amount_eur": _to_eur(MONTHLY_INCLUDED_CREDITS),
        "created_at": now.isoformat(),
        "expires_at": _add_months(now.replace(day=1), 1).isoformat(),
        "source": "monthly_included",
    }
    await db.ai_credit_buckets.update_one({"key": key}, {"$setOnInsert": doc}, upsert=True)
    return await db.ai_credit_buckets.find_one({"key": key})


async def ensure_base_credit_pack(db, account_id: str = ACCOUNT_ID) -> Optional[Dict[str, Any]]:
    if not BASE_PACK_ENABLED or BASE_PACK_CREDITS <= 0:
        return None
    now = datetime.now(timezone.utc)
    key = f"{account_id}:pack:base-active"
    doc = {
        "key": key,
        "account_id": account_id,
        "bucket_type": "pack",
        "period": None,
        "label": BASE_PACK_LABEL,
        "credits_total": BASE_PACK_CREDITS,
        "remaining_credits": BASE_PACK_CREDITS,
        "used_credits": 0,
        "amount_eur": _to_eur(BASE_PACK_CREDITS),
        "created_at": now.isoformat(),
        "expires_at": _add_months(now, PACK_EXPIRY_MONTHS).isoformat(),
        "source": "base_active_pack",
        "notes": "Pacchetto crediti base attivato automaticamente.",
    }
    result = await db.ai_credit_buckets.update_one({"key": key}, {"$setOnInsert": doc}, upsert=True)
    bucket = await db.ai_credit_buckets.find_one({"key": key})
    if result.upserted_id:
        await db.ai_credit_ledger.update_one(
            {"idempotency_key": f"grant:{key}"},
            {
                "$setOnInsert": {
                    "account_id": account_id,
                    "transaction_type": "credit",
                    "action_key": "base_credit_pack",
                    "action_label": BASE_PACK_LABEL,
                    "idempotency_key": f"grant:{key}",
                    "credits": BASE_PACK_CREDITS,
                    "value_eur": _to_eur(BASE_PACK_CREDITS),
                    "bucket_id": str(result.upserted_id),
                    "metadata": {"source": "base_active_pack"},
                    "created_at": now.isoformat(),
                }
            },
            upsert=True,
        )
    return bucket


async def _active_buckets(db, account_id: str = ACCOUNT_ID) -> List[Dict[str, Any]]:
    await ensure_monthly_bucket(db, account_id)
    await ensure_base_credit_pack(db, account_id)
    now = now_iso()
    monthly = await db.ai_credit_buckets.find(
        {
            "account_id": account_id,
            "bucket_type": "monthly",
            "remaining_credits": {"$gt": 0},
            "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
        }
    ).sort([("expires_at", 1), ("created_at", 1)]).to_list(20)
    packs = await db.ai_credit_buckets.find(
        {
            "account_id": account_id,
            "bucket_type": "pack",
            "remaining_credits": {"$gt": 0},
            "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
        }
    ).sort([("expires_at", 1), ("created_at", 1)]).to_list(200)
    return monthly + packs


async def available_credits(db, account_id: str = ACCOUNT_ID) -> int:
    buckets = await _active_buckets(db, account_id)
    return sum(int(bucket.get("remaining_credits") or 0) for bucket in buckets)


async def require_available(db, credits: int, *, account_id: str = ACCOUNT_ID) -> None:
    if credits <= 0:
        return
    available = await available_credits(db, account_id)
    if available < credits:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Crediti AI insufficienti: disponibili {available}, richiesti {credits}. "
                "Acquista un pacchetto crediti o attendi il reset mensile."
            ),
        )


async def require_available_for_generation(
    db,
    credits: int,
    *,
    account_id: str = ACCOUNT_ID,
    user: Optional[Dict[str, Any]] = None,
    lead_id: Optional[str] = None,
    job_id: Optional[str] = None,
    job: Optional[Dict[str, Any]] = None,
    public_message: bool = False,
) -> None:
    if await has_unlimited_generation_access(db, user=user, lead_id=lead_id, job_id=job_id, job=job):
        return
    try:
        await require_available(db, credits, account_id=account_id)
    except HTTPException as exc:
        if public_message:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Il servizio AI non e' momentaneamente disponibile. "
                    "Contatta lo staff GB Construction per informazioni."
                ),
            ) from exc
        raise


async def charge_credits(
    db,
    *,
    action_key: str,
    idempotency_key: str,
    credits: Optional[int] = None,
    account_id: str = ACCOUNT_ID,
    user: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
    job: Optional[Dict[str, Any]] = None,
    lead_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    existing = await db.ai_credit_ledger.find_one({"idempotency_key": idempotency_key})
    if existing:
        return existing

    if credits is None:
        if action_key not in RATE_CARD:
            raise ValueError(f"Azione crediti AI sconosciuta: {action_key}")
        credits = int(RATE_CARD[action_key]["credits"])
    credits = int(credits)
    action = RATE_CARD.get(action_key, {})
    now = now_iso()

    if await has_unlimited_generation_access(db, user=user, lead_id=lead_id, job_id=job_id, job=job):
        doc = {
            "account_id": account_id,
            "transaction_type": "unlimited_bypass",
            "action_key": action_key,
            "action_label": action.get("label") or action_key,
            "idempotency_key": idempotency_key,
            "credits": 0,
            "waived_credits": credits,
            "value_eur": 0,
            "estimated_provider_cost_eur": action.get("estimated_provider_cost_eur"),
            "job_id": job_id,
            "lead_id": lead_id,
            "user_id": (user or {}).get("id"),
            "user_email": (user or {}).get("email") or (job or {}).get("created_by_email"),
            "metadata": {**(metadata or {}), "unlimited_generation_access": True},
            "bucket_consumptions": [],
            "created_at": now,
        }
        await db.ai_credit_ledger.update_one(
            {"idempotency_key": idempotency_key},
            {"$setOnInsert": doc},
            upsert=True,
        )
        await db.ai_usage_events.insert_one(
            {
                **doc,
                "event_type": "ai_credit_unlimited_bypass",
                "credits_debited": 0,
            }
        )
        return await db.ai_credit_ledger.find_one({"idempotency_key": idempotency_key}) or doc

    await require_available(db, credits, account_id=account_id)

    doc = {
        "account_id": account_id,
        "transaction_type": "debit",
        "action_key": action_key,
        "action_label": action.get("label") or action_key,
        "idempotency_key": idempotency_key,
        "credits": -credits,
        "value_eur": _to_eur(credits),
        "estimated_provider_cost_eur": action.get("estimated_provider_cost_eur"),
        "job_id": job_id,
        "lead_id": lead_id,
        "user_id": (user or {}).get("id"),
        "user_email": (user or {}).get("email"),
        "metadata": metadata or {},
        "bucket_consumptions": [],
        "created_at": now,
    }

    # Claim idempotente PRIMA di toccare i bucket: l'indice unico su
    # idempotency_key fa da lock. Due richieste concorrenti con la stessa key
    # non possono entrambe decrementare i saldi.
    try:
        await db.ai_credit_ledger.insert_one(doc)
    except DuplicateKeyError:
        existing = await db.ai_credit_ledger.find_one({"idempotency_key": idempotency_key})
        if existing:
            return existing
        raise

    buckets = await _active_buckets(db, account_id)
    remaining_to_consume = credits
    consumptions: List[Dict[str, Any]] = []
    for bucket in buckets:
        if remaining_to_consume <= 0:
            break
        bucket_remaining = int(bucket.get("remaining_credits") or 0)
        take = min(bucket_remaining, remaining_to_consume)
        if take <= 0:
            continue
        result = await db.ai_credit_buckets.update_one(
            {"_id": bucket["_id"], "remaining_credits": {"$gte": take}},
            {
                "$inc": {"remaining_credits": -take, "used_credits": take},
                "$set": {"updated_at": now_iso()},
            },
        )
        if result.modified_count != 1:
            continue
        remaining_to_consume -= take
        consumptions.append(
            {
                "bucket_id": str(bucket["_id"]),
                "bucket_key": bucket.get("key"),
                "bucket_type": bucket.get("bucket_type"),
                "credits": take,
            }
        )

    if remaining_to_consume > 0:
        # Race sul saldo: rimborsa i bucket gia toccati e rilascia il claim
        # cosi un retry puo ripartire pulito.
        for consumption in consumptions:
            oid = _object_id(consumption["bucket_id"])
            if oid:
                await db.ai_credit_buckets.update_one(
                    {"_id": oid},
                    {
                        "$inc": {
                            "remaining_credits": consumption["credits"],
                            "used_credits": -consumption["credits"],
                        }
                    },
                )
        await db.ai_credit_ledger.delete_one({"idempotency_key": idempotency_key})
        raise HTTPException(status_code=409, detail="Saldo crediti modificato durante l'addebito. Riprova.")

    doc["bucket_consumptions"] = consumptions
    await db.ai_credit_ledger.update_one(
        {"idempotency_key": idempotency_key},
        {"$set": {"bucket_consumptions": consumptions}},
    )
    await db.ai_usage_events.insert_one(
        {
            **doc,
            "event_type": "ai_credit_debit",
            "credits_debited": credits,
        }
    )
    return doc


async def grant_pack(
    db,
    *,
    credits: int,
    amount_eur: Optional[float] = None,
    label: Optional[str] = None,
    account_id: str = ACCOUNT_ID,
    user: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    if credits <= 0:
        raise HTTPException(status_code=400, detail="Crediti pacchetto non validi")
    min_pack = min(preset["credits"] for preset in PACK_PRESETS)
    if credits < min_pack:
        raise HTTPException(status_code=400, detail="Il pacchetto minimo acquistabile e' da 20 EUR / 20.000 crediti")
    now = datetime.now(timezone.utc)
    expires_at = _add_months(now, PACK_EXPIRY_MONTHS).isoformat()
    key = f"{account_id}:pack:{now.strftime('%Y%m%d%H%M%S')}:{credits}"
    doc = {
        "key": key,
        "account_id": account_id,
        "bucket_type": "pack",
        "period": None,
        "label": label or f"Pacchetto {credits} crediti",
        "credits_total": int(credits),
        "remaining_credits": int(credits),
        "used_credits": 0,
        "amount_eur": amount_eur if amount_eur is not None else _to_eur(credits),
        "created_at": now.isoformat(),
        "expires_at": expires_at,
        "source": "manual_pack",
        "notes": notes,
        "created_by": (user or {}).get("email") or (user or {}).get("name"),
    }
    result = await db.ai_credit_buckets.insert_one(doc)
    await db.ai_credit_ledger.insert_one(
        {
            "account_id": account_id,
            "transaction_type": "credit",
            "action_key": "credit_pack_grant",
            "action_label": doc["label"],
            "idempotency_key": f"grant:{str(result.inserted_id)}",
            "credits": int(credits),
            "value_eur": doc["amount_eur"],
            "bucket_id": str(result.inserted_id),
            "user_id": (user or {}).get("id"),
            "user_email": (user or {}).get("email"),
            "metadata": {"notes": notes},
            "created_at": now.isoformat(),
        }
    )
    doc["id"] = str(result.inserted_id)
    return doc


def build_alerts(total_remaining: int) -> List[Dict[str, Any]]:
    public_full = int(RATE_CARD["ai_architect_preliminary"]["credits"]) + int(
        RATE_CARD["ai_architect_render_public"]["credits"]
    )
    preliminary = int(RATE_CARD["ai_architect_preliminary"]["credits"])
    alerts: List[Dict[str, Any]] = []
    if total_remaining < preliminary:
        alerts.append(
            {
                "type": "insufficient",
                "severity": "danger",
                "title": "Crediti AI insufficienti",
                "message": (
                    "Il saldo non basta per avviare nuove analisi AI Architect. "
                    "Le generazioni pubbliche potrebbero fermarsi subito."
                ),
                "required_credits": preliminary,
                "available_credits": total_remaining,
            }
        )
    elif total_remaining < public_full:
        alerts.append(
            {
                "type": "insufficient_for_full_public_job",
                "severity": "danger",
                "title": "Crediti insufficienti per un AI Architect completo",
                "message": (
                    "Il saldo consente azioni leggere, ma non basta per completare un flusso utente "
                    "con analisi, top-down e 2 render."
                ),
                "required_credits": public_full,
                "available_credits": total_remaining,
            }
        )
    elif total_remaining <= LOW_BALANCE_THRESHOLD_CREDITS:
        alerts.append(
            {
                "type": "low_balance",
                "severity": "warning",
                "title": "Crediti AI in esaurimento",
                "message": (
                    "Il saldo sta per terminare. Acquista un pacchetto crediti per evitare blocchi "
                    "durante le richieste degli utenti."
                ),
                "threshold_credits": LOW_BALANCE_THRESHOLD_CREDITS,
                "available_credits": total_remaining,
            }
        )
    return alerts


async def summary(
    db,
    account_id: str = ACCOUNT_ID,
    *,
    user: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    await ensure_monthly_bucket(db, account_id)
    await ensure_base_credit_pack(db, account_id)
    period = _month_period()
    current_iso = now_iso()
    monthly = await db.ai_credit_buckets.find_one(
        {"account_id": account_id, "bucket_type": "monthly", "period": period}
    )
    packs = await db.ai_credit_buckets.find(
        {"account_id": account_id, "bucket_type": "pack"}
    ).sort("created_at", -1).to_list(100)
    recent_ledger = await db.ai_credit_ledger.find({"account_id": account_id}).sort("created_at", -1).to_list(30)
    active_packs = [
        pack
        for pack in packs
        if int(pack.get("remaining_credits") or 0) > 0
        and (not pack.get("expires_at") or pack.get("expires_at") > current_iso)
    ]
    total_remaining = int(monthly.get("remaining_credits") or 0) + sum(
        int(pack.get("remaining_credits") or 0)
        for pack in active_packs
    )
    pack_remaining = sum(
        int(pack.get("remaining_credits") or 0)
        for pack in active_packs
    )
    unlimited_access = await has_unlimited_generation_access(db, user=user)
    alerts = [] if unlimited_access else build_alerts(total_remaining)
    return {
        "account_id": account_id,
        "period": period,
        "credits_per_eur": CREDITS_PER_EUR,
        "credit_value_eur": 1 / CREDITS_PER_EUR,
        "total_remaining_credits": total_remaining,
        "total_remaining_eur": _to_eur(total_remaining),
        "monthly": {
            "credits_total": int(monthly.get("credits_total") or 0),
            "remaining_credits": int(monthly.get("remaining_credits") or 0),
            "used_credits": int(monthly.get("used_credits") or 0),
            "expires_at": monthly.get("expires_at"),
        },
        "packs": [
            {
                "id": str(pack.get("_id")),
                "label": pack.get("label"),
                "credits_total": int(pack.get("credits_total") or 0),
                "remaining_credits": int(pack.get("remaining_credits") or 0),
                "used_credits": int(pack.get("used_credits") or 0),
                "amount_eur": pack.get("amount_eur"),
                "expires_at": pack.get("expires_at"),
            }
            for pack in packs
        ],
        "pack_remaining_credits": pack_remaining,
        "pack_remaining_eur": _to_eur(pack_remaining),
        "low_balance_threshold_credits": LOW_BALANCE_THRESHOLD_CREDITS,
        "unlimited_generation_access": unlimited_access,
        "unlimited_generation_emails": sorted(UNLIMITED_GENERATION_EMAILS),
        "alerts": alerts,
        "pack_presets": PACK_PRESETS,
        "rate_card": _rate_card_list(),
        "recent_ledger": [
            {
                "id": str(item.get("_id")),
                "transaction_type": item.get("transaction_type"),
                "action_key": item.get("action_key"),
                "action_label": item.get("action_label"),
                "credits": int(item.get("credits") or 0),
                "value_eur": item.get("value_eur"),
                "job_id": item.get("job_id"),
                "lead_id": item.get("lead_id"),
                "created_at": item.get("created_at"),
            }
            for item in recent_ledger
        ],
    }
