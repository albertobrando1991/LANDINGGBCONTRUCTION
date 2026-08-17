from decimal import Decimal

import fitz
import pytest
from fastapi import HTTPException

from acca_pdf_parser import parse_acca_pdf


def _pdf(*pages: str) -> bytes:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        page.insert_textbox(fitz.Rect(36, 36, 560, 806), text, fontsize=9)
    result = document.tobytes()
    document.close()
    return result


def test_parses_complete_multpage_primus_computo():
    data = _pdf(
        """PriMus by ACCA software S.p.A.
Num.Ord.
TARIFFA
DESIGNAZIONE DEI LAVORI
1
Demolizione pavimento esistente
CAM24_R02.060.040.A
Totale
10,00
SOMMANO...
mq
10,00
12,50
125,00
2
Fornitura e posa porta interna
NP.02
descrizione che continua""",
        """PriMus by ACCA software S.p.A.
pag. 2
R I P O R T O
125,00
nella pagina successiva
2,00
SOMMANO... cadauno
2,00
300,00
600,00
T O T A L E   euro
725,00""",
    )

    result = parse_acca_pdf(data)

    assert result["n_voci"] == 2
    assert result["totale_pdf"] == Decimal("725.00")
    assert result["n_da_verificare"] == 0
    assert result["voci"][0]["um"] == "mq"
    assert result["voci"][1]["um"] == "cad"
    assert "pagina successiva" in result["voci"][1]["descrizione"]


def test_imports_partial_extraction_as_incomplete_draft():
    data = _pdf(
        """PriMus by ACCA software S.p.A.
1
Voce di prova
NP.01
SOMMANO... a corpo
1,00
100,00
100,00
T O T A L E   euro
200,00"""
    )

    result = parse_acca_pdf(data)

    assert result["n_voci"] == 1
    assert result["totale_pdf"] == Decimal("100.00")
    assert result["totale_documento_dichiarato"] == Decimal("200.00")
    assert result["scostamento_estrazione"] == Decimal("100.00")
    assert result["estrazione_incompleta"] is True


def test_rejects_non_primus_pdf():
    data = _pdf("Documento generico\nT O T A L E euro\n0,00")

    with pytest.raises(HTTPException) as error:
        parse_acca_pdf(data)

    assert error.value.status_code == 422
    assert "PriMus" in error.value.detail
