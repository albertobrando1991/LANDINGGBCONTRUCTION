import fitz

from contract_workflow_service import payment_snapshot
from contratto_appalto_pdf import (
    genera_pdf_contratto,
    numero_contratto,
    risolvi_indirizzo_lavori,
)


def _preventivo():
    return {
        "numero": "PREV-2026-0042",
        "created_at": "2026-08-08T10:00:00+00:00",
        "cliente_nome": "Mario Rossi",
        "cliente_email": "mario@example.com",
        "cliente_telefono": "+39 333 1234567",
        "cliente_indirizzo": "Via Roma 10",
        "cliente_citta": "Napoli",
        "cliente_cf": "RSSMRA80A01F839X",
        "cantiere_indirizzo": "Via Toledo 100, Napoli",
        "totale_imponibile": 12500,
        "iva_percentuale": 10,
        "totale_documento": 13750,
        "snapshot_voci": [
            {
                "fase": "Demolizioni e rimozioni",
                "fase_ordine": 15,
                "area": "Cucina",
                "descrizione": "Demolizione pavimento esistente",
                "um": "mq",
                "qta": 20,
                "prezzo_unitario": 125,
                "totale": 2500,
            },
            {
                "fase": "Impianto elettrico e speciali",
                "fase_ordine": 45,
                "area": "Intero appartamento",
                "descrizione": "Rifacimento impianto elettrico",
                "um": "cad",
                "qta": 1,
                "prezzo_unitario": 10000,
                "totale": 10000,
            },
        ],
    }


def _tenant():
    return {
        "slug": "gbconstruction",
        "ragione_sociale": "GB Construction S.R.L.",
        "piva": "08912341215",
        "theme": {"primary": "#B8202E", "secondary": "#B8A16A"},
        "contatti": {
            "email": "info@gbconstruction.it",
            "telefono": "+39 389 658 4125",
            "indirizzo": "Via San Giacomo 35, Casalnuovo di Napoli",
        },
    }


def _text(pdf: bytes) -> tuple[fitz.Document, str]:
    document = fitz.open(stream=pdf, filetype="pdf")
    return document, "\n".join(page.get_text() for page in document)


def test_contract_number_tracks_quote_number():
    assert numero_contratto("PREV-2026-0042") == "CTR-2026-0042"
    assert numero_contratto("OFFERTA-9") == "CTR-OFFERTA-9"


def test_contract_prefers_linked_site_address():
    assert risolvi_indirizzo_lavori(_preventivo()) == "Via Toledo 100, Napoli"


def test_contract_uses_customer_address_before_site_is_opened():
    preventivo = {**_preventivo(), "cantiere_indirizzo": None}

    assert risolvi_indirizzo_lavori(preventivo) == "Via Roma 10, Napoli"


def test_contract_requires_at_least_a_customer_address():
    preventivo = {
        **_preventivo(),
        "cantiere_indirizzo": None,
        "cliente_indirizzo": None,
    }

    assert risolvi_indirizzo_lavori(preventivo) == ""


def test_contract_is_branded_compiled_and_signed_for_company():
    pdf = genera_pdf_contratto(_preventivo(), _tenant())
    document, text = _text(pdf)
    try:
        assert len(pdf) > 20_000
        assert document.page_count >= 5
        assert "CONTRATTO" in document[0].get_text()
        assert "D'APPALTO" in document[0].get_text()
        assert "Mario Rossi" in text
        assert "RSSMRA80A01F839X" in text
        assert "Via Toledo 100, Napoli" in text
        assert "ART. 13" in text
        assert "CONDIZIONI DI PAGAMENTO" in text
        assert "Alla firma del contratto" in text
        assert "ALLEGATO A" in text
        assert "Timbro e firma dell'Appaltatrice" in text
        assert document[-1].get_images(full=True)
    finally:
        document.close()


def test_contract_does_not_invent_missing_tax_identifier():
    preventivo = {**_preventivo(), "cliente_cf": None, "cliente_piva": None}
    document, text = _text(genera_pdf_contratto(preventivo, _tenant()))
    try:
        assert "C.F./P. IVA non indicato" in text
    finally:
        document.close()


def test_contract_payment_table_shows_taxable_vat_and_gross_amounts():
    rates = [
        {
            "riferimento": "Alla firma",
            "descrizione": "Acconto personalizzato",
            "percentuale": 30,
            "imponibile": 3750,
            "iva_percentuale": 10,
            "iva_importo": 375,
            "importo": 4125,
        },
        {
            "riferimento": "Alla consegna",
            "descrizione": "Saldo personalizzato",
            "percentuale": 70,
            "imponibile": 8750,
            "iva_percentuale": 10,
            "iva_importo": 875,
            "importo": 9625,
        },
    ]
    document, text = _text(
        genera_pdf_contratto(
            _preventivo(),
            _tenant(),
            piano_pagamenti_override=rates,
        )
    )
    try:
        assert "IMPONIBILE" in text
        assert "TOTALE IVA INCL." in text
        assert "Acconto personalizzato" in text
        assert "3.750,00" in text
        assert "375,00" in text
        assert "4.125,00" in text
    finally:
        document.close()


def test_contract_payment_table_shows_monthly_sal_and_final_balance():
    rates = payment_snapshot(
        "sal", _preventivo()["totale_documento"], mesi_lavorazione=5
    )["rate"]
    document, text = _text(
        genera_pdf_contratto(
            _preventivo(),
            _tenant(),
            piano_pagamenti_override=rates,
        )
    )
    try:
        assert "Mese 1 di 5" in text
        assert "accettazione" in text
        assert "preventivo" in text
        assert "Mese 5 di 5" in text
        assert "ultimazione" in text
        assert "Acconto iniziale" in text
        assert "SAL finale e saldo" in text
        assert text.count("18,8%") == 4
    finally:
        document.close()
