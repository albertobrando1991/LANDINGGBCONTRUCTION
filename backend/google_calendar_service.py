"""Integrazione server-side con il calendario unico GB Construction.

Il CRM resta la fonte transazionale delle prenotazioni. Google Calendar viene
usato per bloccare gli impegni aziendali e come agenda condivisa degli eventi.
Le credenziali OAuth sono lette esclusivamente dall'ambiente di esecuzione.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarError(RuntimeError):
    """Errore controllato di configurazione o comunicazione con Calendar."""


class GoogleCalendarConflict(GoogleCalendarError):
    """La fascia richiesta si sovrappone a un impegno aziendale."""


@dataclass(frozen=True)
class CalendarConfig:
    enabled: bool
    calendar_id: str
    client_id: str
    client_secret: str
    refresh_token: str
    timezone: str
    timeout_seconds: float

    @property
    def configured(self) -> bool:
        return self.enabled and all(
            (self.calendar_id, self.client_id, self.client_secret, self.refresh_token)
        )


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def config() -> CalendarConfig:
    try:
        timeout = max(
            2.0, min(float(os.getenv("GOOGLE_CALENDAR_TIMEOUT_SECONDS", "10")), 30.0)
        )
    except (TypeError, ValueError):
        timeout = 10.0
    return CalendarConfig(
        enabled=_truthy(os.getenv("GOOGLE_CALENDAR_ENABLED")),
        calendar_id=(
            os.getenv("GOOGLE_CALENDAR_ID") or "gbconstructionsrls@gmail.com"
        ).strip(),
        client_id=(os.getenv("GOOGLE_CALENDAR_CLIENT_ID") or "").strip(),
        client_secret=(os.getenv("GOOGLE_CALENDAR_CLIENT_SECRET") or "").strip(),
        refresh_token=(os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN") or "").strip(),
        timezone=(os.getenv("GOOGLE_CALENDAR_TIMEZONE") or "Europe/Rome").strip(),
        timeout_seconds=timeout,
    )


def status() -> dict[str, Any]:
    cfg = config()
    missing = []
    if cfg.enabled:
        for name, value in (
            ("GOOGLE_CALENDAR_ID", cfg.calendar_id),
            ("GOOGLE_CALENDAR_CLIENT_ID", cfg.client_id),
            ("GOOGLE_CALENDAR_CLIENT_SECRET", cfg.client_secret),
            ("GOOGLE_CALENDAR_REFRESH_TOKEN", cfg.refresh_token),
        ):
            if not value:
                missing.append(name)
    return {
        "enabled": cfg.enabled,
        "configured": cfg.configured,
        "connected": False,
        "calendar_id": cfg.calendar_id,
        "timezone": cfg.timezone,
        "missing": missing,
    }


def _verify_connection_sync() -> None:
    cfg = _require_config()
    calendar_id = quote(cfg.calendar_id, safe="")
    response = _api_request(
        "GET",
        f"/calendars/{calendar_id}/events",
        params={"maxResults": 1, "singleEvents": "true"},
    )
    if response.status_code != 200:
        raise GoogleCalendarError(
            f"Verifica Google Calendar non riuscita: {_response_detail(response)}"
        )


async def connection_status() -> dict[str, Any]:
    result = status()
    if not result["configured"]:
        return result
    try:
        await asyncio.to_thread(_verify_connection_sync)
        result["connected"] = True
    except GoogleCalendarError:
        result["connection_error"] = "Autorizzazione o accesso al calendario non validi"
    return result


_token_lock = threading.Lock()
_access_token: str | None = None
_access_token_expires_at = 0.0


def _require_config() -> CalendarConfig:
    cfg = config()
    if not cfg.enabled:
        raise GoogleCalendarError("Google Calendar non e abilitato")
    if not cfg.configured:
        raise GoogleCalendarError(
            "Google Calendar e abilitato ma le credenziali OAuth sono incomplete"
        )
    try:
        ZoneInfo(cfg.timezone)
    except ZoneInfoNotFoundError as exc:
        raise GoogleCalendarError(
            f"Fuso orario Google Calendar non valido: {cfg.timezone}"
        ) from exc
    return cfg


def _get_access_token(cfg: CalendarConfig) -> str:
    global _access_token, _access_token_expires_at
    now = time.monotonic()
    with _token_lock:
        if _access_token and now < _access_token_expires_at - 60:
            return _access_token
        try:
            response = requests.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": cfg.client_id,
                    "client_secret": cfg.client_secret,
                    "refresh_token": cfg.refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=cfg.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise GoogleCalendarError("Google Calendar non raggiungibile") from exc
        if response.status_code != 200:
            detail = ""
            try:
                payload = response.json()
                detail = str(
                    payload.get("error_description") or payload.get("error") or ""
                )
            except ValueError:
                detail = response.text[:200]
            raise GoogleCalendarError(
                f"Autorizzazione Google Calendar non valida{': ' + detail if detail else ''}"
            )
        payload = response.json()
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise GoogleCalendarError("Google non ha restituito un access token")
        try:
            expires_in = max(120, int(payload.get("expires_in") or 3600))
        except (TypeError, ValueError):
            expires_in = 3600
        _access_token = token
        _access_token_expires_at = time.monotonic() + expires_in
        return token


def _api_request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> requests.Response:
    cfg = _require_config()
    token = _get_access_token(cfg)
    try:
        response = requests.request(
            method,
            f"{GOOGLE_CALENDAR_API}{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            json=json_body,
            params=params,
            timeout=cfg.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise GoogleCalendarError("Google Calendar non raggiungibile") from exc
    if response.status_code == 401:
        global _access_token_expires_at
        _access_token_expires_at = 0.0
    return response


def _local_datetime(date_value: str, time_value: str, cfg: CalendarConfig) -> datetime:
    try:
        parsed = datetime.strptime(f"{date_value} {time_value}", "%Y-%m-%d %H:%M")
        return parsed.replace(tzinfo=ZoneInfo(cfg.timezone))
    except (TypeError, ValueError) as exc:
        raise GoogleCalendarError("Data o orario del sopralluogo non validi") from exc


def _event_id(slot: dict[str, Any]) -> str:
    existing = str(slot.get("google_event_id") or "").strip().lower()
    if existing:
        return existing
    raw_id = str(slot.get("_id") or slot.get("id") or "").lower()
    clean = "".join(
        char for char in raw_id if char in "0123456789abcdefghijklmnopqrstuv"
    )
    if not clean:
        raise GoogleCalendarError("Slot senza identificativo valido")
    return f"gbcsopralluogo{clean}"


def _slot_interval(
    slot: dict[str, Any], cfg: CalendarConfig
) -> tuple[datetime, datetime]:
    start = _local_datetime(
        str(slot.get("date") or ""), str(slot.get("start") or ""), cfg
    )
    end = _local_datetime(str(slot.get("date") or ""), str(slot.get("end") or ""), cfg)
    if end <= start:
        raise GoogleCalendarError("L'orario di fine deve essere successivo all'inizio")
    return start, end


def _response_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
        error = payload.get("error") or {}
        if isinstance(error, dict):
            return str(error.get("message") or error.get("status") or "")
        return str(error)
    except ValueError:
        return response.text[:200]


def _free_busy_sync(slots: list[dict[str, Any]]) -> list[tuple[datetime, datetime]]:
    if not slots:
        return []
    cfg = _require_config()
    intervals = [_slot_interval(slot, cfg) for slot in slots]
    time_min = min(item[0] for item in intervals)
    time_max = max(item[1] for item in intervals)
    response = _api_request(
        "POST",
        "/freeBusy",
        json_body={
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "timeZone": cfg.timezone,
            "items": [{"id": cfg.calendar_id}],
        },
    )
    if response.status_code != 200:
        raise GoogleCalendarError(
            f"Controllo disponibilita Google non riuscito: {_response_detail(response)}"
        )
    payload = response.json()
    calendar = (payload.get("calendars") or {}).get(cfg.calendar_id) or {}
    if calendar.get("errors"):
        raise GoogleCalendarError("Il calendario aziendale non e accessibile")
    busy: list[tuple[datetime, datetime]] = []
    for period in calendar.get("busy") or []:
        try:
            busy.append(
                (
                    datetime.fromisoformat(str(period["start"]).replace("Z", "+00:00")),
                    datetime.fromisoformat(str(period["end"]).replace("Z", "+00:00")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return busy


def _overlaps(
    start: datetime, end: datetime, busy: Iterable[tuple[datetime, datetime]]
) -> bool:
    return any(start < busy_end and end > busy_start for busy_start, busy_end in busy)


async def filter_available_slots(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cfg = config()
    if not cfg.enabled:
        return slots
    if not cfg.configured:
        raise GoogleCalendarError("Google Calendar e abilitato ma non configurato")
    busy = await asyncio.to_thread(_free_busy_sync, slots)
    return [slot for slot in slots if not _overlaps(*_slot_interval(slot, cfg), busy)]


async def require_available(slot: dict[str, Any]) -> None:
    cfg = config()
    if not cfg.enabled:
        return
    if not cfg.configured:
        raise GoogleCalendarError("Google Calendar e abilitato ma non configurato")
    busy = await asyncio.to_thread(_free_busy_sync, [slot])
    if _overlaps(*_slot_interval(slot, cfg), busy):
        raise GoogleCalendarConflict(
            "La fascia e gia occupata nel Google Calendar aziendale"
        )


def _event_body(
    slot: dict[str, Any], lead: dict[str, Any] | None = None
) -> dict[str, Any]:
    cfg = _require_config()
    start, end = _slot_interval(slot, cfg)
    lead = lead or {}
    status_value = str(slot.get("status") or "free")
    completed = bool(slot.get("completed"))
    customer = lead.get("nome") or slot.get("booked_name") or "Cliente"
    if status_value == "free":
        summary = "Disponibilita sopralluogo GB Construction"
        transparency = "transparent"
        description = "Slot disponibile pubblicato dal CRM GB Construction."
        location = ""
    else:
        summary = f"Sopralluogo{' completato' if completed else ''} - {customer}"
        transparency = "opaque"
        details = [
            "Prenotazione sincronizzata dal CRM GB Construction.",
            f"Cliente: {customer}",
            f"Telefono: {lead.get('telefono') or slot.get('booked_phone') or '-'}",
            f"Email: {lead.get('email') or slot.get('booked_email') or '-'}",
            f"Tecnico: {slot.get('tecnico') or lead.get('owner') or 'Da assegnare'}",
        ]
        description = "\n".join(details)
        location = str(lead.get("indirizzo") or lead.get("citta") or "").strip()
    body: dict[str, Any] = {
        "id": _event_id(slot),
        "status": "confirmed",
        "summary": summary,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": cfg.timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": cfg.timezone},
        "transparency": transparency,
        "visibility": "private",
        "extendedProperties": {
            "private": {
                "source": "gbconstruction-crm",
                "slot_id": str(slot.get("_id") or slot.get("id") or ""),
                "lead_id": str(slot.get("lead_id") or ""),
                "status": "completed" if completed else status_value,
            }
        },
    }
    if location:
        body["location"] = location
    return body


def _upsert_event_sync(
    slot: dict[str, Any], lead: dict[str, Any] | None = None
) -> dict[str, Any]:
    cfg = _require_config()
    event_id = _event_id(slot)
    calendar_id = quote(cfg.calendar_id, safe="")
    event_path = f"/calendars/{calendar_id}/events/{quote(event_id, safe='')}"
    body = _event_body(slot, lead)
    patch_body = {key: value for key, value in body.items() if key != "id"}
    response = _api_request("PATCH", event_path, json_body=patch_body)
    if response.status_code == 404:
        response = _api_request(
            "POST",
            f"/calendars/{calendar_id}/events",
            json_body=body,
            params={"sendUpdates": "none"},
        )
        if response.status_code == 409:
            response = _api_request("PATCH", event_path, json_body=patch_body)
    if response.status_code not in {200, 201}:
        raise GoogleCalendarError(
            f"Sincronizzazione evento Google non riuscita: {_response_detail(response)}"
        )
    payload = response.json()
    return {
        "event_id": str(payload.get("id") or event_id),
        "html_link": str(payload.get("htmlLink") or ""),
        "updated": str(payload.get("updated") or ""),
    }


async def upsert_event(
    slot: dict[str, Any], lead: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    if not config().enabled:
        return None
    return await asyncio.to_thread(_upsert_event_sync, slot, lead)


def _delete_event_sync(slot: dict[str, Any]) -> None:
    cfg = _require_config()
    calendar_id = quote(cfg.calendar_id, safe="")
    event_id = quote(_event_id(slot), safe="")
    response = _api_request("DELETE", f"/calendars/{calendar_id}/events/{event_id}")
    if response.status_code not in {204, 404, 410}:
        raise GoogleCalendarError(
            f"Eliminazione evento Google non riuscita: {_response_detail(response)}"
        )


async def delete_event(slot: dict[str, Any]) -> None:
    if not config().enabled:
        return
    await asyncio.to_thread(_delete_event_sync, slot)
