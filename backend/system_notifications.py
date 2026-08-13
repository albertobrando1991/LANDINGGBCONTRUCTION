"""Centro notifiche operativo della dashboard GB Construction.

Le notifiche sono viste derivate dai dati reali: quando la condizione che le
genera viene risolta, spariscono. Conserviamo soltanto gli ID letti per utente
nel document store tenant-scoped, cosi lo stato segue l'account su ogni device.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from document_store import ReturnDocument

logger = logging.getLogger("gb.notifications")
ROME = ZoneInfo("Europe/Rome")
MAX_NOTIFICATIONS = 50
MAX_READ_IDS = 1000
NOTIFICATION_ID_RE = re.compile(r"^[a-f0-9]{24}$")
SEVERITY_RANK = {"info": 1, "warning": 2, "urgent": 3}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min, tzinfo=ROME)
    elif value not in (None, ""):
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: Any, fallback: datetime) -> str:
    parsed = _as_datetime(value) or fallback
    return parsed.astimezone(timezone.utc).isoformat()


def _lead_arrival(lead: dict[str, Any], fallback: datetime) -> datetime:
    meta = lead.get("meta") if isinstance(lead.get("meta"), dict) else {}
    if lead.get("origine") == "meta_ads":
        value = (
            meta.get("created_time")
            or lead.get("lead_created_at")
            or lead.get("data_arrivo")
            or lead.get("created_at")
        )
    else:
        value = lead.get("created_at") or lead.get("data_arrivo")
    return _as_datetime(value) or fallback


def _stable_id(kind: str, entity_id: Any, version: Any = "") -> str:
    raw = f"{kind}:{entity_id}:{version}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _notification(
    *,
    kind: str,
    entity_id: Any,
    version: Any,
    severity: str,
    title: str,
    message: str,
    href: str,
    occurred_at: Any,
    now: datetime,
) -> dict[str, Any]:
    return {
        "id": _stable_id(kind, entity_id, version),
        "kind": kind,
        "severity": severity,
        "title": title,
        "message": message,
        "href": href,
        "occurred_at": _iso(occurred_at, now),
        "entity_id": str(entity_id),
    }


def _display_name(value: Any, fallback: str) -> str:
    clean = str(value or "").strip()
    return clean or fallback


def _money_it(value: Any) -> str:
    try:
        number = Decimal(str(value or 0))
    except Exception:
        number = Decimal("0")
    return f"{number:,.0f}".replace(",", ".")


def _document_notifications(
    leads: Iterable[dict[str, Any]],
    slots: Iterable[dict[str, Any]],
    sites: Iterable[dict[str, Any]],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    today = now.astimezone(ROME).date()
    lead_documents = list(leads)
    lead_status_by_id = {
        str(lead.get("_id") or lead.get("id")): lead.get("status")
        for lead in lead_documents
        if lead.get("_id") or lead.get("id")
    }

    for lead in lead_documents:
        if lead.get("status") != "nuovo" or lead.get("first_response_at"):
            continue
        lead_id = lead.get("_id") or lead.get("id")
        if not lead_id:
            continue
        arrival = _lead_arrival(lead, now)
        explicit_due = _as_datetime(lead.get("sla_due_at"))
        wait = (
            timedelta(minutes=15)
            if lead.get("origine") == "meta_ads"
            else timedelta(hours=18)
        )
        due = explicit_due or arrival + wait
        name = _display_name(lead.get("nome"), "Nuovo contatto")
        city = str(lead.get("citta") or "").strip()
        place = f" a {city}" if city else ""
        if now > due:
            minutes = max(1, int((now - arrival).total_seconds() // 60))
            elapsed = f"{minutes // 60} ore" if minutes >= 60 else f"{minutes} minuti"
            items.append(
                _notification(
                    kind="lead_sla",
                    entity_id=lead_id,
                    version=due.isoformat(),
                    severity="urgent",
                    title="Lead da contattare subito",
                    message=f"{name}{place} attende una risposta da {elapsed}.",
                    href=f"/dashboard/lead/{lead_id}",
                    occurred_at=due,
                    now=now,
                )
            )
        else:
            items.append(
                _notification(
                    kind="new_lead",
                    entity_id=lead_id,
                    version=arrival.isoformat(),
                    severity="info",
                    title="Nuovo lead ricevuto",
                    message=f"{name}{place} ha inviato una nuova richiesta.",
                    href=f"/dashboard/lead/{lead_id}",
                    occurred_at=arrival,
                    now=now,
                )
            )

    for slot in slots:
        lead_status = lead_status_by_id.get(str(slot.get("lead_id") or ""))
        if (
            slot.get("status") != "booked"
            or slot.get("completed")
            or lead_status == "sopralluogo_fatto"
        ):
            continue
        try:
            slot_date = date.fromisoformat(str(slot.get("date")))
        except (TypeError, ValueError):
            continue
        if slot_date not in {today, today + timedelta(days=1)}:
            continue
        slot_id = slot.get("_id") or slot.get("id")
        if not slot_id:
            continue
        when = "oggi" if slot_date == today else "domani"
        customer = _display_name(slot.get("booked_name"), "Cliente")
        start = str(slot.get("start") or "orario da definire")
        technician = str(slot.get("tecnico") or "").strip()
        suffix = f" · tecnico {technician}" if technician else ""
        items.append(
            _notification(
                kind="appointment",
                entity_id=slot_id,
                version=f"{slot_date.isoformat()}:{start}",
                severity="warning" if slot_date == today else "info",
                title=f"Sopralluogo {when}",
                message=f"{customer} alle {start}{suffix}.",
                href="/dashboard/sopralluoghi",
                occurred_at=slot.get("updated_at") or slot.get("created_at"),
                now=now,
            )
        )

    for site in sites:
        criticality = str(site.get("criticita") or "").strip()
        if not criticality or site.get("stato") == "completato":
            continue
        site_id = site.get("_id") or site.get("id")
        if not site_id:
            continue
        customer = _display_name(site.get("cliente"), "Cantiere")
        items.append(
            _notification(
                kind="site_criticality",
                entity_id=site_id,
                version=hashlib.sha256(criticality.encode("utf-8")).hexdigest()[:12],
                severity="urgent",
                title=f"Criticita cantiere · {customer}",
                message=criticality,
                href=f"/dashboard/cantieri/{site_id}",
                occurred_at=site.get("updated_at") or site.get("created_at"),
                now=now,
            )
        )
    return items


async def _postgres_notifications(
    conn: Any,
    tenant_id: str,
    user: dict[str, Any],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    quote_rows = await conn.fetch(
        """
        select p.id, p.computo_id, p.numero, p.inviato_at, p.created_at,
               coalesce(l.nome, cl.nome, 'Cliente non associato') as cliente
        from public.preventivi p
        left join public.leads l
          on l.tenant_id = p.tenant_id and l.id = p.lead_id
        left join public.clienti cl
          on cl.tenant_id = p.tenant_id and cl.id = p.cliente_id
        where p.tenant_id = $1::uuid and p.stato = 'inviato'
        order by coalesce(p.inviato_at, p.created_at) asc
        limit 100
        """,
        tenant_id,
    )
    for raw in quote_rows:
        row = dict(raw)
        sent = _as_datetime(row.get("inviato_at") or row.get("created_at"))
        if not sent:
            continue
        days = max(0, int((now - sent).total_seconds() // 86400))
        if days < 3:
            continue
        stage = 14 if days >= 14 else 7 if days >= 7 else 3
        severity = "urgent" if stage >= 7 else "warning"
        number = _display_name(row.get("numero"), "senza numero")
        customer = _display_name(row.get("cliente"), "Cliente")
        items.append(
            _notification(
                kind="quote_waiting",
                entity_id=row["id"],
                version=stage,
                severity=severity,
                title="Preventivo senza risposta",
                message=f"{number} · {customer}: inviato da {days} giorni.",
                href=f"/dashboard/computi/{row['computo_id']}",
                occurred_at=sent + timedelta(days=stage),
                now=now,
            )
        )

    if user.get("role") not in {"owner", "admin"}:
        return items

    local_today = now.astimezone(ROME).date()
    payment_rows = await conn.fetch(
        """
        select i.id, i.cantiere_id, i.descrizione, i.importo,
               i.data_prevista, i.stato, c.cliente,
               coalesce(sum(pc.importo), 0) as pagato
        from public.incassi i
        join public.cantieri c
          on c.tenant_id = i.tenant_id and c.id = i.cantiere_id
        left join public.pagamenti_cliente pc
          on pc.tenant_id = i.tenant_id and pc.incasso_id = i.id
        where i.tenant_id = $1::uuid
          and i.stato in ('previsto', 'parziale')
          and i.data_prevista <= $2::date
        group by i.id, c.cliente
        having i.importo - coalesce(sum(pc.importo), 0) > 0
        order by i.data_prevista asc
        limit 100
        """,
        tenant_id,
        local_today,
    )
    for raw in payment_rows:
        row = dict(raw)
        due_date = row.get("data_prevista")
        if not isinstance(due_date, date):
            try:
                due_date = date.fromisoformat(str(due_date))
            except (TypeError, ValueError):
                continue
        overdue_days = max(0, (local_today - due_date).days)
        stage = 30 if overdue_days >= 30 else 7 if overdue_days >= 7 else 0
        remaining = Decimal(str(row.get("importo") or 0)) - Decimal(
            str(row.get("pagato") or 0)
        )
        customer = _display_name(row.get("cliente"), "Cliente")
        timing = (
            "scade oggi" if overdue_days == 0 else f"scaduto da {overdue_days} giorni"
        )
        items.append(
            _notification(
                kind="payment_due",
                entity_id=row["id"],
                version=stage,
                severity="urgent" if overdue_days > 0 else "warning",
                title="Incasso da verificare",
                message=f"{customer}: {timing}, residuo EUR {_money_it(remaining)}.",
                href="/dashboard/economics",
                occurred_at=datetime.combine(due_date, time.min, tzinfo=ROME),
                now=now,
            )
        )
    return items


def _user_state_id(user: dict[str, Any]) -> str:
    identity = (
        str(user.get("id") or user.get("sub") or user.get("email") or "anonymous")
        .strip()
        .lower()
    )
    return f"system-notifications-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32]}"


async def _read_ids(document_db: Any, user: dict[str, Any]) -> set[str]:
    state = await document_db.system_notification_states.find_one(
        {"_id": _user_state_id(user)}
    )
    return {
        str(item)
        for item in (state or {}).get("read_ids", [])
        if NOTIFICATION_ID_RE.fullmatch(str(item))
    }


async def collect_notifications(
    document_db: Any,
    conn: Any,
    tenant_id: str,
    user: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = (now or _utc_now()).astimezone(timezone.utc)
    leads = await document_db.leads.find({}).to_list(1000)
    slots = await document_db.sopralluogo_slots.find({"status": "booked"}).to_list(500)
    sites = await document_db.cantieri.find({}).to_list(500)
    items = _document_notifications(leads, slots, sites, now=current)
    try:
        items.extend(await _postgres_notifications(conn, tenant_id, user, now=current))
    except Exception as exc:
        # Lead e cantieri restano fruibili anche se una sorgente EdilOS ha un
        # guasto temporaneo o una migrazione non ancora applicata.
        logger.warning("Sorgenti EdilOS notifiche non disponibili: %s", exc)

    read_ids = await _read_ids(document_db, user)
    unique: dict[str, dict[str, Any]] = {}
    for item in items:
        item["read"] = item["id"] in read_ids
        unique[item["id"]] = item
    ordered = sorted(
        unique.values(),
        key=lambda item: (
            not item["read"],
            SEVERITY_RANK.get(item.get("severity"), 0),
            _as_datetime(item.get("occurred_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )[:MAX_NOTIFICATIONS]
    return {
        "items": ordered,
        "unread_count": sum(1 for item in ordered if not item["read"]),
        "generated_at": current.isoformat(),
    }


async def mark_notifications_read(
    document_db: Any,
    user: dict[str, Any],
    notification_ids: Iterable[str],
) -> int:
    clean_ids = list(
        dict.fromkeys(
            str(item)
            for item in notification_ids
            if NOTIFICATION_ID_RE.fullmatch(str(item))
        )
    )
    if not clean_ids:
        return 0
    state_id = _user_state_id(user)
    updated = await document_db.system_notification_states.find_one_and_update(
        {"_id": state_id},
        {
            "$set": {"updated_at": _utc_now().isoformat()},
            "$setOnInsert": {"created_at": _utc_now().isoformat()},
            "$addToSet": {"read_ids": {"$each": clean_ids}},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    read_ids = [str(item) for item in (updated or {}).get("read_ids", [])]
    if len(read_ids) > MAX_READ_IDS:
        await document_db.system_notification_states.update_one(
            {"_id": state_id},
            {"$set": {"read_ids": read_ids[-MAX_READ_IDS:]}},
        )
    return len(clean_ids)
