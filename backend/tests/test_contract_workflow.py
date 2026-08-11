from decimal import Decimal

import pytest
from fastapi import HTTPException

from contract_workflow_service import (
    contract_payment_snapshot,
    default_sections,
    payment_article_text,
    payment_snapshot,
    sections_with_payment_article,
    validate_sections,
)


def test_tre_modalita_generano_rate_che_sommano_al_totale():
    for tipo in ("sal", "scaglionato_fisso", "due_tranche"):
        snapshot = payment_snapshot(tipo, Decimal("12345.67"))
        assert round(sum(row["importo"] for row in snapshot["rate"]), 2) == 12345.67
        assert snapshot["tipo"] == tipo
        assert snapshot["condizioni_generali"]


def test_scaglionato_fisso_contiene_otto_rate_di_saldo():
    snapshot = payment_snapshot("scaglionato_fisso", 10000)
    deferred = [row for row in snapshot["rate"] if "Mese" in row["riferimento"]]
    assert len(deferred) == 8
    assert round(sum(row["importo"] for row in deferred), 2) == 2500


def test_editor_parte_da_sezioni_complete_e_accetta_nuove_parti():
    sections = default_sections(
        {
            "numero": "PREV-2026-001",
            "totale_documento": 10000,
            "cantiere_indirizzo": "Via Roma 1",
        }
    )
    assert len(sections) == 21
    sections.append(
        {"titolo": "ART. 22 — PATTO AGGIUNTIVO", "testo": "Testo concordato."}
    )
    assert validate_sections(sections)[-1]["titolo"].startswith("ART. 22")


def test_editor_rifiuta_sezioni_vuote():
    with pytest.raises(HTTPException) as exc:
        validate_sections([{"titolo": "ART. 1", "testo": ""}])
    assert exc.value.status_code == 422


def test_dettaglio_contratto_ripartisce_imponibile_iva_e_totale():
    preventivo = {
        "totale_imponibile": Decimal("10000.00"),
        "iva_percentuale": Decimal("10.00"),
        "totale_documento": Decimal("11000.00"),
    }
    snapshot = contract_payment_snapshot(
        "due_tranche",
        preventivo,
        {
            "tipo": "due_tranche",
            "rate": [
                {
                    "riferimento": "Alla firma",
                    "descrizione": "Acconto",
                    "importo": "3300.00",
                },
                {
                    "riferimento": "Alla consegna",
                    "descrizione": "Saldo",
                    "importo": "7700.00",
                },
            ],
        },
    )

    assert sum(row["importo"] for row in snapshot["rate"]) == 11000
    assert sum(row["imponibile"] for row in snapshot["rate"]) == 10000
    assert sum(row["iva_importo"] for row in snapshot["rate"]) == 1000
    assert snapshot["rate"][0]["iva_percentuale"] == 10
    assert "imponibile € 3.000,00" in payment_article_text(snapshot)
    assert "IVA 10% € 300,00" in payment_article_text(snapshot)


def test_articolo_13_viene_sostituito_con_il_dettaglio_fiscale():
    preventivo = {
        "totale_imponibile": 1000,
        "iva_percentuale": 10,
        "totale_documento": 1100,
    }
    snapshot = contract_payment_snapshot("due_tranche", preventivo)
    sections = sections_with_payment_article(
        [
            {"titolo": "ART. 12 — MATERIALI", "testo": "Materiali."},
            {"titolo": "ART. 13 — PAGAMENTI", "testo": "Testo generico."},
            {"titolo": "ART. 14 — ALLEGATI", "testo": "Allegati."},
        ],
        snapshot,
    )

    article = sections[1]
    assert article["titolo"] == "ART. 13 — CONDIZIONI DI PAGAMENTO"
    assert "Pagamento in Due Tranche" in article["testo"]
    assert "totale contrattuale IVA inclusa € 1.100,00" in article["testo"]


def test_dettaglio_contratto_rifiuta_una_somma_diversa_dal_totale():
    preventivo = {
        "totale_imponibile": 1000,
        "iva_percentuale": 10,
        "totale_documento": 1100,
    }
    with pytest.raises(HTTPException) as exc:
        contract_payment_snapshot(
            "due_tranche",
            preventivo,
            {
                "tipo": "due_tranche",
                "rate": [
                    {
                        "riferimento": "Alla firma",
                        "descrizione": "Acconto",
                        "importo": 500,
                    }
                ],
            },
        )

    assert exc.value.status_code == 422
    assert "somma delle scadenze" in exc.value.detail
