"""Rendering del documento SAL con allegato libretto."""

from datetime import date

import fitz

from sal_pdf import genera_pdf_sal


def _documento():
    righe = []
    misure = []
    for index in range(1, 18):
        righe.append(
            {
                "id": f"riga-{index}",
                "descrizione": (
                    "Demolizione controllata e trasporto del materiale di risulta "
                    f"settore operativo {index}"
                ),
                "um": "mq",
                "qta_periodo": 3.5 + index,
                "qta_progressiva": 8 + index,
                "qta_contrattuale": 20 if index > 2 else 5,
                "prezzo_unitario": 42.5,
                "importo_periodo": (3.5 + index) * 42.5,
                "in_eccedenza": index <= 2,
                "eccedenza_qta": 3 + index if index <= 2 else 0,
            }
        )
        misure.append(
            {
                "id": f"misura-{index}",
                "data_misura": date(2026, 8, min(index, 28)),
                "descrizione": f"Parete vano {index} <tecnico>",
                "computo_voce_descrizione": "Demolizione controllata",
                "computo_voce_um": "mq",
                "parti": 2,
                "lunghezza": 3.5,
                "larghezza": 2.7,
                "altezza": None,
                "qta": 18.9,
                "foto_paths": ["tenant/cantiere/foto.jpg"],
            }
        )
    return {
        "tenant": {
            "slug": "gbconstruction",
            "ragione_sociale": "GB Construction S.R.L.",
            "piva": "08912341215",
            "theme": {"primary": "#C41E3A", "secondary": "#D4AF37"},
            "contatti": {
                "email": "info@gbconstruction.it",
                "telefono": "+39 389 658 4125",
                "indirizzo": "Via San Giacomo 35, Casalnuovo di Napoli",
            },
        },
        "cantiere": {
            "cliente": "Condominio Residenza Porta Romana",
            "indirizzo": "Via delle Maestranze Specializzate 128, Milano",
            "capocantiere": "Mario Rossi",
        },
        "sal": {
            "numero": 2,
            "stato": "bozza",
            "periodo_da": date(2026, 8, 1),
            "periodo_a": date(2026, 8, 31),
            "totale_periodo": sum(row["importo_periodo"] for row in righe),
            "righe": righe,
        },
        "misure": misure,
    }


def test_pdf_sal_e_libretto_sono_leggibili_e_multipagina():
    pdf_bytes = genera_pdf_sal(_documento())

    assert pdf_bytes.startswith(b"%PDF")
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in pdf)

    assert len(pdf) >= 2
    assert "SAL 02" in text
    assert "Quadro economico del periodo" in text
    assert "Allegato A - Libretto delle misure" in text
    assert "info@gbconstruction.it" in text
    assert "Totale rilevazioni documentate: 17" in text
    assert "BOZZA" in text
    assert "<tecnico>" in text
