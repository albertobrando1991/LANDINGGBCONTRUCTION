"""Generazione PDF preventivo white-label con reportlab.
Nessun riferimento hardcoded a GB Construction: branding da tenants.theme/contatti.
"""
from __future__ import annotations

import io
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _hex_color(value: str, fallback: str = "#111111") -> colors.Color:
    raw = (value or fallback).lstrip("#")
    if len(raw) != 6:
        raw = fallback.lstrip("#")
    try:
        r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
        return colors.Color(r / 255, g / 255, b / 255)
    except Exception:
        return colors.black


def genera_pdf_preventivo(preventivo: dict, tenant: dict) -> bytes:
    theme = tenant.get("theme") or {}
    contatti = tenant.get("contatti") or {}
    primary = _hex_color(theme.get("primary") or "#C41E3A")
    secondary = _hex_color(theme.get("secondary") or "#D4AF37")
    ragione = tenant.get("ragione_sociale") or tenant.get("slug") or "Preventivo"

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleBrand", parent=styles["Heading1"], textColor=primary, fontSize=18, spaceAfter=6
    )
    sub_style = ParagraphStyle("Sub", parent=styles["Normal"], textColor=colors.HexColor("#444444"), fontSize=10)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9, leading=12)

    story = []
    story.append(Paragraph(ragione, title_style))
    contatto_line = " · ".join(
        x for x in [
            contatti.get("telefono"),
            contatti.get("email"),
            contatti.get("indirizzo"),
        ] if x
    )
    if contatto_line:
        story.append(Paragraph(contatto_line, sub_style))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(f"Preventivo <b>{preventivo.get('numero')}</b>", styles["Heading2"]))
    story.append(Paragraph(
        f"Stato: {preventivo.get('stato')} · IVA {preventivo.get('iva_percentuale')}% · "
        f"Sconto {preventivo.get('sconto_percentuale')}%",
        body,
    ))
    story.append(Spacer(1, 6 * mm))

    snapshot = preventivo.get("snapshot_voci") or []
    if isinstance(snapshot, str):
        import json
        snapshot = json.loads(snapshot)

    data = [["#", "Descrizione", "UM", "Q.tà", "Prezzo", "Totale"]]
    for i, v in enumerate(snapshot, 1):
        qta = float(v.get("qta") or 0)
        pu = float(v.get("prezzo_unitario") or 0)
        tot = float(v.get("totale") or round(qta * pu, 2))
        data.append([
            str(i),
            (v.get("descrizione") or "")[:60],
            v.get("um") or "",
            f"{qta:.2f}",
            f"€ {pu:,.2f}",
            f"€ {tot:,.2f}",
        ])

    table = Table(data, colWidths=[12 * mm, 80 * mm, 15 * mm, 20 * mm, 25 * mm, 25 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primary),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(table)
    story.append(Spacer(1, 8 * mm))

    totals = [
        ["Imponibile", f"€ {float(preventivo.get('totale_imponibile') or 0):,.2f}"],
        ["IVA", f"€ {float(preventivo.get('totale_iva') or 0):,.2f}"],
        ["Totale documento", f"€ {float(preventivo.get('totale_documento') or 0):,.2f}"],
    ]
    t2 = Table(totals, colWidths=[120 * mm, 40 * mm])
    t2.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, -1), (-1, -1), primary),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, secondary),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    story.append(t2)
    if preventivo.get("note"):
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(f"Note: {preventivo['note']}", body))

    doc.build(story)
    return buf.getvalue()
