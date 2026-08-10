"""Contratto d'appalto dinamico, derivato dal modello GB fornito dal cliente."""

from __future__ import annotations

import io
import json
from datetime import date, datetime
from html import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
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
from pdf_brand_assets import COVER_PATH, LOGO_PATH, firma_appaltatrice, is_gb_tenant
import preventivo_struttura
from preventivo_pdf_blocchi import importo


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


def _date_it(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime(
            "%d/%m/%Y"
        )
    except (TypeError, ValueError):
        return str(value or "-")


def _safe(value: Any, fallback: str = "non indicato") -> str:
    return escape(str(value).strip()) if value not in (None, "") else fallback


def numero_contratto(numero_preventivo: Any) -> str:
    numero = str(numero_preventivo or "BOZZA").strip()
    if numero.upper().startswith("PREV"):
        return f"CTR{numero[4:]}"
    return f"CTR-{numero}"


def risolvi_indirizzo_lavori(preventivo: dict) -> str:
    """Usa il cantiere; prima della sua apertura ripiega sull'indirizzo cliente."""
    cantiere = str(preventivo.get("cantiere_indirizzo") or "").strip()
    if cantiere:
        return cantiere

    indirizzo = str(preventivo.get("cliente_indirizzo") or "").strip()
    if not indirizzo:
        return ""
    citta = str(preventivo.get("cliente_citta") or "").strip()
    if citta and citta.casefold() not in indirizzo.casefold():
        return f"{indirizzo}, {citta}"
    return indirizzo


def _color(value: Any, fallback: str) -> colors.Color:
    try:
        return colors.HexColor(str(value or fallback).strip())
    except (TypeError, ValueError):
        return colors.HexColor(fallback)


def _cover(
    *,
    ragione: str,
    numero: str,
    cliente: str,
    intervento: str,
    data_contratto: str,
    primary: colors.Color,
):
    def draw(canvas, _doc):
        width, height = A4
        canvas.saveState()
        canvas.setTitle(f"Contratto d'appalto {numero} - {ragione}")
        canvas.setAuthor(ragione)
        canvas.setSubject("Contratto privato d'appalto per lavori edili")
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
        canvas.setFillColor(colors.Color(0.035, 0.035, 0.045, alpha=0.56))
        canvas.rect(0, 0, width, height, stroke=0, fill=1)
        canvas.setFillColor(colors.Color(0.035, 0.035, 0.045, alpha=0.90))
        canvas.rect(0, 0, width, 112 * mm, stroke=0, fill=1)
        canvas.setFillColor(primary)
        canvas.rect(0, 0, 11 * mm, height, stroke=0, fill=1)
        canvas.rect(11 * mm, 108 * mm, width - 11 * mm, 4 * mm, stroke=0, fill=1)
        if LOGO_PATH.exists():
            canvas.drawImage(
                str(LOGO_PATH),
                22 * mm,
                height - 53 * mm,
                width=37 * mm,
                height=31 * mm,
                mask="auto",
            )
        canvas.setFillColor(colors.HexColor("#F5F3EF"))
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(64 * mm, height - 32 * mm, ragione.upper())
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#C8C5BF"))
        canvas.drawString(
            64 * mm,
            height - 38 * mm,
            "COSTRUIAMO SPAZI. TRASFORMIAMO IL MODO DI VIVERLI.",
        )
        canvas.setFillColor(colors.HexColor("#F5F3EF"))
        canvas.setFont("Helvetica-Bold", 32)
        canvas.drawString(22 * mm, 84 * mm, "CONTRATTO")
        canvas.drawString(22 * mm, 70 * mm, "D'APPALTO")
        canvas.setFillColor(primary)
        canvas.rect(22 * mm, 62 * mm, 31 * mm, 2.2 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#F5F3EF"))
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(22 * mm, 52 * mm, f"{numero}  /  {data_contratto}")
        canvas.setFillColor(colors.HexColor("#A9A6A0"))
        canvas.setFont("Helvetica-Bold", 6.5)
        canvas.drawString(112 * mm, 94 * mm, "COMMITTENTE")
        canvas.setFillColor(colors.HexColor("#F5F3EF"))
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(112 * mm, 88 * mm, cliente[:42])
        canvas.setFillColor(colors.HexColor("#A9A6A0"))
        canvas.setFont("Helvetica-Bold", 6.5)
        canvas.drawString(112 * mm, 68 * mm, "INTERVENTO")
        canvas.setFillColor(colors.HexColor("#F5F3EF"))
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(112 * mm, 62 * mm, intervento[:58])
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor("#A9A6A0"))
        canvas.drawString(22 * mm, 15 * mm, "DOCUMENTO RISERVATO  /  GB CONSTRUCTION")
        canvas.restoreState()

    return draw


def _footer(ragione: str, numero: str, primary: colors.Color):
    def draw(canvas, _doc):
        canvas.saveState()
        canvas.setStrokeColor(primary)
        canvas.setLineWidth(0.7)
        canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
        canvas.setFillColor(colors.HexColor("#62666D"))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(18 * mm, 8.5 * mm, f"{ragione} - Contratto {numero}")
        canvas.drawRightString(
            A4[0] - 18 * mm, 8.5 * mm, f"Pagina {canvas.getPageNumber()}"
        )
        canvas.restoreState()

    return draw


def genera_pdf_contratto(
    preventivo: dict,
    tenant: dict,
    *,
    sezioni: list[dict] | None = None,
    piano_pagamenti_override: list[dict] | None = None,
) -> bytes:
    """Genera il contratto già compilato e firmato dall'Appaltatrice GB."""
    theme = _dict(tenant.get("theme"))
    contatti = _dict(tenant.get("contatti"))
    primary = _color(theme.get("primary"), "#B8202E")
    secondary = _color(theme.get("secondary"), "#B8A16A")
    graphite = colors.HexColor("#202226")
    soft = colors.HexColor("#F3F1ED")
    line = colors.HexColor("#D8D4CD")
    ragione = str(tenant.get("ragione_sociale") or "GB Construction S.r.l.")
    numero = numero_contratto(preventivo.get("numero"))
    data_contratto = _date_it(preventivo.get("data_contratto") or date.today())
    cliente = str(preventivo.get("cliente_nome") or "Cliente non associato")
    cantiere = str(preventivo.get("cantiere_indirizzo") or "Sede da definire")
    snapshot = preventivo.get("snapshot_voci") or []
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)
    durata = cronoprogramma.stima(
        snapshot,
        superficie_mq=preventivo.get("superficie_mq"),
        durate_fasi=preventivo.get("durate_fasi") or {},
    )
    giorni_lavorativi = int(durata.get("giorni_totali") or 0)
    piano_pagamenti = (
        piano_pagamenti_override
        if piano_pagamenti_override is not None
        else preventivo_struttura.piano_pagamenti(
            snapshot, preventivo.get("totale_documento")
        )
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=f"Contratto d'appalto {numero} - {ragione}",
        author=ragione,
    )
    base = getSampleStyleSheet()
    styles = {
        "brand": ParagraphStyle(
            "ContractBrand",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            textColor=graphite,
        ),
        "title": ParagraphStyle(
            "ContractTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=25,
            alignment=TA_RIGHT,
            textColor=primary,
        ),
        "lead": ParagraphStyle(
            "ContractLead",
            parent=base["Normal"],
            fontSize=9,
            leading=12.5,
            textColor=graphite,
        ),
        "body": ParagraphStyle(
            "ContractBody",
            parent=base["Normal"],
            fontSize=8.2,
            leading=11.2,
            alignment=TA_JUSTIFY,
            textColor=graphite,
            spaceAfter=1.4 * mm,
        ),
        "article": ParagraphStyle(
            "ContractArticle",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.2,
            leading=13,
            textColor=primary,
            spaceBefore=4 * mm,
            spaceAfter=1.8 * mm,
        ),
        "small": ParagraphStyle(
            "ContractSmall",
            parent=base["Normal"],
            fontSize=7.2,
            leading=9.2,
            textColor=colors.HexColor("#5D6168"),
        ),
        "table": ParagraphStyle(
            "ContractTable",
            parent=base["Normal"],
            fontSize=7.4,
            leading=9.2,
            textColor=graphite,
        ),
        "table_head": ParagraphStyle(
            "ContractTableHead",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8.5,
            alignment=TA_CENTER,
            textColor=colors.white,
        ),
    }

    logo = None
    if is_gb_tenant(tenant) and LOGO_PATH.exists():
        logo = Image(str(LOGO_PATH), width=29 * mm, height=24.5 * mm)
    company = [Paragraph(_safe(ragione), styles["brand"])]
    if tenant.get("piva"):
        company.append(
            Paragraph(f"P. IVA {_safe(tenant.get('piva'))}", styles["small"])
        )
    identity = [logo, company] if logo else [company]
    identity_table = Table(
        [identity], colWidths=[34 * mm, 79 * mm] if logo else [113 * mm]
    )
    identity_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    title_block = [
        Paragraph("CONTRATTO D'APPALTO", styles["title"]),
        Paragraph(f"N. <b>{_safe(numero)}</b>", styles["small"]),
        Paragraph(f"Data {data_contratto}", styles["small"]),
    ]
    header = Table([[identity_table, title_block]], colWidths=[115 * mm, 57 * mm])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, primary),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    sede_impresa = (
        contatti.get("indirizzo") or "Via San Giacomo 35, Casalnuovo di Napoli (NA)"
    )
    pec_impresa = contatti.get("pec") or "gbconstruction@pec.it"
    telefono_impresa = contatti.get("telefono") or contatti.get("whatsapp")
    identificativo_cliente = (
        preventivo.get("cliente_cf") or preventivo.get("cliente_piva") or "non indicato"
    )
    tipo_identificativo = "C.F./P. IVA"
    appaltatrice = (
        f"<b>{_safe(ragione)}</b>, con sede in {_safe(sede_impresa)}, "
        f"P. IVA {_safe(tenant.get('piva'))}, PEC {_safe(pec_impresa)}, "
        "in persona del legale rappresentante Giovanni Brancale, di seguito "
        "<b>“Appaltatrice”</b>."
    )
    committente = (
        f"<b>{_safe(cliente)}</b>, residente/con sede in "
        f"{_safe(preventivo.get('cliente_indirizzo') or preventivo.get('cliente_citta'))}, "
        f"{tipo_identificativo} {_safe(identificativo_cliente)}, di seguito "
        "<b>“Committente”</b>."
    )

    articles: list[tuple[str, list[str]]] = [
        (
            "ART. 1 — DICHIARAZIONI DELL'IMPRESA APPALTATRICE",
            [
                "L'Appaltatrice dichiara di avere esaminato le opere da realizzare, di averne valutato quantità, condizioni e modalità esecutive e di disporre dell'organizzazione, delle maestranze e delle attrezzature necessarie alla loro completa esecuzione.",
                "L'Appaltatrice assume la gestione a proprio rischio sotto il profilo economico, organizzativo, tecnico e di legge e si obbliga a eseguire le opere con cura e diligenza, a perfetta regola d'arte e in conformità agli elaborati approvati e alle esigenze della Committenza.",
                "Restano a carico dell'Appaltatrice la pulizia delle aree di lavoro, l'organizzazione dei mezzi necessari e la consegna delle certificazioni dei materiali e della documentazione prevista da leggi, norme e regolamenti vigenti. Eventuali indicazioni tecniche mancanti saranno tempestivamente richieste alla Direzione Lavori.",
            ],
        ),
        (
            "ART. 2 — CESSIONE, SUBAPPALTO E RISOLUZIONE",
            [
                "È vietata la cessione del presente contratto. Il subappalto è ammesso nel rispetto della legge e previo consenso scritto della Committenza; l'Appaltatrice resta in ogni caso pienamente responsabile verso la Committenza delle opere e forniture subappaltate.",
                "La presenza di manodopera irregolare, il persistente mancato rispetto delle norme di sicurezza dopo contestazione scritta o il reiterato mancato rispetto del programma lavori costituiscono motivo di risoluzione, fermo il diritto della Committenza alla verifica dello stato di consistenza delle opere eseguite.",
            ],
        ),
        (
            "ART. 3 — OSSERVANZA DI LEGGI E REGOLAMENTI",
            [
                "Le opere sono soggette alla piena osservanza delle leggi, dei regolamenti e delle prescrizioni vigenti in materia edilizia, sicurezza, qualità dei materiali, esecuzione, misurazione, contabilità e collaudo dei lavori, nonché delle disposizioni dell'autorità competente per il luogo del cantiere.",
            ],
        ),
        (
            "ART. 4 — TIPOLOGIA E OGGETTO DELL'APPALTO",
            [
                f"L'appalto riguarda le lavorazioni descritte nel preventivo {_safe(preventivo.get('numero'))} e nel computo metrico ad esso collegato, relativi all'intervento presso <b>{_safe(cantiere)}</b>.",
                f"Il corrispettivo netto è pari a <b>{importo(preventivo.get('totale_imponibile'))}</b>, oltre IVA al {_safe(preventivo.get('iva_percentuale'), '0')}%, per un totale contrattuale di <b>{importo(preventivo.get('totale_documento'))}</b>. I prezzi compensano materiali e forniture se previsti, trasporti, scarichi, sfridi, noli, attrezzature, manodopera e ogni onere espressamente compreso nel computo.",
            ],
        ),
        (
            "ART. 5 — VARIAZIONI AL PROGETTO",
            [
                "La Committenza può richiedere variazioni o commissionare soltanto parte delle opere. Ogni variante, lavorazione extra o modifica quantitativa dovrà essere preventivamente descritta, valorizzata e approvata per iscritto prima dell'esecuzione, con conseguente aggiornamento di importi e tempi.",
            ],
        ),
        (
            "ART. 6 — NUOVI PREZZI",
            [
                "Per categorie di opere non previste sarà concordato preventivamente un nuovo prezzo, ricavato ove possibile dalle voci già presenti oppure dal prezzario ufficiale regionale vigente alla data dell'offerta. I nuovi prezzi si intendono comprensivi di spese generali e utile d'impresa.",
            ],
        ),
        (
            "ART. 7 — OPERE IN ECONOMIA",
            [
                "Le prestazioni in economia richieste dalla Committenza saranno preventivamente autorizzate e annotate con descrizione, quantità di manodopera, materiali e noli. La valorizzazione farà riferimento agli accordi scritti tra le parti o, in mancanza, al prezzario ufficiale vigente.",
            ],
        ),
        (
            "ART. 8 — INVARIABILITÀ DEI PREZZI",
            [
                "I prezzi concordati restano fissi per le lavorazioni e quantità indicate. Sono esclusi dall'invariabilità le varianti richieste, gli imprevisti non conoscibili con l'ordinaria diligenza e le quantità eccedenti, che saranno oggetto di preventiva contabilizzazione e approvazione.",
            ],
        ),
        (
            "ART. 9 — CONSEGNA E PROGRAMMA DEI LAVORI",
            [
                "L'avvio avverrà dopo la disponibilità del cantiere, il rilascio degli eventuali titoli abilitativi e la sottoscrizione del verbale di consegna. L'Appaltatrice inizierà le attività entro sette giorni dalla comunicazione di disponibilità, salvo diverso accordo scritto.",
            ],
        ),
        (
            "ART. 10 — TERMINE E ULTIMAZIONE",
            [
                (
                    f"La durata tecnica stimata è di <b>{giorni_lavorativi} giorni lavorativi</b> "
                    "dall'effettivo avvio del cantiere."
                    if giorni_lavorativi
                    else "La durata sarà definita nel programma lavori allegato prima dell'avvio del cantiere."
                ),
                "Il termine è sospeso o prorogato per cause di forza maggiore, condizioni meteo incompatibili, indisponibilità dei locali, ritardi autorizzativi, varianti, lavorazioni extra, ritardi della Committenza o altre cause non imputabili all'Appaltatrice.",
            ],
        ),
        (
            "ART. 11 — DIREZIONE LAVORI",
            [
                "I lavori saranno coordinati con la Direzione Lavori nominata dalla Committenza. Per le attività affidate alla struttura GB, il referente tecnico indicato nel modello è il Geom. Giuseppe Brancale, iscritto al Collegio dei Geometri di Napoli al n. 7533, salvo diversa nomina scritta.",
            ],
        ),
        (
            "ART. 12 — MATERIALI, ELABORATI E ATTREZZATURE",
            [
                "Materiali e attrezzature dovranno essere idonei e di buona qualità. L'approvazione della Committenza o della Direzione Lavori non esonera l'Appaltatrice dalle responsabilità relative alla qualità, alla posa e alla conformità delle forniture agli elaborati approvati.",
            ],
        ),
        (
            "ART. 13 — CONDIZIONI DI PAGAMENTO",
            [
                f"Il corrispettivo complessivo di <b>{importo(preventivo.get('totale_documento'))}</b>, IVA inclusa, sarà pagato secondo il piano riportato di seguito e coerente con le fasi del preventivo. Le lavorazioni extra e quelle in economia saranno fatturate e pagate secondo gli accordi scritti che le autorizzano.",
            ],
        ),
        (
            "ART. 14 — CAPITOLATO E ALLEGATI",
            [
                f"Le opere comprese sono quelle descritte nel preventivo {_safe(preventivo.get('numero'))} e nel relativo computo metrico, che costituiscono parte integrante del presente contratto. In caso di contrasto, prevalgono gli accordi successivi sottoscritti da entrambe le parti.",
            ],
        ),
        (
            "ART. 15 — ASSICURAZIONI SOCIALI, PREVIDENZIALI E RESPONSABILITÀ",
            [
                "L'Appaltatrice garantisce la regolarità del personale impiegato e la copertura assicurativa prevista dalla legge, trasmettendo prima dell'inizio dei lavori il DURC e il Piano Operativo di Sicurezza quando dovuti.",
                "L'Appaltatrice risponde dei danni imputabili all'esecuzione delle proprie opere e si impegna a mantenere adeguata copertura di responsabilità civile verso terzi. Restano ferme le responsabilità previste dal Codice Civile per difformità, vizi e gravi difetti.",
            ],
        ),
        (
            "ART. 16 — SICUREZZA",
            [
                "L'Appaltatrice dichiara di conoscere e osservare il D.Lgs. 81/2008 e le ulteriori disposizioni applicabili, nonché le prescrizioni del Piano di Sicurezza e Coordinamento quando previsto. La Committenza assicura l'accessibilità del cantiere e comunica i rischi specifici di propria conoscenza.",
            ],
        ),
        (
            "ART. 17 — GARANZIE PER DIFETTI E VIZI",
            [
                "Al termine dei lavori l'Appaltatrice garantisce le opere eseguite per cinque anni, senza pregiudizio delle garanzie inderogabili di legge. I vizi o le difformità imputabili all'Appaltatrice, tempestivamente denunciati, saranno verificati e rimossi entro tempi compatibili con natura e urgenza dell'intervento.",
            ],
        ),
        (
            "ART. 18 — CLAUSOLA RISOLUTIVA ESPRESSA",
            [
                "Ai sensi dell'art. 1456 c.c., il grave inadempimento degli obblighi previsti agli articoli 2, 9, 10, 13, 15, 16 e 17 può determinare la risoluzione di diritto dal ricevimento della comunicazione scritta, anche a mezzo PEC, con cui la parte adempiente dichiara di volersi avvalere della presente clausola.",
            ],
        ),
        (
            "ART. 19 — DISPOSIZIONI FINALI E REGISTRAZIONE",
            [
                "Per quanto non previsto si applicano il Codice Civile e la normativa vigente in materia di appalto. La scrittura sarà registrata in caso d'uso; imposte, tasse e interessi dovuti per fatto imputabile a una parte saranno a carico di quest'ultima, nei limiti consentiti dalla legge.",
            ],
        ),
        (
            "ART. 20 — MANCATO PAGAMENTO E SOSPENSIONE",
            [
                "In caso di ritardo superiore a quindici giorni nel pagamento di una scadenza, decorreranno gli interessi di mora nella misura del tasso legale aumentato di cinque punti percentuali, nei limiti di legge. Decorso inutilmente il termine, l'Appaltatrice potrà sospendere i lavori previa comunicazione scritta a mezzo PEC, fermo il diritto al risarcimento del danno documentato.",
            ],
        ),
        (
            "ART. 21 — VERBALI DI CONSEGNA E FINE LAVORI",
            [
                "La data di avvio sarà formalizzata mediante verbale di consegna del cantiere. Al termine sarà redatto verbale di ultimazione che attesti la conclusione delle opere, lo stato dell'intervento, le eventuali riserve e la documentazione consegnata.",
            ],
        ),
    ]

    if sezioni is not None:
        articles = [
            (
                str(sezione.get("titolo") or "SEZIONE").strip(),
                [str(sezione.get("testo") or "").strip()],
            )
            for sezione in sezioni
            if str(sezione.get("titolo") or "").strip()
            and str(sezione.get("testo") or "").strip()
        ]

    story: list = [Spacer(1, 252 * mm), PageBreak(), header, Spacer(1, 5 * mm)]
    story.extend(
        [
            Paragraph("CON IL PRESENTE CONTRATTO PRIVATO", styles["article"]),
            Paragraph(appaltatrice, styles["lead"]),
            Spacer(1, 2 * mm),
            Paragraph(committente, styles["lead"]),
            Spacer(1, 3 * mm),
            Paragraph("Le parti convengono e stipulano quanto segue.", styles["lead"]),
        ]
    )
    for title, paragraphs in articles:
        story.append(Paragraph(title, styles["article"]))
        story.extend(Paragraph(text, styles["body"]) for text in paragraphs)
        if title.startswith("ART. 13") and piano_pagamenti:
            payment_rows = [
                [
                    Paragraph("SCADENZA", styles["table_head"]),
                    Paragraph("DESCRIZIONE", styles["table_head"]),
                    Paragraph("QUOTA", styles["table_head"]),
                    Paragraph("IMPORTO", styles["table_head"]),
                ]
            ]
            for rata in piano_pagamenti:
                payment_rows.append(
                    [
                        Paragraph(_safe(rata.get("riferimento")), styles["table"]),
                        Paragraph(_safe(rata.get("descrizione")), styles["table"]),
                        f"{float(rata.get('percentuale') or 0):.1f}%".replace(".", ","),
                        importo(rata.get("importo")),
                    ]
                )
            payments = Table(
                payment_rows,
                repeatRows=1,
                colWidths=[54 * mm, 64 * mm, 18 * mm, 36 * mm],
            )
            payments.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), primary),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.35, line),
                        ("BACKGROUND", (0, 1), (-1, -1), soft),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                        ("FONTNAME", (3, 1), (3, -1), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 1), (-1, -1), 7.3),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2.3 * mm),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2.3 * mm),
                        ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
                    ]
                )
            )
            story.extend([Spacer(1, 2 * mm), payments])

    gruppi = fasi_lavorazione.raggruppa_per_fase(snapshot)
    if gruppi:
        story.extend(
            [
                PageBreak(),
                header,
                Spacer(1, 5 * mm),
                Paragraph("ALLEGATO A — QUADRO DELLE OPERE", styles["article"]),
                Paragraph(
                    "Riepilogo economico delle fasi incluse. Il dettaglio analitico resta quello del preventivo e del computo metrico collegati.",
                    styles["body"],
                ),
            ]
        )
        work_rows = [
            [
                Paragraph("#", styles["table_head"]),
                Paragraph("FASE DI LAVORAZIONE", styles["table_head"]),
                Paragraph("VOCI", styles["table_head"]),
                Paragraph("IMPORTO", styles["table_head"]),
            ]
        ]
        for index, gruppo in enumerate(gruppi, 1):
            work_rows.append(
                [
                    f"{index:02d}",
                    Paragraph(_safe(gruppo.get("fase")), styles["table"]),
                    str(gruppo.get("n_voci") or len(gruppo.get("voci") or [])),
                    importo(gruppo.get("totale")),
                ]
            )
        works = Table(
            work_rows,
            repeatRows=1,
            colWidths=[13 * mm, 105 * mm, 18 * mm, 36 * mm],
        )
        works.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), graphite),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.35, line),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, soft]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 1), (0, -1), "CENTER"),
                    ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                    ("FONTNAME", (3, 1), (3, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 1), (-1, -1), 7.5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ]
            )
        )
        story.append(works)

    firma = firma_appaltatrice(tenant)
    firma_impresa = (
        [
            Paragraph(f"Data {data_contratto}", styles["small"]),
            firma,
            Paragraph("Timbro e firma dell'Appaltatrice", styles["small"]),
        ]
        if firma
        else [
            Paragraph("Data ____________________", styles["small"]),
            Spacer(1, 12 * mm),
            Paragraph("Firma __________________________", styles["small"]),
        ]
    )
    signature_table = Table(
        [
            [
                Paragraph("IL COMMITTENTE", styles["table_head"]),
                Paragraph("L'APPALTATRICE", styles["table_head"]),
            ],
            [
                [
                    Paragraph("Data ____________________", styles["small"]),
                    Spacer(1, 15 * mm),
                    Paragraph("Firma __________________________", styles["small"]),
                ],
                firma_impresa,
            ],
        ],
        colWidths=[86 * mm, 86 * mm],
    )
    signature_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), primary),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.5, line),
                ("LINEBEFORE", (1, 0), (1, -1), 0.5, line),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("TOPPADDING", (0, 0), (-1, 0), 2.5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2.5 * mm),
                ("TOPPADDING", (0, 1), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4 * mm),
            ]
        )
    )
    story.extend(
        [
            Spacer(1, 7 * mm),
            Paragraph(
                "Le parti dichiarano di aver letto e approvato il presente contratto e i suoi allegati.",
                styles["body"],
            ),
            Paragraph(
                "Ai sensi e per gli effetti degli artt. 1341 e 1342 c.c., il Committente approva specificamente gli articoli 2, 5, 8, 9, 10, 13, 15, 17, 18, 19 e 20.",
                styles["body"],
            ),
            Spacer(1, 3 * mm),
            KeepTogether(signature_table),
            Spacer(1, 2 * mm),
            Paragraph(
                f"Contatti Appaltatrice: {_safe(telefono_impresa)} · PEC {_safe(pec_impresa)}",
                styles["small"],
            ),
        ]
    )

    doc.build(
        story,
        onFirstPage=_cover(
            ragione=ragione,
            numero=numero,
            cliente=cliente,
            intervento=cantiere,
            data_contratto=data_contratto,
            primary=primary,
        ),
        onLaterPages=_footer(ragione, numero, primary),
    )
    return buffer.getvalue()
