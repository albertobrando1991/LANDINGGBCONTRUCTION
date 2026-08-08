"""Preventivo professionale A4 con branding tenant e identità GB."""
from __future__ import annotations

import io
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import cronoprogramma
import fasi_lavorazione
import preventivo_pdf_blocchi as blocchi
import preventivo_struttura

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "email-logo.png"
COVER_PATH = Path(__file__).resolve().parent / "assets" / "document-cover.jpg"
LIVELLI_DETTAGLIO = ("analitico", "sintetico")


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
    try:
        return colors.HexColor(str(value or fallback).strip())
    except (TypeError, ValueError):
        return colors.HexColor(fallback)


_text = blocchi.testo
_money = blocchi.importo
_number = blocchi.numero


def _date_it(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime(
            "%d/%m/%Y"
        )
    except (TypeError, ValueError):
        return str(value or "-")


def _page_decorator(ragione: str, numero: str, stato: str, primary: colors.Color):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setTitle(f"Preventivo {numero} - {ragione}")
        canvas.setAuthor(ragione)
        canvas.setSubject("Preventivo professionale lavori edili")
        if stato == "bozza":
            canvas.saveState()
            canvas.setFillColor(colors.Color(0.45, 0.45, 0.45, alpha=0.09))
            canvas.setFont("Helvetica-Bold", 52)
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "BOZZA")
            canvas.restoreState()
        canvas.setStrokeColor(primary)
        canvas.setLineWidth(0.7)
        canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
        canvas.setFillColor(colors.HexColor("#62666D"))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(18 * mm, 8.5 * mm, f"{ragione} - Preventivo {numero}")
        canvas.drawRightString(
            A4[0] - 18 * mm, 8.5 * mm, f"Pagina {canvas.getPageNumber()}"
        )
        canvas.restoreState()

    return draw


def _cover_decorator(
    ragione: str,
    numero: str,
    cliente: str,
    intervento: str,
    totale: str,
    data_emissione: str,
    primary: colors.Color,
):
    """Copertina fotografica, costruita come apertura editoriale."""
    def draw(canvas, _doc):
        width, height = A4
        canvas.saveState()
        canvas.setTitle(f"Preventivo {numero} - {ragione}")
        canvas.setAuthor(ragione)
        canvas.setSubject("Proposta economica professionale")
        canvas.setFillColor(colors.HexColor("#141416"))
        canvas.rect(0, 0, width, height, stroke=0, fill=1)
        if COVER_PATH.exists():
            image = ImageReader(str(COVER_PATH))
            image_width, image_height = image.getSize()
            scale = max(width / image_width, height / image_height)
            draw_width = image_width * scale
            draw_height = image_height * scale
            canvas.saveState()
            path = canvas.beginPath()
            path.rect(0, 0, width, height)
            canvas.clipPath(path, stroke=0, fill=0)
            canvas.drawImage(
                image,
                (width - draw_width) / 2,
                (height - draw_height) / 2,
                width=draw_width,
                height=draw_height,
                mask="auto",
            )
            canvas.restoreState()
        canvas.setFillColor(colors.Color(0.035, 0.035, 0.045, alpha=0.50))
        canvas.rect(0, 0, width, height, stroke=0, fill=1)
        canvas.setFillColor(colors.Color(0.035, 0.035, 0.045, alpha=0.88))
        canvas.rect(0, 0, width, 105 * mm, stroke=0, fill=1)
        canvas.setFillColor(primary)
        canvas.rect(0, 0, 11 * mm, height, stroke=0, fill=1)
        canvas.rect(11 * mm, 101 * mm, width - 11 * mm, 4 * mm, stroke=0, fill=1)

        if LOGO_PATH.exists():
            canvas.drawImage(
                str(LOGO_PATH), 22 * mm, height - 53 * mm,
                width=37 * mm, height=31 * mm, mask="auto",
            )
        canvas.setFillColor(colors.HexColor("#F5F3EF"))
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(64 * mm, height - 32 * mm, ragione.upper())
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#C8C5BF"))
        canvas.drawString(64 * mm, height - 38 * mm, "COSTRUIAMO SPAZI. TRASFORMIAMO IL MODO DI VIVERLI.")

        canvas.setFillColor(colors.HexColor("#F5F3EF"))
        canvas.setFont("Helvetica-Bold", 35)
        canvas.drawString(22 * mm, 77 * mm, "PROPOSTA")
        canvas.drawString(22 * mm, 62 * mm, "ECONOMICA")
        canvas.setFillColor(primary)
        canvas.rect(22 * mm, 54 * mm, 31 * mm, 2.2 * mm, stroke=0, fill=1)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.setFillColor(colors.HexColor("#F5F3EF"))
        canvas.drawString(22 * mm, 44 * mm, f"{numero}  /  {data_emissione}")

        canvas.setFillColor(colors.HexColor("#A9A6A0"))
        canvas.setFont("Helvetica-Bold", 6.5)
        canvas.drawString(112 * mm, 88 * mm, "PER")
        canvas.setFillColor(colors.HexColor("#F5F3EF"))
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(112 * mm, 82 * mm, cliente[:42])
        canvas.setFillColor(colors.HexColor("#A9A6A0"))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(112 * mm, 76 * mm, intervento[:58])

        canvas.setFillColor(colors.HexColor("#A9A6A0"))
        canvas.setFont("Helvetica-Bold", 6.5)
        canvas.drawString(112 * mm, 54 * mm, "INVESTIMENTO")
        canvas.setFillColor(colors.HexColor("#F5F3EF"))
        canvas.setFont("Helvetica-Bold", 18)
        canvas.drawString(112 * mm, 45 * mm, totale)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor("#A9A6A0"))
        canvas.drawString(112 * mm, 39 * mm, "IMPORTO COMPLESSIVO IVA INCLUSA")

        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor("#A9A6A0"))
        canvas.drawString(22 * mm, 15 * mm, "DOCUMENTO RISERVATO  /  GB CONSTRUCTION")
        canvas.restoreState()

    return draw


def genera_pdf_preventivo(
    preventivo: dict, tenant: dict, *, dettaglio: str = "analitico"
) -> bytes:
    theme = _as_dict(tenant.get("theme"))
    contatti = _as_dict(tenant.get("contatti"))
    primary = _color(theme.get("primary"), "#B8202E")
    secondary = _color(theme.get("secondary"), "#B8A16A")
    graphite = colors.HexColor("#202226")
    soft = colors.HexColor("#F3F1ED")
    line = colors.HexColor("#D8D4CD")
    ragione = str(tenant.get("ragione_sociale") or "GB Construction S.r.l.")
    numero = str(preventivo.get("numero") or "BOZZA")
    stato = str(preventivo.get("stato") or "bozza").lower()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title=f"Preventivo {numero} - {ragione}",
        author=ragione,
    )
    base = getSampleStyleSheet()
    styles = {
        "brand": ParagraphStyle(
            "QuoteBrand", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=15, leading=18, textColor=graphite, spaceAfter=1 * mm,
        ),
        "title": ParagraphStyle(
            "QuoteTitle", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=25, leading=28, textColor=primary, alignment=TA_RIGHT,
        ),
        "section": ParagraphStyle(
            "QuoteSection", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11, leading=14, textColor=primary,
            spaceBefore=5 * mm, spaceAfter=2.5 * mm,
        ),
        "body": ParagraphStyle(
            "QuoteBody", parent=base["Normal"], fontSize=8.5, leading=11,
            textColor=graphite,
        ),
        "small": ParagraphStyle(
            "QuoteSmall", parent=base["Normal"], fontSize=7.2, leading=9,
            textColor=colors.HexColor("#5D6168"),
        ),
        "table": ParagraphStyle(
            "QuoteTable", parent=base["Normal"], fontSize=7.2, leading=9,
            textColor=graphite,
        ),
        "table_head": ParagraphStyle(
            "QuoteTableHead", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=6.7, leading=8, textColor=colors.white,
        ),
        "right": ParagraphStyle(
            "QuoteRight", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=9, leading=11, alignment=TA_RIGHT, textColor=graphite,
        ),
        "fase_numero": ParagraphStyle(
            "QuotePhaseNumber", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=13, leading=15, textColor=secondary,
        ),
        "fase_titolo": ParagraphStyle(
            "QuotePhaseTitle", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=9, leading=12, textColor=colors.white,
        ),
        "fase_importo": ParagraphStyle(
            "QuotePhaseAmount", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=9.5, leading=12, alignment=TA_RIGHT, textColor=colors.white,
        ),
    }
    palette = {
        "primary": primary,
        "secondary": secondary,
        "graphite": graphite,
        "soft": soft,
        "line": line,
    }

    is_gb = "gbconstruction" in str(tenant.get("slug") or "").lower()
    logo = None
    if is_gb and LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=29 * mm, height=24.5 * mm)
    company = [Paragraph(_text(ragione), styles["brand"])]
    if tenant.get("piva"):
        company.append(Paragraph(f"P. IVA {_text(tenant['piva'])}", styles["small"]))
    contact_line = " · ".join(
        _text(value) for value in (
            contatti.get("indirizzo"), contatti.get("telefono"), contatti.get("email")
        ) if value
    )
    if contact_line:
        company.append(Paragraph(contact_line, styles["small"]))
    identity = [logo, company] if logo else [company]
    left_widths = [34 * mm, 79 * mm] if logo else [113 * mm]
    identity_table = Table([identity], colWidths=left_widths)
    identity_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    title_block = [
        Paragraph("PREVENTIVO", styles["title"]),
        Paragraph(f"N. <b>{_text(numero)}</b>", styles["right"]),
        Paragraph(f"Emesso il {_date_it(preventivo.get('created_at'))}", styles["small"]),
    ]
    header = Table([[identity_table, title_block]], colWidths=[115 * mm, 57 * mm])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 1.2, primary),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    cliente = preventivo.get("cliente_nome") or "Cliente non associato"
    cliente_lines = [Paragraph("DESTINATARIO", styles["table_head"]), Paragraph(f"<b>{_text(cliente)}</b>", styles["body"])]
    for value in (preventivo.get("cliente_indirizzo"), preventivo.get("cliente_citta"), preventivo.get("cliente_email"), preventivo.get("cliente_telefono")):
        if value:
            cliente_lines.append(Paragraph(_text(value), styles["small"]))
    project_lines = [Paragraph("INTERVENTO", styles["table_head"])]
    project_lines.append(Paragraph(_text(preventivo.get("cantiere_indirizzo"), "Sede da definire"), styles["body"]))
    validity = int(preventivo.get("validita_giorni") or 30)
    project_lines.append(Paragraph(f"Validità offerta: <b>{validity} giorni</b>", styles["small"]))
    info = Table([[cliente_lines, project_lines]], colWidths=[86 * mm, 86 * mm])
    info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), soft),
        ("BOX", (0, 0), (-1, -1), 0.5, line),
        ("LINEBEFORE", (1, 0), (1, 0), 0.5, line),
        ("BACKGROUND", (0, 0), (0, 0), soft),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))

    snapshot = preventivo.get("snapshot_voci") or []
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)
    sintetico = str(dettaglio or "analitico").lower() == "sintetico"

    # Senza fasi (preventivi anteriori alla classificazione) resta l'elenco piatto.
    classificato = any(voce.get("fase") for voce in snapshot)
    if classificato:
        gruppi = [
            {**gruppo, "voci": preventivo_struttura.aggrega_voci_gemelle(gruppo["voci"])}
            for gruppo in fasi_lavorazione.raggruppa_per_fase(snapshot)
        ]
        opere = blocchi.quadro_economico(gruppi, styles, palette)
        costruttore = (
            blocchi.sezione_fase_sintetica if sintetico else blocchi.sezione_fase
        )
        for indice, gruppo in enumerate(gruppi, 1):
            opere.extend(costruttore(indice, gruppo, styles, palette))
    else:
        gruppi = []
        opere = blocchi.tabella_voci_piatta(
            preventivo_struttura.aggrega_voci_gemelle(snapshot), styles, palette
        )

    subtotal = float(preventivo.get("totale_imponibile") or 0)
    discount = float(preventivo.get("sconto_percentuale") or 0)
    vat = float(preventivo.get("iva_percentuale") or 0)
    totals_data = [["Imponibile", _money(subtotal)]]
    if discount:
        totals_data.append([f"Sconto applicato ({_number(discount)}%)", f"- {_money(subtotal * discount / 100)}"])
    totals_data.extend([
        [f"IVA ({_number(vat)}%)", _money(preventivo.get("totale_iva"))],
        ["TOTALE OFFERTA", _money(preventivo.get("totale_documento"))],
    ])
    totals = Table(totals_data, colWidths=[118 * mm, 54 * mm])
    totals.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -2), 9),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), primary),
        ("LINEABOVE", (0, 0), (-1, 0), 0.7, secondary),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))

    conditions = (
        "Gli importi si riferiscono esclusivamente alle lavorazioni elencate. "
        "Eventuali varianti, opere impreviste o quantità eccedenti saranno concordate e contabilizzate separatamente. "
        "Tempi di esecuzione e modalità di pagamento saranno definiti prima dell'avvio dei lavori."
    )
    signatures = Table([
        ["PER ACCETTAZIONE DEL CLIENTE", "PER L'IMPRESA"],
        ["Data ____________________\n\nFirma __________________________", "Data ____________________\n\nFirma __________________________"],
    ], colWidths=[86 * mm, 86 * mm])
    signatures.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 1), (-1, -1), 5 * mm),
    ]))

    cover_space = Spacer(1, 252 * mm)
    story = [
        cover_space, PageBreak(),
        header, Spacer(1, 5 * mm), info,
        Spacer(1, 2 * mm),
        Table(
            [[
                Paragraph("01", ParagraphStyle(
                    "QuoteChapterNumber", parent=styles["title"], fontSize=34,
                    leading=36, alignment=0, textColor=primary,
                )),
                Paragraph(
                    "Una proposta costruita intorno al progetto.<br/>"
                    "Le lavorazioni sono raccolte nelle fasi di cantiere che le "
                    "eseguono, cosi da leggere subito dove va ogni euro.",
                    ParagraphStyle(
                        "QuoteEditorialIntro", parent=styles["body"], fontSize=12,
                        leading=16, textColor=graphite,
                    ),
                ),
            ]],
            colWidths=[28 * mm, 144 * mm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.7, secondary),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
            ]),
        ),
        *opere,
        Spacer(1, 5 * mm),
        totals,
    ]
    if classificato:
        story.extend(
            blocchi.cronoprogramma(cronoprogramma.stima(snapshot), styles, palette)
        )
    story.extend(
        blocchi.piano_pagamenti(
            preventivo_struttura.piano_pagamenti(
                snapshot, preventivo.get("totale_documento")
            ),
            styles,
            palette,
        )
    )
    if classificato:
        story.extend(
            blocchi.esclusioni(preventivo_struttura.esclusioni(snapshot), styles, palette)
        )
    if preventivo.get("note"):
        story.extend([
            Paragraph("Note specifiche", styles["section"]),
            Paragraph(_text(preventivo["note"]), styles["body"]),
        ])
    story.extend([
        Paragraph("Condizioni dell'offerta", styles["section"]),
        Paragraph(conditions, styles["small"]),
        Spacer(1, 8 * mm), KeepTogether(signatures),
    ])
    cover = _cover_decorator(
        ragione,
        numero,
        str(cliente),
        str(preventivo.get("cantiere_indirizzo") or "Intervento da definire"),
        _money(preventivo.get("totale_documento")),
        _date_it(preventivo.get("created_at")),
        primary,
    )
    decorator = _page_decorator(ragione, numero, stato, primary)
    doc.build(story, onFirstPage=cover, onLaterPages=decorator)
    return buffer.getvalue()
