import fitz

from preventivo_pdf import genera_pdf_preventivo


def _sample(items=3):
    return {
        "numero": "PREV-2026-0042",
        "stato": "bozza",
        "created_at": "2026-08-08T10:00:00+00:00",
        "validita_giorni": 30,
        "cliente_nome": "Mario Rossi",
        "cliente_email": "mario@example.com",
        "cliente_telefono": "+39 333 1234567",
        "cliente_indirizzo": "Via Roma 10",
        "cliente_citta": "Napoli",
        "cantiere_indirizzo": "Via Toledo 100, Napoli",
        "totale_imponibile": 12500,
        "sconto_percentuale": 5,
        "iva_percentuale": 10,
        "totale_iva": 1187.50,
        "totale_documento": 13062.50,
        "snapshot_voci": [
            {
                "sub_categoria": f"GB.{index:03d}",
                "descrizione": "Fornitura e posa in opera di lavorazione completa a perfetta regola d'arte",
                "um": "mq",
                "qta": 10,
                "prezzo_unitario": 125,
                "totale": 1250,
            }
            for index in range(1, items + 1)
        ],
    }


def _tenant():
    return {
        "slug": "gbconstruction",
        "ragione_sociale": "G.B. Construction S.r.l.",
        "piva": "01234567890",
        "theme": {"primary": "#B8202E", "secondary": "#B8A16A"},
        "contatti": {
            "email": "info@gbconstruction.it",
            "telefono": "+39 081 0000000",
            "indirizzo": "Napoli (NA)",
        },
    }


def test_professional_quote_contains_brand_customer_and_totals():
    pdf = genera_pdf_preventivo(_sample(), _tenant())
    document = fitz.open(stream=pdf, filetype="pdf")
    text = "\n".join(page.get_text() for page in document)
    assert len(pdf) > 5000
    assert "G.B. Construction" in text
    assert "PROPOSTA" in text
    assert "ECONOMICA" in text
    assert "Mario Rossi" in text
    assert "PREV-2026-0042" in text
    assert "TOTALE OFFERTA" in text
    assert "PER ACCETTAZIONE" in text
    document.close()


def test_long_quote_repeats_table_header_and_numbers_pages():
    pdf = genera_pdf_preventivo(_sample(items=65), _tenant())
    document = fitz.open(stream=pdf, filetype="pdf")
    assert document.page_count >= 3
    pages_with_table = 0
    assert "PROPOSTA" in document[0].get_text()
    assert "INVESTIMENTO" in document[0].get_text()
    for index, page in enumerate(document, 1):
        text = page.get_text()
        pages_with_table += "DESCRIZIONE DELLE OPERE" in text
        if index > 1:
            assert f"Pagina {index}" in text
    assert pages_with_table >= 2
    document.close()
