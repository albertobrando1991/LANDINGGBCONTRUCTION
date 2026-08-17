"""Estrazione deterministica di computi esportati da ACCA PriMus in PDF."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

import fitz
from fastapi import HTTPException

NUMBER_RE = re.compile(r"^-?\d+(?:[.´']\d{3})*(?:,\d+)?$")
UM_MAP = {
    "mq": "mq",
    "m²": "mq",
    "m2": "mq",
    "ml": "ml",
    "m": "ml",
    "mc": "mc",
    "m³": "mc",
    "m3": "mc",
    "cad": "cad",
    "cadauno": "cad",
    "corpo": "corpo",
    "a corpo": "corpo",
    "kg": "kg",
    "h": "h",
    "n": "n",
}
BOILERPLATE_PREFIXES = (
    "pag. ",
    "committente:",
    "a   r i p o r t a r e",
    "r i p o r t o",
    "num.ord.",
    "d i m e n s i o n i",
    "i m p o r t i",
    "designazione dei lavori",
    "primus by",
)
BOILERPLATE_EXACT = {
    "tariffa",
    "unità",
    "di",
    "quantità",
    "misura",
    "par.ug.",
    "lung.",
    "larg.",
    "h/peso",
    "unitario",
    "totale",
}


def _decimal(value: str) -> Decimal:
    normalized = value.replace("´", "").replace("'", "").replace(".", "")
    normalized = normalized.replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Numero ACCA non valido: {value}") from exc


def _is_boilerplate(value: str) -> bool:
    low = value.strip().lower()
    return low in BOILERPLATE_EXACT or any(
        low.startswith(prefix) for prefix in BOILERPLATE_PREFIXES
    )


def _normalize_um(value: str) -> str | None:
    return UM_MAP.get(value.strip().lower().replace("...", ""))


def _looks_like_code(value: str) -> bool:
    stripped = value.strip()
    if len(stripped) > 40:
        return False
    return bool(
        re.search(r"\d", stripped)
        and re.fullmatch(r"[A-Za-z0-9_.()\-/ ]+", stripped)
    ) or stripped.upper() in {"N.P.", "NP", "Q.E.C.", "P.F.", "M."}


def _description_and_code(lines: list[str], number: int) -> tuple[str, str]:
    content: list[str] = []
    code_parts: list[str] = []
    for line in lines:
        value = line.strip()
        low = value.lower()
        if not value or _is_boilerplate(value) or NUMBER_RE.fullmatch(value):
            continue
        if low == "totale" or low.startswith("vedi voce n"):
            continue
        if _looks_like_code(value):
            code_parts.append(value)
            continue
        content.append(value)
    description = " ".join(content).strip()
    description = re.sub(r"\s+", " ", description)
    if not description:
        description = f"Voce ACCA {number}"
    code = "".join(code_parts[:3]).replace(" ", "") or f"ACCA-{number:03d}"
    return description[:1000], code[:100]


def parse_acca_pdf(pdf_bytes: bytes) -> dict:
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Il file caricato non e un PDF valido")
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PDF non leggibile") from exc
    if document.page_count > 150:
        raise HTTPException(status_code=413, detail="PDF troppo lungo")
    lines: list[str] = []
    for page in document:
        lines.extend(line.strip() for line in page.get_text("text").splitlines())
    document.close()
    if not any("primus" in line.lower() for line in lines[:80]):
        raise HTTPException(status_code=422, detail="Formato ACCA PriMus non riconosciuto")

    items: list[dict] = []
    segment_start = 0
    expected_number = 1
    for marker_index, line in enumerate(lines):
        if not line.upper().startswith("SOMMANO"):
            continue
        marker_suffix = re.sub(r"^SOMMANO\.{0,3}", "", line, flags=re.IGNORECASE).strip()
        um = _normalize_um(marker_suffix)
        um_index = marker_index
        if not um:
            for index in range(marker_index + 1, min(marker_index + 8, len(lines))):
                um = _normalize_um(lines[index])
                if um:
                    um_index = index
                    break
        if not um or um_index is None:
            continue
        numeric: list[tuple[int, Decimal]] = []
        for index in range(um_index + 1, min(um_index + 10, len(lines))):
            value = lines[index].strip()
            if NUMBER_RE.fullmatch(value):
                numeric.append((index, _decimal(value)))
                if len(numeric) == 3:
                    break
        if len(numeric) < 3:
            continue

        number_index = next(
            (
                index
                for index in range(segment_start, marker_index)
                if lines[index].strip() == str(expected_number)
            ),
            None,
        )
        if number_index is None:
            continue
        quantity, unit_price, stated_total = (entry[1] for entry in numeric)
        description, code = _description_and_code(
            lines[number_index + 1 : marker_index], expected_number
        )
        calculated = (quantity * unit_price).quantize(Decimal("0.01"))
        delta = abs(calculated - stated_total)
        items.append(
            {
                "numero": expected_number,
                "codice": code,
                "descrizione": description,
                "um": um,
                "qta": quantity,
                "prezzo_unitario": unit_price,
                "totale_pdf": stated_total,
                "coerente": delta <= Decimal("0.05"),
            }
        )
        expected_number += 1
        segment_start = numeric[-1][0] + 1

    if not items:
        raise HTTPException(
            status_code=422,
            detail="Nessuna voce ACCA riconosciuta nel PDF",
        )
    total_document = None
    for index, line in enumerate(lines):
        compact = re.sub(r"\s+", "", line).lower()
        if compact in {"totaleeuro", "totalelavorieuro"}:
            for candidate in lines[index + 1 : index + 5]:
                if NUMBER_RE.fullmatch(candidate.strip()):
                    total_document = _decimal(candidate.strip())
                    break
    calculated_total = sum(
        (item["totale_pdf"] for item in items), Decimal("0")
    ).quantize(Decimal("0.01"))
    if total_document is None:
        raise HTTPException(
            status_code=422,
            detail="Totale finale ACCA non riconosciuto: importazione annullata",
        )
    declared_total = total_document.quantize(Decimal("0.01"))
    extraction_incomplete = (
        abs(calculated_total - declared_total) > Decimal("0.05")
    )
    if any(item["numero"] != index for index, item in enumerate(items, 1)):
        raise HTTPException(
            status_code=422,
            detail="Numerazione delle voci ACCA incompleta: importazione annullata",
        )
    return {
        "voci": items,
        "n_voci": len(items),
        "totale_pdf": calculated_total,
        "totale_documento_dichiarato": declared_total,
        "scostamento_estrazione": (declared_total - calculated_total).quantize(
            Decimal("0.01")
        ),
        "estrazione_incompleta": extraction_incomplete,
        "n_da_verificare": sum(not item["coerente"] for item in items),
    }
