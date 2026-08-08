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


FASI_DEMO = (
    ("Demolizioni e rimozioni", 15),
    ("Impianto elettrico e speciali", 45),
    ("Pavimenti e rivestimenti", 70),
)


def _sample_a_fasi(items=6):
    """Snapshot classificato, con voci ripetute per verificare l'aggregazione."""
    voci = []
    for index in range(items):
        fase, ordine = FASI_DEMO[index % len(FASI_DEMO)]
        voci.append(
            {
                "fase": fase,
                "fase_ordine": ordine,
                "area": "Bagno" if index % 2 else "Cucina",
                "descrizione": f"Lavorazione tipo {index % len(FASI_DEMO)} a regola d'arte",
                "um": "mq",
                "qta": 10,
                "prezzo_unitario": 125,
                "totale": 1250,
            }
        )
    return {**_sample(items=1), "snapshot_voci": voci}


def _testo(pdf):
    document = fitz.open(stream=pdf, filetype="pdf")
    try:
        return "\n".join(page.get_text() for page in document)
    finally:
        document.close()


def test_quote_groups_items_by_fase_with_economic_overview():
    text = _testo(genera_pdf_preventivo(_sample_a_fasi(), _tenant()))

    assert "Quadro economico per fase di lavorazione" in text
    # Ordine cronologico di cantiere, non ordine di inserimento.
    assert text.index("DEMOLIZIONI E RIMOZIONI") < text.index("PAVIMENTI E RIVESTIMENTI")
    assert "IMPIANTO ELETTRICO E SPECIALI" in text
    assert "1.1" in text


def test_quote_merges_twin_items_and_lists_their_areas():
    text = _testo(genera_pdf_preventivo(_sample_a_fasi(), _tenant()))
    assert "2 posizioni" in text
    assert "Bagno" in text and "Cucina" in text


def test_quote_adds_payment_plan_and_exclusions():
    text = _testo(genera_pdf_preventivo(_sample_a_fasi(), _tenant()))

    assert "Piano dei pagamenti" in text
    assert "Alla firma del contratto" in text
    assert "Alla consegna dei lavori" in text
    assert "Prestazioni non comprese" in text
    # Le fasi presenti non possono comparire tra le esclusioni.
    assert "Fornitura e posa di pavimenti e rivestimenti" not in text
    assert "Massetti, sottofondi e isolamenti termo-acustici" in text


def test_quote_adds_indicative_schedule():
    text = _testo(genera_pdf_preventivo(_sample_a_fasi(), _tenant()))

    assert "Cronoprogramma indicativo" in text
    assert "giorni lavorativi" in text
    assert "AVANZAMENTO" in text
    # Il disclaimer va sempre stampato: la stima non e contrattuale.
    assert "contrattuale" in text


def test_synthetic_detail_hides_quantities_and_unit_prices():
    text = _testo(
        genera_pdf_preventivo(_sample_a_fasi(), _tenant(), dettaglio="sintetico")
    )

    assert "Quadro economico per fase di lavorazione" in text
    assert "DEMOLIZIONI E RIMOZIONI" in text
    assert "DESCRIZIONE DELLE OPERE" not in text


def test_unclassified_snapshot_falls_back_to_flat_table():
    text = _testo(genera_pdf_preventivo(_sample(), _tenant()))

    assert "Dettaglio economico delle lavorazioni" in text
    assert "Quadro economico per fase di lavorazione" not in text


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
    assert "Timbro e firma dell'Appaltatrice" in text
    assert document[-1].get_images(full=True)
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
