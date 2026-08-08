"""Stima durate: deve essere sequenziale, ripetibile e senza calendario."""

from __future__ import annotations

import cronoprogramma


def _voce(fase, ordine, totale):
    return {"fase": fase, "fase_ordine": ordine, "totale": totale}


DEMOLIZIONI = ("Demolizioni e rimozioni", 15)
ELETTRICO = ("Impianto elettrico e speciali", 45)
IDRICO = ("Impianto idrico-sanitario e scarichi", 35)
PAVIMENTI = ("Pavimenti e rivestimenti", 70)
NOLI = ("Noli, trasporti e smaltimenti", 95)


def test_giorni_derivano_dal_valore_giornaliero_della_fase():
    # 7000 euro di demolizioni a 700 euro/giorno = 10 giorni.
    assert cronoprogramma.giorni_fase(15, 7000) == 10
    # 7000 euro di serramenti a 2500 euro/giorno = 2,8 -> 3 giorni.
    assert cronoprogramma.giorni_fase(75, 7000) == 3


def test_importi_minimi_rispettano_il_presidio_minimo():
    assert cronoprogramma.giorni_fase(15, 50) == cronoprogramma.GIORNI_MINIMI_DEFAULT
    assert cronoprogramma.giorni_fase(5, 50) == 1


def test_le_fasi_si_incatenano_senza_buchi():
    piano = cronoprogramma.stima([_voce(*DEMOLIZIONI, 7000), _voce(*PAVIMENTI, 12000)])
    blocchi = piano["blocchi"]

    assert [blocco["giorni"] for blocco in blocchi] == [10, 10]
    assert blocchi[0]["inizio"] == 0 and blocchi[0]["fine"] == 10
    assert blocchi[1]["inizio"] == 10 and blocchi[1]["fine"] == 20
    assert piano["giorni_totali"] == 20
    assert piano["settimane"] == 4.0


def test_gli_impianti_corrono_in_parallelo():
    piano = cronoprogramma.stima([_voce(*IDRICO, 4000), _voce(*ELETTRICO, 8000)])
    idrico, elettrico = piano["blocchi"]

    assert idrico["inizio"] == elettrico["inizio"] == 0
    assert idrico["parallela"] and elettrico["parallela"]
    # La durata del blocco e quella dell'impianto piu lungo, non la somma.
    assert piano["giorni_totali"] == 10


def test_noli_e_forniture_non_allungano_il_cantiere():
    piano = cronoprogramma.stima([_voce(*DEMOLIZIONI, 7000), _voce(*NOLI, 5000)])
    noli = piano["blocchi"][1]

    assert noli["giorni"] == 0
    assert noli["continuativa"] is True
    assert piano["giorni_totali"] == 10


def test_computo_senza_voci_non_produce_cronoprogramma():
    piano = cronoprogramma.stima([])
    assert piano["blocchi"] == []
    assert piano["giorni_totali"] == 0
