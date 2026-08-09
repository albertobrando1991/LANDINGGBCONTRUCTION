from decimal import Decimal

import pytest
from fastapi import HTTPException

from contract_workflow_service import (
    default_sections,
    payment_snapshot,
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
