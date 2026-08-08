"""Classificazione in fasi: deve essere deterministica e coprire il catalogo reale."""

from __future__ import annotations

import csv
import io
import zipfile

import pytest

import fasi_lavorazione as fasi
from campania_prezzario import ASSET_PATH


def _famiglie_ufficiali() -> set[str]:
    with zipfile.ZipFile(ASSET_PATH) as archive:
        name = [n for n in archive.namelist() if n.lower().endswith(".csv")][0]
        text = archive.read(name).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter="|")
    next(reader, None)
    return {row[2].strip() for row in reader if row and row[0].strip()}


def test_ogni_famiglia_del_prezzario_ufficiale_ha_una_fase():
    non_coperte = [
        famiglia
        for famiglia in _famiglie_ufficiali()
        if fasi.classifica(super_categoria=famiglia)[0] == fasi.FASE_NON_CLASSIFICATA
    ]
    assert non_coperte == []


def test_override_famiglia_vince_sul_default_della_macro():
    assert fasi.classifica(super_categoria="OPERE EDILI - PAVIMENTI")[1] == (
        "Pavimenti e rivestimenti"
    )
    assert fasi.classifica(super_categoria="OPERE EDILI - MURATURE")[1] == (
        "Strutture e opere murarie"
    )


def test_famiglia_sconosciuta_della_macro_nota_usa_il_default():
    ordine, nome = fasi.classifica(super_categoria="IMPIANTI ELETTRICI - NUOVA FAMIGLIA")
    assert (ordine, nome) == (45, "Impianto elettrico e speciali")


def test_famiglia_generica_lascia_decidere_al_testo():
    ordine, nome = fasi.classifica(
        super_categoria="MATERIALI",
        descrizione="Piastrelle in gres porcellanato per pavimento",
    )
    assert nome == "Pavimenti e rivestimenti"
    assert ordine == 70
    assert fasi.classifica(super_categoria="MATERIALI", descrizione="Sabbia")[1] == (
        "Forniture e materiali"
    )


def test_voce_acca_senza_prezzario_classificata_dalla_descrizione():
    ordine, nome = fasi.classifica(
        super_categoria="Importazione ACCA",
        categoria="Computo PriMus",
        sub_categoria="CAM26_E01.010.010.A",
        descrizione="Demolizione di tramezzatura interna compreso il calo a terra",
    )
    assert (ordine, nome) == (15, "Demolizioni e rimozioni")


def test_scavo_non_finisce_negli_impianti_elettrici_per_la_parola_cavo():
    assert fasi.classifica(descrizione="Scavo a sezione obbligata")[1] == (
        "Scavi e movimenti terra"
    )
    assert fasi.classifica(descrizione="Fornitura di cavo unipolare FS17")[1] == (
        "Impianto elettrico e speciali"
    )


def test_voce_senza_segnali_resta_da_classificare():
    ordine, nome = fasi.classifica(descrizione="Prestazione varia come da accordi")
    assert ordine == fasi.FASE_NON_CLASSIFICATA
    assert nome == "Da classificare"


def test_normalizza_fase_rifiuta_nomi_fuori_catalogo():
    assert fasi.normalizza_fase("Serramenti e opere da vetraio") == (
        75,
        "Serramenti e opere da vetraio",
    )
    with pytest.raises(ValueError):
        fasi.normalizza_fase("Fase inventata")


def _voce(fase, ordine, totale, **extra):
    return {"fase": fase, "fase_ordine": ordine, "totale": totale, **extra}


def test_raggruppa_per_fase_ordina_per_cantiere_e_calcola_incidenza():
    gruppi = fasi.raggruppa_per_fase(
        [
            _voce("Pavimenti e rivestimenti", 70, 300),
            _voce("Demolizioni e rimozioni", 15, 100),
            _voce("Pavimenti e rivestimenti", 70, 100),
        ]
    )
    assert [gruppo["fase"] for gruppo in gruppi] == [
        "Demolizioni e rimozioni",
        "Pavimenti e rivestimenti",
    ]
    assert [gruppo["totale"] for gruppo in gruppi] == [100.0, 400.0]
    assert [gruppo["incidenza"] for gruppo in gruppi] == [20.0, 80.0]
    assert gruppi[1]["n_voci"] == 2


def test_voci_senza_fase_confluiscono_in_da_classificare():
    gruppi = fasi.raggruppa_per_fase([{"qta": 2, "prezzo_unitario": 50}])
    assert gruppi[0]["fase"] == "Da classificare"
    assert gruppi[0]["totale"] == 100.0


def test_raggruppa_per_area_usa_il_default_quando_manca():
    gruppi = fasi.raggruppa_per_area(
        [
            {"area": "Bagno", "totale": 100},
            {"area": None, "totale": 50},
            {"area": "Bagno", "totale": 50},
        ]
    )
    assert [gruppo["area"] for gruppo in gruppi] == ["Bagno", "Tutto l'immobile"]
    assert [gruppo["totale"] for gruppo in gruppi] == [150.0, 50.0]
