"""Blocchi ReportLab del preventivo: quadro economico, sezioni per fase, allegati.

Solo costruzione di flowable a partire da dati gia calcolati. Nessun accesso a
database, nessuna logica di prezzo.
"""
from __future__ import annotations

from html import escape
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

LARGHEZZA_UTILE = 172 * mm
COLONNE_VOCI = [11 * mm, 78 * mm, 12 * mm, 18 * mm, 25 * mm, 28 * mm]
LARGHEZZA_BARRA = 34 * mm
INTESTAZIONE_VOCI = ("N.", "DESCRIZIONE DELLE OPERE", "UM", "Q.TA", "PREZZO", "IMPORTO")


def testo(value: Any, fallback: str = "-") -> str:
    return escape(str(value or fallback))


def numero(value: Any, decimals: int = 2) -> str:
    raw = f"{float(value or 0):,.{decimals}f}"
    return raw.replace(",", "X").replace(".", ",").replace("X", ".")


def importo(value: Any) -> str:
    return "EUR " + numero(value)


def _barra(percentuale: float, primary: colors.Color, line: colors.Color) -> Table:
    """Barra di incidenza: due celle affiancate, larghezza proporzionale."""
    quota = max(0.0, min(100.0, float(percentuale or 0)))
    piena = max(LARGHEZZA_BARRA * quota / 100, 0.4 * mm)
    vuota = max(LARGHEZZA_BARRA - piena, 0.4 * mm)
    barra = Table([["", ""]], colWidths=[piena, vuota], rowHeights=[2.4 * mm])
    barra.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), primary),
                ("BACKGROUND", (1, 0), (1, 0), line),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return barra


def _riga_intestazione(styles: dict) -> list:
    return [Paragraph(voce, styles["table_head"]) for voce in INTESTAZIONE_VOCI]


def quadro_economico(gruppi: list[dict], styles: dict, palette: dict) -> list:
    """Una riga per fase con incidenza e subtotale: apre il documento."""
    righe = [
        [
            Paragraph("#", styles["table_head"]),
            Paragraph("FASE DI LAVORAZIONE", styles["table_head"]),
            Paragraph("LAVORAZIONI", styles["table_head"]),
            Paragraph("INCIDENZA", styles["table_head"]),
            Paragraph("%", styles["table_head"]),
            Paragraph("IMPORTO", styles["table_head"]),
        ]
    ]
    for indice, gruppo in enumerate(gruppi, 1):
        righe.append(
            [
                f"{indice:02d}",
                Paragraph(f"<b>{testo(gruppo['fase'])}</b>", styles["table"]),
                str(gruppo["n_voci"]),
                _barra(gruppo["incidenza"], palette["primary"], palette["line"]),
                f"{numero(gruppo['incidenza'], 1)}%",
                importo(gruppo["totale"]),
            ]
        )
    tabella = Table(
        righe,
        repeatRows=1,
        colWidths=[11 * mm, 62 * mm, 20 * mm, LARGHEZZA_BARRA + 4 * mm, 17 * mm, 28 * mm],
    )
    tabella.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), palette["graphite"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, palette["line"]),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, palette["soft"]]),
                ("TOPPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2 * mm),
                ("LEFTPADDING", (0, 0), (-1, -1), 1.7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1.7 * mm),
            ]
        )
    )
    return [
        Paragraph("Quadro economico per fase di lavorazione", styles["section"]),
        tabella,
    ]


def _intestazione_fase(indice: int, gruppo: dict, styles: dict, palette: dict) -> Table:
    barra = Table(
        [
            [
                Paragraph(f"{indice:02d}", styles["fase_numero"]),
                Paragraph(testo(gruppo["fase"]).upper(), styles["fase_titolo"]),
                Paragraph(importo(gruppo["totale"]), styles["fase_importo"]),
            ]
        ],
        colWidths=[13 * mm, 111 * mm, 48 * mm],
    )
    barra.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), palette["graphite"]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBEFORE", (0, 0), (0, 0), 2.2, palette["primary"]),
                ("TOPPADDING", (0, 0), (-1, -1), 2.4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4 * mm),
                ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
            ]
        )
    )
    return barra


def _descrizione_voce(voce: dict, styles: dict) -> Paragraph:
    corpo = testo(voce.get("descrizione"), "Voce senza descrizione")
    dettagli = []
    # Per le voci importate da ACCA qui vive il codice di tariffa: resta il
    # riferimento con cui il cliente ritrova la voce nel computo metrico.
    if voce.get("sub_categoria"):
        dettagli.append(str(voce["sub_categoria"]))
    posizioni = int(voce.get("n_posizioni") or 1)
    if posizioni > 1:
        aree = [str(area) for area in voce.get("aree") or []]
        etichetta = f"{posizioni} posizioni"
        if aree:
            etichetta = f"{etichetta}: {', '.join(aree)}"
        dettagli.append(etichetta)
    elif voce.get("area"):
        dettagli.append(str(voce["area"]))
    if dettagli:
        nota = escape(" · ".join(dettagli))
        corpo = f"{corpo}<br/><font size=6 color='#6A6E75'>{nota}</font>"
    return Paragraph(corpo, styles["table"])


def _stile_voci(palette: dict, intestazione_scura: bool) -> TableStyle:
    sfondo = palette["graphite"] if intestazione_scura else palette["soft"]
    inchiostro = colors.white if intestazione_scura else palette["graphite"]
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), sfondo),
            ("TEXTCOLOR", (0, 0), (-1, 0), inchiostro),
            ("ALIGN", (0, 1), (0, -1), "CENTER"),
            ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.25, palette["line"]),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAF9F7")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 1.7 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1.7 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
        ]
    )


def _riga_voce(etichetta: str, voce: dict, styles: dict) -> list:
    qta = float(voce.get("qta") or 0)
    prezzo = float(voce.get("prezzo_unitario") or 0)
    totale = float(voce.get("totale") or round(qta * prezzo, 2))
    return [
        etichetta,
        _descrizione_voce(voce, styles),
        testo(voce.get("um")),
        numero(qta, 3),
        importo(prezzo),
        importo(totale),
    ]


def sezione_fase(indice: int, gruppo: dict, styles: dict, palette: dict) -> list:
    """Intestazione della fase piu il dettaglio analitico delle sue voci."""
    righe = [_riga_intestazione(styles)]
    for posizione, voce in enumerate(gruppo["voci"], 1):
        righe.append(_riga_voce(f"{indice}.{posizione}", voce, styles))
    tabella = Table(righe, repeatRows=1, colWidths=COLONNE_VOCI)
    tabella.setStyle(_stile_voci(palette, intestazione_scura=False))
    return [
        Spacer(1, 4 * mm),
        _intestazione_fase(indice, gruppo, styles, palette),
        Spacer(1, 1.5 * mm),
        tabella,
    ]


def sezione_fase_sintetica(
    indice: int, gruppo: dict, styles: dict, palette: dict, *, max_caratteri: int = 110
) -> list:
    """Solo cosa comprende la fase, senza quantita ne prezzi unitari."""
    elenco = []
    for voce in gruppo["voci"]:
        descrizione = str(voce.get("descrizione") or "").strip()
        if len(descrizione) > max_caratteri:
            descrizione = f"{descrizione[:max_caratteri].rstrip()}..."
        elenco.append(Paragraph(f"- {escape(descrizione)}", styles["table"]))
    corpo = Table([[elenco]], colWidths=[LARGHEZZA_UTILE])
    corpo.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.4, palette["line"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
            ]
        )
    )
    return [
        Spacer(1, 4 * mm),
        KeepTogether(
            [
                _intestazione_fase(indice, gruppo, styles, palette),
                Spacer(1, 1.5 * mm),
                corpo,
            ]
        ),
    ]


def tabella_voci_piatta(voci: Iterable[dict], styles: dict, palette: dict) -> list:
    """Vecchio elenco numerato: usato quando nessuna voce ha una fase."""
    righe = [_riga_intestazione(styles)]
    for indice, voce in enumerate(voci, 1):
        righe.append(_riga_voce(str(indice), voce, styles))
    tabella = Table(righe, repeatRows=1, colWidths=COLONNE_VOCI)
    tabella.setStyle(_stile_voci(palette, intestazione_scura=True))
    return [Paragraph("Dettaglio economico delle lavorazioni", styles["section"]), tabella]


def piano_pagamenti(rate: list[dict], styles: dict, palette: dict) -> list:
    if not rate:
        return []
    righe = [
        [
            Paragraph("RATA", styles["table_head"]),
            Paragraph("RIFERIMENTO", styles["table_head"]),
            Paragraph("QUOTA", styles["table_head"]),
            Paragraph("IMPORTO", styles["table_head"]),
        ]
    ]
    for indice, rata in enumerate(rate, 1):
        righe.append(
            [
                f"{indice:02d}",
                Paragraph(
                    f"<b>{testo(rata['riferimento'])}</b><br/>"
                    f"<font size=6 color='#6A6E75'>{testo(rata['descrizione'])}</font>",
                    styles["table"],
                ),
                f"{numero(rata['percentuale'], 1)}%",
                importo(rata["importo"]),
            ]
        )
    tabella = Table(righe, repeatRows=1, colWidths=[18 * mm, 106 * mm, 20 * mm, 28 * mm])
    tabella.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), palette["graphite"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.25, palette["line"]),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, palette["soft"]]),
                ("LEFTPADDING", (0, 0), (-1, -1), 1.7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1.7 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
            ]
        )
    )
    return [
        Paragraph("Piano dei pagamenti", styles["section"]),
        tabella,
        Spacer(1, 2 * mm),
        Paragraph(
            "Le quote intermedie sono corrisposte a completamento verificato della "
            "fase indicata. Il piano puo essere rimodulato in sede contrattuale.",
            styles["small"],
        ),
    ]


LARGHEZZA_GANTT = 74 * mm


def _barra_gantt(
    inizio: int, giorni: int, totale: int, primary: colors.Color, line: colors.Color
) -> Table:
    """Segmento posizionato sull'asse dei giorni lavorativi."""
    scala = LARGHEZZA_GANTT / totale if totale else 0
    prima = max(inizio * scala, 0.01 * mm)
    barra = max(giorni * scala, 0.6 * mm)
    dopo = max(LARGHEZZA_GANTT - prima - barra, 0.01 * mm)
    tabella = Table(
        [["", "", ""]], colWidths=[prima, barra, dopo], rowHeights=[2.6 * mm]
    )
    tabella.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.white),
                ("BACKGROUND", (1, 0), (1, 0), primary),
                ("BACKGROUND", (2, 0), (2, 0), line),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return tabella


def cronoprogramma(piano: dict, styles: dict, palette: dict) -> list:
    if not piano or not piano.get("blocchi") or not piano.get("giorni_totali"):
        return []
    totale = int(piano["giorni_totali"])
    righe = [
        [
            Paragraph("FASE", styles["table_head"]),
            Paragraph("GG", styles["table_head"]),
            Paragraph("DA / A", styles["table_head"]),
            Paragraph("AVANZAMENTO", styles["table_head"]),
        ]
    ]
    for blocco in piano["blocchi"]:
        if blocco["continuativa"]:
            periodo, giorni = "in continuo", "-"
        else:
            periodo = f"gg {blocco['inizio'] + 1} - {blocco['fine']}"
            giorni = str(blocco["giorni"])
        etichetta = testo(blocco["fase"])
        if blocco["parallela"] and not blocco["continuativa"]:
            etichetta = f"{etichetta} <font size=6 color='#6A6E75'>(in parallelo)</font>"
        righe.append(
            [
                Paragraph(etichetta, styles["table"]),
                giorni,
                periodo,
                _barra_gantt(
                    blocco["inizio"],
                    blocco["giorni"],
                    totale,
                    palette["primary"],
                    palette["line"],
                ),
            ]
        )
    tabella = Table(
        righe,
        repeatRows=1,
        colWidths=[62 * mm, 10 * mm, 22 * mm, LARGHEZZA_GANTT + 4 * mm],
    )
    tabella.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), palette["graphite"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (1, 1), (2, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, palette["line"]),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, palette["soft"]]),
                ("LEFTPADDING", (0, 0), (-1, -1), 1.7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1.7 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
            ]
        )
    )
    return [
        Paragraph("Cronoprogramma indicativo", styles["section"]),
        tabella,
        Spacer(1, 2 * mm),
        Paragraph(
            f"Durata stimata complessiva: <b>{totale} giorni lavorativi</b> "
            f"(circa {numero(piano['settimane'], 1)} settimane / "
            f"{numero(piano.get('mesi'), 1)} mesi), al netto di sospensioni. "
            "La stima considera superficie, complessita delle fasi, "
            "sovrapposizione controllata delle squadre e tempi tecnici di "
            "maturazione. Il programma definitivo e la data di avvio vengono "
            "fissati nel cronoprogramma allegato al contratto.",
            styles["small"],
        ),
    ]


def esclusioni(voci_escluse: list[str], styles: dict, palette: dict) -> list:
    if not voci_escluse:
        return []
    elenco = [Paragraph(f"- {escape(riga)}", styles["small"]) for riga in voci_escluse]
    blocco = Table([[elenco]], colWidths=[LARGHEZZA_UTILE])
    blocco.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), palette["soft"]),
                ("BOX", (0, 0), (-1, -1), 0.4, palette["line"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
            ]
        )
    )
    return [
        Paragraph("Prestazioni non comprese", styles["section"]),
        Paragraph(
            "Quanto segue non rientra nell'offerta e, se richiesto, sara oggetto di "
            "integrazione concordata prima dell'esecuzione.",
            styles["small"],
        ),
        Spacer(1, 2 * mm),
        blocco,
    ]
