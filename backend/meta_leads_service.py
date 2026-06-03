import asyncio
import hashlib
import hmac
import logging
import os
import re
import unicodedata
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
from pymongo import ReturnDocument

from predictive_engine import calcola_preventivo, lead_score


logger = logging.getLogger("gb.meta")

META_SOURCE = "meta_ads"
GRAPH_FIELDS = (
    "created_time,field_data,form_id,ad_id,ad_name,"
    "adset_id,adset_name,campaign_id,campaign_name,platform"
)


class MetaLeadError(RuntimeError):
    pass


class MetaLeadConfigError(MetaLeadError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_phone(value: Any) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    return digits


def _strip_accents(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(c)
    )


def normalize_field_name(value: Any) -> str:
    text = _strip_accents(str(value or "").strip().lower())
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(clean_text(v) for v in value if clean_text(v))
    return str(value).strip()


def parse_int(value: Any, default: int) -> int:
    text = clean_text(value)
    match = re.search(r"\d+", text.replace(".", ""))
    if not match:
        return default
    try:
        return int(match.group(0))
    except ValueError:
        return default


def parse_bool(value: Any, default: bool) -> bool:
    text = clean_text(value).lower()
    if not text:
        return default
    if text in {"si", "sì", "yes", "true", "1", "con cucina", "presente"}:
        return True
    if text in {"no", "false", "0", "senza cucina", "assente"}:
        return False
    return default


def verify_meta_signature(raw_body: bytes, signature_header: Optional[str], app_secret: Optional[str]) -> bool:
    if not app_secret:
        raise MetaLeadConfigError("META_APP_SECRET non configurato")
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def extract_leadgen_events(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for entry in payload.get("entry", []) or []:
        entry_id = entry.get("id")
        for change in entry.get("changes", []) or []:
            if change.get("field") != "leadgen":
                continue
            value = change.get("value") or {}
            leadgen_id = clean_text(value.get("leadgen_id"))
            if not leadgen_id:
                continue
            events.append({
                "leadgen_id": leadgen_id,
                "form_id": clean_text(value.get("form_id")),
                "page_id": clean_text(value.get("page_id") or entry_id),
                "ad_id": clean_text(value.get("ad_id")),
                "created_time": value.get("created_time"),
                "raw_value": value,
            })
    return events


def fetch_meta_lead(
    leadgen_id: str,
    page_token: Optional[str],
    graph_version: str = "v23.0",
    timeout: int = 12,
    get: Callable[..., Any] = requests.get,
) -> Dict[str, Any]:
    if not page_token:
        raise MetaLeadConfigError("META_PAGE_ACCESS_TOKEN non configurato")
    version = (graph_version or "v23.0").strip().lstrip("/")
    url = f"https://graph.facebook.com/{version}/{leadgen_id}"
    response = get(url, params={"access_token": page_token, "fields": GRAPH_FIELDS}, timeout=timeout)
    if response.status_code >= 400:
        raise MetaLeadError(f"Graph API lead fetch failed: HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, dict):
        raise MetaLeadError("Graph API ha restituito una risposta non valida")
    if data.get("error"):
        raise MetaLeadError("Graph API lead fetch failed")
    return data


def flatten_field_data(field_data: Any) -> Tuple[Dict[str, str], Dict[str, Any]]:
    fields: Dict[str, str] = {}
    raw: Dict[str, Any] = {}
    for item in field_data or []:
        name = clean_text(item.get("name"))
        if not name:
            continue
        values = item.get("values") or []
        value = clean_text(values)
        fields[normalize_field_name(name)] = value
        raw[name] = values
    return fields, raw


def first_value(fields: Dict[str, str], *keys: str) -> str:
    for key in keys:
        value = fields.get(normalize_field_name(key))
        if value:
            return value
    return ""


def normalize_property_type(value: str) -> str:
    text = normalize_field_name(value)
    if "villa" in text:
        return "villa"
    if "negozio" in text or "commerciale" in text or "locale" in text:
        return "locale_commerciale"
    if "ufficio" in text:
        return "ufficio"
    return "appartamento"


def normalize_level(value: str) -> str:
    text = normalize_field_name(value)
    if "luxury" in text or "lusso" in text:
        return "luxury"
    if "essenziale" in text or "base" in text or "econom" in text:
        return "essenziale"
    return "premium"


def build_config_from_meta_fields(fields: Dict[str, str]) -> Dict[str, Any]:
    tipo = first_value(fields, "tipo_immobile", "tipo immobile", "immobile", "casa")
    livello = first_value(fields, "livello", "pacchetto", "budget", "fascia_budget")
    stile = first_value(fields, "stile", "stile_desiderato", "stile_ristrutturazione") or "Da definire"
    tempistiche = (
        first_value(fields, "tempistiche", "quando", "inizio_lavori", "quando_vuoi_iniziare")
        or "Da qualificare"
    )
    return {
        "tipo_immobile": normalize_property_type(tipo),
        "mq": max(20, parse_int(first_value(fields, "mq", "metri_quadri", "metratura", "superficie"), 80)),
        "livello": normalize_level(livello),
        "bagni": max(0, parse_int(first_value(fields, "bagni", "numero_bagni"), 1)),
        "camere": max(0, parse_int(first_value(fields, "camere", "numero_camere"), 2)),
        "cucina": parse_bool(first_value(fields, "cucina"), True),
        "ambienti": [],
        "stile": stile,
        "tempistiche": tempistiche,
        "has_files": False,
    }


def parse_meta_created_at(value: Any) -> str:
    if value in (None, ""):
        return now_iso()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    text = str(value).strip()
    if text.isdigit():
        return datetime.fromtimestamp(int(text), tz=timezone.utc).isoformat()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return now_iso()


def add_minutes_iso(iso_value: str, minutes: int) -> str:
    try:
        dt = datetime.fromisoformat(iso_value)
    except ValueError:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt + timedelta(minutes=minutes)).isoformat()


def filter_tracking_payload(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    out: Dict[str, str] = {}
    for key, raw in value.items():
        normalized = normalize_field_name(key)
        if normalized.startswith("utm_") or normalized in {
            "fbclid", "gclid", "msclkid", "landing_path", "referrer"
        }:
            cleaned = clean_text(raw)
            if cleaned:
                out[normalized] = cleaned[:500]
    return out


def build_note_from_fields(fields: Dict[str, str]) -> str:
    standard = {
        "full_name", "first_name", "last_name", "nome", "nome_e_cognome",
        "email", "e_mail", "phone_number", "telefono", "numero_di_telefono",
        "cellulare", "whatsapp", "city", "citta", "comune",
    }
    lines = []
    for key, value in fields.items():
        if key in standard or not value:
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines[:20])


def build_meta_lead_doc(
    event: Dict[str, Any],
    graph_lead: Dict[str, Any],
    owner: Optional[str] = None,
) -> Dict[str, Any]:
    fields, raw_fields = flatten_field_data(graph_lead.get("field_data"))
    first_name = first_value(fields, "first_name", "nome")
    last_name = first_value(fields, "last_name", "cognome")
    nome = (
        first_value(fields, "full_name", "nome_e_cognome", "name")
        or " ".join(v for v in [first_name, last_name] if v).strip()
        or "Lead Meta Ads"
    )
    email = normalize_email(first_value(fields, "email", "e_mail", "indirizzo_email"))
    telefono = first_value(fields, "phone_number", "telefono", "numero_di_telefono", "cellulare", "whatsapp")
    citta = first_value(fields, "city", "citta", "comune", "provincia")
    cfg = build_config_from_meta_fields(fields)
    est = calcola_preventivo(cfg)
    score = max(65, lead_score(cfg, False))
    pkg = est["pacchetti"][cfg["livello"]]
    leadgen_id = clean_text(graph_lead.get("id") or event.get("leadgen_id"))
    campaign_name = clean_text(graph_lead.get("campaign_name"))
    created_at = parse_meta_created_at(
        graph_lead.get("created_time") or event.get("created_time")
    )
    tags = ["Meta Ads"]
    if score >= 75:
        tags.append("Caldo")
    if cfg["livello"] in ("premium", "luxury"):
        tags.append(cfg["livello"].capitalize())

    meta = {
        "leadgen_id": leadgen_id,
        "form_id": clean_text(graph_lead.get("form_id") or event.get("form_id")),
        "page_id": clean_text(graph_lead.get("page_id") or event.get("page_id")),
        "ad_id": clean_text(graph_lead.get("ad_id") or event.get("ad_id")),
        "ad_name": clean_text(graph_lead.get("ad_name")),
        "adset_id": clean_text(graph_lead.get("adset_id")),
        "adset_name": clean_text(graph_lead.get("adset_name")),
        "campaign_id": clean_text(graph_lead.get("campaign_id")),
        "campaign_name": campaign_name,
        "platform": clean_text(graph_lead.get("platform")),
        "field_data": raw_fields,
    }
    meta = {k: v for k, v in meta.items() if v not in ("", None, {})}

    return {
        "nome": nome,
        "email": email,
        "email_norm": email,
        "telefono": telefono,
        "phone_norm": normalize_phone(telefono),
        "citta": citta,
        "newsletter": False,
        "privacy": True,
        "tipo_immobile": cfg["tipo_immobile"],
        "mq": cfg["mq"],
        "livello": cfg["livello"],
        "bagni": cfg["bagni"],
        "camere": cfg["camere"],
        "cucina": cfg["cucina"],
        "ambienti": cfg["ambienti"],
        "stile": cfg["stile"],
        "tempistiche": cfg["tempistiche"],
        "origine": META_SOURCE,
        "fonti": [META_SOURCE],
        "status": "nuovo",
        "owner": owner,
        "score": score,
        "tags": tags,
        "has_files": False,
        "note_cliente": build_note_from_fields(fields),
        "range_basso": pkg["range_basso"],
        "range_alto": pkg["range_alto"],
        "estimate": est,
        "prossima_azione": "Contattare il lead Meta Ads entro 15 minuti",
        "timeline": [{
            "id": "ev-" + uuid.uuid4().hex[:8],
            "tipo": "lead_ricevuto",
            "testo": (
                "Lead ricevuto da Meta Ads"
                + (f" - campagna {campaign_name}" if campaign_name else "")
            ),
            "ts": now_iso(),
        }],
        "meta": meta,
        "external_ids": {"meta_leadgen_id": leadgen_id},
        "lead_created_at": created_at,
        "created_at": created_at,
        "last_contact": created_at,
        "status_changed_at": created_at,
        "first_response_at": None,
        "assigned_at": now_iso() if owner else None,
        "sla_due_at": add_minutes_iso(created_at, 15),
    }


async def choose_round_robin_owner(db) -> Optional[str]:
    users = await db.users.find({
        "role": {"$in": ["staff", "operations", "admin"]},
        "disabled": {"$ne": True},
    }).to_list(100)
    if not users:
        return None
    role_order = {"staff": 0, "operations": 1, "admin": 2}
    users.sort(key=lambda u: (role_order.get(u.get("role"), 9), u.get("name", "")))
    state = await db.lead_assignment_state.find_one_and_update(
        {"_id": "meta_ads_round_robin"},
        {"$inc": {"seq": 1}, "$set": {"updated_at": now_iso()}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    index = ((state or {}).get("seq", 1) - 1) % len(users)
    return users[index].get("name")


def build_duplicate_query(doc: Dict[str, Any]) -> Dict[str, Any]:
    conditions: List[Dict[str, Any]] = []
    leadgen_id = doc.get("external_ids", {}).get("meta_leadgen_id")
    if leadgen_id:
        conditions.append({"external_ids.meta_leadgen_id": leadgen_id})
    if doc.get("email_norm"):
        conditions.extend([
            {"email_norm": doc["email_norm"]},
            {"email": {"$regex": f"^{re.escape(doc['email_norm'])}$", "$options": "i"}},
        ])
    if doc.get("phone_norm"):
        conditions.extend([
            {"phone_norm": doc["phone_norm"]},
            {"telefono_norm": doc["phone_norm"]},
        ])
    return {"$or": conditions} if conditions else {"_id": "__never__"}


async def create_or_merge_meta_lead(
    db,
    event: Dict[str, Any],
    graph_lead: Dict[str, Any],
) -> Dict[str, Any]:
    owner = await choose_round_robin_owner(db)
    doc = build_meta_lead_doc(event, graph_lead, owner=owner)
    existing = await db.leads.find_one(build_duplicate_query(doc))
    if not existing:
        res = await db.leads.insert_one(doc)
        return {"created": True, "lead_id": str(res.inserted_id)}

    event_text = "Lead Meta Ads collegato a scheda esistente"
    if doc.get("meta", {}).get("campaign_name"):
        event_text += f" - campagna {doc['meta']['campaign_name']}"
    timeline_event = {
        "id": "ev-" + uuid.uuid4().hex[:8],
        "tipo": "dedup",
        "testo": event_text,
        "ts": now_iso(),
    }
    set_fields: Dict[str, Any] = {
        "external_ids.meta_leadgen_id": doc["external_ids"]["meta_leadgen_id"],
        "meta": doc["meta"],
        "updated_at": now_iso(),
    }
    if not existing.get("owner") and doc.get("owner"):
        set_fields["owner"] = doc["owner"]
        set_fields["assigned_at"] = now_iso()
    if doc.get("email_norm") and not existing.get("email_norm"):
        set_fields["email_norm"] = doc["email_norm"]
    if doc.get("phone_norm") and not existing.get("phone_norm"):
        set_fields["phone_norm"] = doc["phone_norm"]

    await db.leads.update_one(
        {"_id": existing["_id"]},
        {
            "$set": set_fields,
            "$addToSet": {
                "fonti": {"$each": [META_SOURCE]},
                "tags": {"$each": doc.get("tags", [])},
            },
            "$push": {"timeline": {"$each": [timeline_event], "$position": 0}},
        },
    )
    return {"created": False, "lead_id": str(existing["_id"])}


async def process_meta_webhook_event(
    db,
    event_id: str,
    page_token: Optional[str] = None,
    graph_version: Optional[str] = None,
) -> None:
    page_token = page_token or os.environ.get("META_PAGE_ACCESS_TOKEN")
    graph_version = graph_version or os.environ.get("META_GRAPH_API_VERSION", "v23.0")
    event = await db.meta_webhook_events.find_one({"_id": event_id})
    if not event:
        logger.warning("Meta webhook event not found: %s", event_id)
        return
    try:
        graph_lead = await asyncio.to_thread(
            fetch_meta_lead,
            event["leadgen_id"],
            page_token,
            graph_version,
        )
        result = await create_or_merge_meta_lead(db, event, graph_lead)
        await db.meta_webhook_events.update_one(
            {"_id": event_id},
            {"$set": {
                "status": "processed",
                "processed_at": now_iso(),
                "lead_id": result["lead_id"],
                "created_lead": result["created"],
                "last_error": None,
            }},
        )
    except Exception as exc:
        logger.exception("Meta lead processing failed")
        await db.meta_webhook_events.update_one(
            {"_id": event_id},
            {
                "$set": {"status": "failed", "last_error": str(exc), "failed_at": now_iso()},
                "$inc": {"attempts": 1},
            },
        )
