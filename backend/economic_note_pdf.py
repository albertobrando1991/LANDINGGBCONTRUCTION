"""Note PDF firmabili per riepilogo SAL e autorizzazione extra."""

from __future__ import annotations

import io
import json
from datetime import date, datetime
from html import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from pdf_brand_assets import firma_appaltatrice


def _dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _text(value: Any) -> str:
    return escape(str(value or "-"))


def _date(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    try:
        return datetime.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(value or "-")


def _money(value: Any) -> str:
    raw = f"{float(value or 0):,.2f}"
    return "EUR " + raw.replace(",", "X").replace(".", ",").replace("X", ".")


def genera_nota_economica_pdf(documento: dict) -> bytes:
    snapshot = _dict(documento.get("snapshot"))
    cantiere = _dict(snapshot.get("cantiere"))
    tenant = {
        "ragione_sociale": documento.get("ragione_sociale"),
        "slug": documento.get("slug"),
        "piva": documento.get("piva"),
        "theme": documento.get("theme"),
        "contatti": documento.get("contatti"),
    }
    tipo = str(documento.get("tipo") or snapshot.get("tipo") or "")
    sal = _dict(snapshot.get("sal"))
    extra = _dict(snapshot.get("extra"))
    is_sal = tipo == "riepilogo_sal"
    title = (
        f"Nota di riepilogo SAL {int(sal.get('numero') or 0):02d}"
        if is_sal
        else f"Autorizzazione extra {int(extra.get('numero') or 0):02d}"
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
        author=str(tenant.get("ragione_sociale") or "GB Construction"),
    )
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "EconomicNoteTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#C62828"),
            spaceAfter=8 * mm,
        ),
        "body": ParagraphStyle(
            "EconomicNoteBody", parent=base["BodyText"], fontSize=10, leading=15
        ),
        "small": ParagraphStyle(
            "EconomicNoteSmall",
            parent=base["BodyText"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#5F6368"),
        ),
    }
    story = [
        Paragraph(_text(tenant.get("ragione_sociale") or "GB Construction"), styles["small"]),
        Paragraph(title, styles["title"]),
        Paragraph(
            f"Cantiere: <b>{_text(cantiere.get('cliente'))}</b><br/>"
            f"Indirizzo: {_text(cantiere.get('indirizzo'))}",
            styles["body"],
        ),
        Spacer(1, 6 * mm),
    ]
    if is_sal:
        rows = [
            ["Periodo", f"{_date(sal.get('periodo_da'))} - {_date(sal.get('periodo_a'))}"],
            ["Stato", str(sal.get("stato") or "-").upper()],
            ["Totale SAL", _money(sal.get("totale"))],
        ]
        statement = (
            "Il presente documento riepiloga le lavorazioni contabilizzate nel SAL "
            "indicato. Lo snapshot economico e il relativo hash garantiscono che il "
            "contenuto sottoscritto non venga sostituito dopo la firma."
        )
    else:
        rows = [
            ["Oggetto", _text(extra.get("titolo"))],
            ["Descrizione", _text(extra.get("descrizione"))],
            ["Imponibile", _money(extra.get("imponibile"))],
            ["IVA", f"{float(extra.get('iva_percentuale') or 0):.2f}%"],
            ["Totale extra", _money(extra.get("totale"))],
            ["Scadenza", _date(extra.get("data_scadenza"))],
        ]
        statement = (
            "La sottoscrizione autorizza espressamente l'esecuzione della lavorazione "
            "extra e il relativo corrispettivo, separato dal contratto originario."
        )
    table = Table(rows, colWidths=[45 * mm, 125 * mm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5D7DA")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
            ]
        )
    )
    story.extend(
        [
            table,
            Spacer(1, 7 * mm),
            Paragraph(statement, styles["body"]),
            Spacer(1, 4 * mm),
            Paragraph(
                f"Hash documento: {_text(documento.get('documento_hash'))}",
                styles["small"],
            ),
            Spacer(1, 15 * mm),
        ]
    )
    company_signature = firma_appaltatrice(tenant, width=58 * mm)
    signature_cells: list[Any] = [
        ["L'APPALTATRICE", "IL COMMITTENTE"],
        [company_signature or "Firma digitale GB", "\n\n____________________________"],
    ]
    signatures = Table(signature_cells, colWidths=[85 * mm, 85 * mm])
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
    story.append(signatures)
    doc.build(story)
    return buffer.getvalue()
