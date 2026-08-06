"""Documento PDF SAL con allegato del libretto misure sorgente."""

from __future__ import annotations

import io
import json
from datetime import date, datetime
from html import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _color(value: Any, fallback: str) -> colors.Color:
    raw = str(value or fallback).strip()
    try:
        return colors.HexColor(raw)
    except (TypeError, ValueError):
        return colors.HexColor(fallback)


def _date_it(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    try:
        return datetime.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(value or "-")


def _number_it(value: Any, decimals: int = 3) -> str:
    number = float(value or 0)
    raw = f"{number:,.{decimals}f}"
    return raw.replace(",", "X").replace(".", ",").replace("X", ".")


def _money(value: Any) -> str:
    return f"EUR {_number_it(value, 2)}"


def _text(value: Any) -> str:
    return escape(str(value or "-"))


def _measurement_formula(row: dict) -> str:
    dimensions = [
        row.get("lunghezza"),
        row.get("larghezza"),
        row.get("altezza"),
    ]
    factors = []
    if int(row.get("parti") or 1) != 1:
        factors.append(str(int(row.get("parti") or 1)))
    factors.extend(_number_it(value) for value in dimensions if value is not None)
    return " x ".join(factors) if factors else "Quantita diretta"


def _page_decorator(ragione: str, stato: str, primary: colors.Color):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setTitle(f"SAL {doc.sal_number} - {ragione}")
        canvas.setAuthor(ragione)
        canvas.setSubject("Stato avanzamento lavori e libretto delle misure")
        if stato == "bozza":
            canvas.saveState()
            canvas.setFillColor(colors.Color(0.75, 0.75, 0.75, alpha=0.15))
            canvas.setFont("Helvetica-Bold", 48)
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "BOZZA")
            canvas.restoreState()
        canvas.setStrokeColor(primary)
        canvas.setLineWidth(0.6)
        canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
        canvas.setFillColor(colors.HexColor("#5E6470"))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(18 * mm, 8.5 * mm, f"{ragione} - Contabilita di cantiere")
        canvas.drawString(
            A4[0] - 36 * mm,
            8.5 * mm,
            f"Pagina {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    return draw


def genera_pdf_sal(documento: dict) -> bytes:
    """Genera un PDF A4 con SAL economico e allegato del libretto misure."""
    sal = documento.get("sal") or {}
    cantiere = documento.get("cantiere") or {}
    tenant = documento.get("tenant") or {}
    misure = documento.get("misure") or []
    theme = _as_dict(tenant.get("theme"))
    contatti = _as_dict(tenant.get("contatti"))
    primary = _color(theme.get("primary"), "#C41E3A")
    secondary = _color(theme.get("secondary"), "#D4AF37")
    ragione = str(tenant.get("ragione_sociale") or tenant.get("slug") or "Impresa")
    stato = str(sal.get("stato") or "bozza").lower()
    numero = int(sal.get("numero") or 0)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"SAL {numero:02d} - {ragione}",
        author=ragione,
    )
    doc.sal_number = f"{numero:02d}"

    base = getSampleStyleSheet()
    styles = {
        "brand": ParagraphStyle(
            "SalBrand",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=21,
            textColor=primary,
            spaceAfter=2 * mm,
        ),
        "title": ParagraphStyle(
            "SalTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=23,
            textColor=colors.HexColor("#16181D"),
        ),
        "section": ParagraphStyle(
            "SalSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=primary,
            spaceBefore=4 * mm,
            spaceAfter=3 * mm,
        ),
        "body": ParagraphStyle(
            "SalBody", parent=base["Normal"], fontSize=8.5, leading=11
        ),
        "small": ParagraphStyle(
            "SalSmall",
            parent=base["Normal"],
            fontSize=7.2,
            leading=9,
            textColor=colors.HexColor("#4E5562"),
        ),
        "right": ParagraphStyle(
            "SalRight",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            alignment=TA_RIGHT,
        ),
        "center": ParagraphStyle(
            "SalCenter",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.white,
        ),
    }

    contact_parts = [
        contatti.get("indirizzo"),
        contatti.get("telefono"),
        contatti.get("email"),
    ]
    company_lines = [Paragraph(_text(ragione), styles["brand"])]
    if tenant.get("piva"):
        company_lines.append(
            Paragraph(f"P. IVA {_text(tenant['piva'])}", styles["small"])
        )
    if any(contact_parts):
        company_lines.append(
            Paragraph(
                " - ".join(_text(value) for value in contact_parts if value),
                styles["small"],
            )
        )
    header = Table(
        [
            [
                company_lines,
                [
                    Paragraph(f"SAL {numero:02d}", styles["title"]),
                    Paragraph(f"Stato: <b>{_text(stato.upper())}</b>", styles["right"]),
                ],
            ]
        ],
        colWidths=[116 * mm, 56 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("BOX", (0, 0), (-1, -1), 0.8, primary),
                ("LINEBEFORE", (1, 0), (1, 0), 0.8, primary),
                ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#F5F6F8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]
        )
    )

    story = [header, Spacer(1, 6 * mm)]
    meta = [
        ["CANTIERE", "COMMITTENTE", "PERIODO", "CAPOCANTIERE"],
        [
            Paragraph(
                _text(cantiere.get("indirizzo") or "Sede non indicata"), styles["body"]
            ),
            Paragraph(_text(cantiere.get("cliente")), styles["body"]),
            Paragraph(
                f"{_date_it(sal.get('periodo_da'))} - {_date_it(sal.get('periodo_a'))}",
                styles["body"],
            ),
            Paragraph(
                _text(cantiere.get("capocantiere") or "Non indicato"), styles["body"]
            ),
        ],
    ]
    meta_table = Table(meta, colWidths=[48 * mm, 46 * mm, 42 * mm, 36 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#22252B")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 6.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#CED2D9")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DADDE2")),
                ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
            ]
        )
    )
    story.extend(
        [meta_table, Paragraph("Quadro economico del periodo", styles["section"])]
    )

    table_data = [
        [
            Paragraph("#", styles["center"]),
            Paragraph("DESCRIZIONE", styles["center"]),
            Paragraph("UM", styles["center"]),
            Paragraph("PERIODO", styles["center"]),
            Paragraph("PROGR.", styles["center"]),
            Paragraph("CONTR.", styles["center"]),
            Paragraph("PREZZO", styles["center"]),
            Paragraph("IMPORTO", styles["center"]),
        ]
    ]
    for index, row in enumerate(sal.get("righe") or [], 1):
        description = _text(row.get("descrizione"))
        if row.get("in_eccedenza"):
            description += f"<br/><font color='#B45309'><b>Eccedenza: {_number_it(row.get('eccedenza_qta'))} {_text(row.get('um'))}</b></font>"
        table_data.append(
            [
                str(index),
                Paragraph(description, styles["small"]),
                _text(row.get("um")),
                _number_it(row.get("qta_periodo")),
                _number_it(row.get("qta_progressiva")),
                _number_it(row.get("qta_contrattuale")),
                _money(row.get("prezzo_unitario")),
                _money(row.get("importo_periodo")),
            ]
        )
    sal_table = Table(
        table_data,
        repeatRows=1,
        colWidths=[
            7 * mm,
            51 * mm,
            10 * mm,
            17 * mm,
            17 * mm,
            17 * mm,
            25 * mm,
            28 * mm,
        ],
    )
    sal_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), primary),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (-1, -1), 7),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8DBE0")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F7F8FA")],
                ),
                ("LEFTPADDING", (0, 0), (-1, -1), 1.5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1.5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
            ]
        )
    )
    story.append(sal_table)
    story.append(Spacer(1, 4 * mm))

    warnings = sum(1 for row in sal.get("righe") or [] if row.get("in_eccedenza"))
    totals = Table(
        [
            ["Voci contabilizzate", str(len(sal.get("righe") or []))],
            ["Voci in eccedenza", str(warnings)],
            ["TOTALE SAL DEL PERIODO", _money(sal.get("totale_periodo"))],
        ],
        colWidths=[125 * mm, 47 * mm],
    )
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, -1), (-1, -1), primary),
                ("LINEABOVE", (0, -1), (-1, -1), 1.2, secondary),
                ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
            ]
        )
    )
    story.append(totals)
    if warnings:
        warning_box = Table(
            [
                [
                    Paragraph(
                        "<b>ATTENZIONE:</b> il SAL contiene quantita progressive superiori al contratto. "
                        "Le eccedenze non sono bloccate e devono essere verificate prima dell'approvazione.",
                        styles["body"],
                    )
                ]
            ],
            colWidths=[172 * mm],
        )
        warning_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF4D6")),
                    ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#D39B00")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
                ]
            )
        )
        story.extend([Spacer(1, 4 * mm), warning_box])

    story.extend(
        [
            Spacer(1, 8 * mm),
            Paragraph(
                "Il quadro economico e uno snapshot delle quantita e dei prezzi al momento della generazione del SAL. "
                "Le rilevazioni sorgente sono riportate nell'Allegato A.",
                styles["small"],
            ),
            Spacer(1, 10 * mm),
        ]
    )
    signatures = Table(
        [
            ["L'IMPRESA", "DIREZIONE LAVORI / COMMITTENTE"],
            ["\n\n____________________________", "\n\n____________________________"],
        ],
        colWidths=[86 * mm, 86 * mm],
    )
    signatures.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ]
        )
    )
    story.extend([signatures, PageBreak()])

    story.append(Paragraph("Allegato A - Libretto delle misure", styles["title"]))
    story.append(
        Paragraph(
            f"Rilevazioni dal {_date_it(sal.get('periodo_da'))} al {_date_it(sal.get('periodo_a'))} "
            f"utilizzate per il SAL {numero:02d}.",
            styles["body"],
        )
    )
    story.append(Spacer(1, 5 * mm))
    if misure:
        measure_data = [
            [
                Paragraph("DATA", styles["center"]),
                Paragraph("VOCE / DESCRIZIONE", styles["center"]),
                Paragraph("MISURAZIONE", styles["center"]),
                Paragraph("Q.TA", styles["center"]),
                Paragraph("UM", styles["center"]),
                Paragraph("FOTO", styles["center"]),
            ]
        ]
        for row in misure:
            description = _text(
                row.get("descrizione")
                or row.get("computo_voce_descrizione")
                or "Misura senza descrizione"
            )
            if row.get("descrizione") and row.get("computo_voce_descrizione"):
                description += f"<br/><font color='#5E6470'>{_text(row.get('computo_voce_descrizione'))}</font>"
            measure_data.append(
                [
                    _date_it(row.get("data_misura")),
                    Paragraph(description, styles["small"]),
                    Paragraph(_text(_measurement_formula(row)), styles["small"]),
                    _number_it(row.get("qta")),
                    _text(row.get("computo_voce_um") or row.get("um")),
                    str(len(row.get("foto_paths") or [])),
                ]
            )
        measure_table = Table(
            measure_data,
            repeatRows=1,
            colWidths=[21 * mm, 64 * mm, 43 * mm, 20 * mm, 11 * mm, 13 * mm],
        )
        measure_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#22252B")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 1), (-1, -1), 7),
                    ("ALIGN", (0, 1), (0, -1), "CENTER"),
                    ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8DBE0")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F7F8FA")],
                    ),
                    ("LEFTPADDING", (0, 0), (-1, -1), 1.7 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 1.7 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
                ]
            )
        )
        story.append(measure_table)
    else:
        story.append(
            Paragraph(
                "Nessuna rilevazione sorgente disponibile per il periodo selezionato.",
                styles["body"],
            )
        )
    story.extend(
        [
            Spacer(1, 5 * mm),
            Paragraph(
                f"Totale rilevazioni documentate: <b>{len(misure)}</b>. Il libretto e append-only: "
                "eventuali correzioni sono registrate come nuove righe di segno opposto.",
                styles["small"],
            ),
        ]
    )

    decorator = _page_decorator(ragione, stato, primary)
    doc.build(story, onFirstPage=decorator, onLaterPages=decorator)
    return buffer.getvalue()
