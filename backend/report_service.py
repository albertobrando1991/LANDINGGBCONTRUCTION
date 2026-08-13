"""Aggregazioni robuste e testabili per la reportistica commerciale."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


REPORT_PERIOD_DAYS = {
    "30d": 30,
    "90d": 90,
    "180d": 180,
    "365d": 365,
    "all": None,
}

REPORT_PERIOD_LABELS = {
    "30d": "Ultimi 30 giorni",
    "90d": "Ultimi 90 giorni",
    "180d": "Ultimi 6 mesi",
    "365d": "Ultimi 12 mesi",
    "all": "Tutto lo storico",
}

_STAGE_RANK = {
    "nuovo": 0,
    "qualificato": 1,
    "sopralluogo_fissato": 2,
    "sopralluogo_fatto": 2,
    "preventivo_preparazione": 2,
    "preventivo_inviato": 3,
    "follow_up": 3,
    "in_trattativa": 3,
    "chiuso_perso": 3,
    "chiuso_vinto": 4,
}

_LEVEL_LABELS = {
    "essenziale": "Essenziale",
    "premium": "Premium",
    "luxury": "Luxury",
}

_UNREPORTED_CITY_LABEL = "Non segnalata"
_UNREPORTED_CITY_VALUES = {
    "",
    "-",
    "altro",
    "altra",
    "campania",
    "da confermare",
    "da definire",
    "da verificare",
    "italia",
    "n a",
    "n d",
    "na",
    "nd",
    "nessuna",
    "nessuno",
    "non disponibile",
    "non indicata",
    "non indicato",
    "non pervenuta",
    "non pervenuto",
    "non segnalata",
    "non segnalato",
    "non specificata",
    "non specificato",
    "null",
    "provincia",
    "regione",
    "sconosciuta",
    "sconosciuto",
    "sud italia",
    "unknown",
}
_ITALIAN_REGION_NAMES = {
    "abruzzo",
    "basilicata",
    "calabria",
    "campania",
    "emilia romagna",
    "friuli venezia giulia",
    "lazio",
    "liguria",
    "lombardia",
    "marche",
    "molise",
    "piemonte",
    "puglia",
    "sardegna",
    "sicilia",
    "toscana",
    "trentino alto adige",
    "umbria",
    "valle d aosta",
    "veneto",
}
_LOWERCASE_CITY_PARTICLES = {
    "a",
    "da",
    "dal",
    "dalla",
    "de",
    "dei",
    "del",
    "della",
    "delle",
    "di",
    "in",
}


def _utc_now(value: datetime | None = None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _utc_now(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return _utc_now(parsed)


def _safe_number(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def _estimated_value(lead: dict[str, Any]) -> float:
    low = max(0.0, _safe_number(lead.get("range_basso")))
    high = max(0.0, _safe_number(lead.get("range_alto")))
    if low and high:
        return (low + high) / 2
    return high or low


def _period_start(period: str, now: datetime) -> datetime | None:
    days = REPORT_PERIOD_DAYS.get(period)
    if period not in REPORT_PERIOD_DAYS:
        raise ValueError(f"Periodo report non supportato: {period}")
    if days is None:
        return None
    return now - timedelta(days=days)


def _location_key(value: str) -> str:
    normalized = "".join(
        char
        for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    return " ".join(re.sub(r"[^a-z0-9]+", " ", normalized).split())


def _city_label(value: Any) -> str | None:
    cleaned = " ".join(str(value or "").split())
    key = _location_key(cleaned)
    is_generic_area = (
        key in _ITALIAN_REGION_NAMES
        or key.startswith("provincia di ")
        or key.startswith("regione ")
        or key.startswith("area metropolitana ")
        or key.endswith(" provincia")
        or key.endswith(" e provincia")
        or key.endswith(" e dintorni")
        or key.endswith(" area metropolitana")
    )
    if (
        not key
        or key in _UNREPORTED_CITY_VALUES
        or is_generic_area
        or not any(char.isalpha() for char in key)
    ):
        return None
    words = cleaned.title().split()
    return " ".join(
        word.casefold()
        if index > 0 and word.casefold() in _LOWERCASE_CITY_PARTICLES
        else word
        for index, word in enumerate(words)
    )


def _city_display_label(value: Any) -> str:
    return _city_label(value) or _UNREPORTED_CITY_LABEL


def _solution_label(lead: dict[str, Any]) -> str:
    level = str(lead.get("livello") or "").strip().lower()
    has_project_data = str(lead.get("tipo_immobile") or "").strip() not in {"", "-"}
    return _LEVEL_LABELS.get(level, "Da definire") if has_project_data else "Da definire"


def _month_start(value: datetime) -> datetime:
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next_month(value: datetime) -> datetime:
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1)
    return value.replace(month=value.month + 1)


def _timeline(
    leads: list[dict[str, Any]],
    *,
    period: str,
    start: datetime | None,
    now: datetime,
) -> tuple[list[dict[str, Any]], str]:
    dated = [
        (lead, created)
        for lead in leads
        if (created := _parse_datetime(lead.get("created_at"))) is not None
    ]
    if not dated:
        return [], "day" if period == "30d" else "month"

    first = start or min(created for _, created in dated)
    span_days = max(0, (now.date() - first.date()).days)
    if period == "30d" or (period == "all" and span_days <= 45):
        granularity = "day"
    elif period == "90d" or (period == "all" and span_days <= 150):
        granularity = "week"
    else:
        granularity = "month"

    counts: Counter[str] = Counter()
    for _, created in dated:
        if granularity == "day":
            key = created.date().isoformat()
        elif granularity == "week":
            key = (created - timedelta(days=created.weekday())).date().isoformat()
        else:
            key = created.strftime("%Y-%m")
        counts[key] += 1

    points: list[dict[str, Any]] = []
    if granularity == "day":
        cursor = first.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        while cursor <= end:
            key = cursor.date().isoformat()
            points.append({"data": key, "lead": counts.get(key, 0)})
            cursor += timedelta(days=1)
    elif granularity == "week":
        cursor = (first - timedelta(days=first.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        while cursor <= end:
            key = cursor.date().isoformat()
            points.append({"data": key, "lead": counts.get(key, 0)})
            cursor += timedelta(days=7)
    else:
        cursor = _month_start(first)
        end = _month_start(now)
        while cursor <= end:
            key = cursor.strftime("%Y-%m")
            points.append({"data": key, "lead": counts.get(key, 0)})
            cursor = _next_month(cursor)
    return points, granularity


def build_sales_report(
    source_leads: Iterable[dict[str, Any]],
    *,
    period: str = "all",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Costruisce il report senza dipendenze dal database o da FastAPI."""

    current = _utc_now(now)
    start = _period_start(period, current)
    all_leads = [dict(lead) for lead in source_leads if isinstance(lead, dict)]
    if start is None:
        leads = all_leads
    else:
        leads = [
            lead
            for lead in all_leads
            if (created := _parse_datetime(lead.get("created_at"))) is not None
            and created >= start
        ]

    total = len(leads)
    ranks = [_STAGE_RANK.get(str(lead.get("status") or "nuovo"), 0) for lead in leads]
    qualificati = sum(rank >= 1 for rank in ranks)
    sopralluoghi = sum(rank >= 2 for rank in ranks)
    preventivi = sum(rank >= 3 for rank in ranks)
    vinti = [lead for lead in leads if lead.get("status") == "chiuso_vinto"]
    persi = [lead for lead in leads if lead.get("status") == "chiuso_perso"]
    aperti = [
        lead
        for lead in leads
        if lead.get("status") not in {"chiuso_vinto", "chiuso_perso"}
    ]

    conversione = round((len(vinti) / total * 100) if total else 0, 1)
    valore_pipeline = round(sum(_estimated_value(lead) for lead in aperti))
    valore_chiuso = round(sum(_estimated_value(lead) for lead in vinti))

    distribution_counts = Counter(_solution_label(lead) for lead in leads)
    distribution_order = ["Essenziale", "Premium", "Luxury", "Da definire"]
    distribuzione = [
        {"name": label, "value": distribution_counts[label]}
        for label in distribution_order
        if distribution_counts[label]
    ]

    reported_cities = [
        city
        for lead in leads
        if (city := _city_label(lead.get("citta"))) is not None
    ]
    city_counts: Counter[str] = Counter(reported_cities)
    geography_reported = len(reported_cities)
    geography_unreported = total - geography_reported
    geografia = [
        {
            "citta": city,
            "lead": count,
            "percentuale": round(
                (count / geography_reported * 100) if geography_reported else 0,
                1,
            ),
        }
        for city, count in sorted(
            city_counts.items(), key=lambda item: (-item[1], item[0].casefold())
        )
    ]

    funnel_values = [
        ("Lead", total),
        ("Qualificati", qualificati),
        ("Sopralluoghi", sopralluoghi),
        ("Preventivi", preventivi),
        ("Vinti", len(vinti)),
    ]
    funnel = [
        {
            "step": step,
            "value": value,
            "percentuale": round((value / total * 100) if total else 0, 1),
        }
        for step, value in funnel_values
    ]

    timeline, timeline_granularity = _timeline(
        leads, period=period, start=start, now=current
    )
    sorted_lost = sorted(
        persi,
        key=lambda lead: _parse_datetime(
            lead.get("status_changed_at") or lead.get("created_at")
        )
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    valid_dates = [
        parsed
        for lead in leads
        if (parsed := _parse_datetime(lead.get("created_at"))) is not None
    ]
    effective_start = start or (min(valid_dates) if valid_dates else None)

    return {
        "kpi": {
            "lead_ricevuti": total,
            "lead_qualificati": qualificati,
            "sopralluoghi": sopralluoghi,
            "preventivi": preventivi,
            "chiusi_vinti": len(vinti),
            "chiusi_persi": len(persi),
            "conversione": conversione,
            "valore_pipeline": valore_pipeline,
            "valore_chiuso": valore_chiuso,
        },
        "distribuzione": distribuzione,
        "geografia": geografia,
        "copertura_geografica": {
            "segnalati": geography_reported,
            "non_segnalati": geography_unreported,
            "copertura_percentuale": round(
                (geography_reported / total * 100) if total else 0,
                1,
            ),
        },
        "funnel": funnel,
        "timeline": timeline,
        "persi": [
            {
                "id": str(lead.get("id") or lead.get("_id") or ""),
                "nome": str(lead.get("nome") or "Lead senza nome"),
                "citta": _city_display_label(lead.get("citta")),
                "livello": _solution_label(lead),
                "range": round(_estimated_value(lead)),
                "data": lead.get("status_changed_at") or lead.get("created_at"),
            }
            for lead in sorted_lost[:12]
        ],
        "meta": {
            "period": period,
            "period_label": REPORT_PERIOD_LABELS[period],
            "date_from": effective_start.isoformat() if effective_start else None,
            "date_to": current.isoformat(),
            "generated_at": current.isoformat(),
            "timeline_granularity": timeline_granularity,
            "lost_total": len(persi),
            "lost_shown": min(len(persi), 12),
        },
    }
