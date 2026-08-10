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


def _voce_100mq(fase, ordine, totale, descrizione="", um="corpo", qta=1):
    return {
        "fase": fase,
        "fase_ordine": ordine,
        "totale": totale,
        "descrizione": descrizione,
        "um": um,
        "qta": qta,
    }


def _ristrutturazione_completa_100mq(massetto="Massetto cementizio tradizionale"):
    return [
        _voce_100mq("Allestimento cantiere e sicurezza", 5, 1500),
        _voce_100mq(*DEMOLIZIONI, 5600),
        _voce_100mq("Strutture e opere murarie", 25, 9000),
        _voce_100mq(*IDRICO, 4000),
        _voce_100mq(*ELETTRICO, 8000),
        _voce_100mq("Impianto termico e climatizzazione", 55, 6000),
        _voce_100mq(
            "Massetti, sottofondi e isolamenti",
            60,
            6000,
            descrizione=massetto,
            um="mq",
            qta=100,
        ),
        _voce_100mq("Intonaci, cartongesso e controsoffitti", 65, 6000),
        _voce_100mq(
            *PAVIMENTI,
            12000,
            descrizione="Pavimento interno in gres",
            um="mq",
            qta=100,
        ),
        _voce_100mq("Serramenti e opere da vetraio", 75, 7000),
        _voce_100mq("Tinteggiature e finiture", 80, 7000),
        _voce_100mq("Pulizie e consegna", 92, 1000),
    ]


def test_ristrutturazione_completa_100mq_dura_circa_quattro_cinque_mesi():
    piano = cronoprogramma.stima(_ristrutturazione_completa_100mq())

    assert piano["profilo"] == "ristrutturazione_completa"
    assert piano["superficie_stimata_mq"] == 100
    assert 90 <= piano["giorni_totali"] <= 110
    assert 4.0 <= piano["mesi"] <= 5.1
    assert piano["giorni_attesa_tecnica"] > 0
    assert any(blocco["tecnica"] for blocco in piano["blocchi"])


def test_massetto_rapido_riduce_solo_l_attesa_tecnica():
    tradizionale = cronoprogramma.stima(_ristrutturazione_completa_100mq())
    rapido = cronoprogramma.stima(
        _ristrutturazione_completa_100mq(
            "Massetto MAPECEM PRONTO a presa e asciugamento rapido"
        )
    )

    assert rapido["giorni_attesa_tecnica"] < tradizionale["giorni_attesa_tecnica"]
    assert rapido["giorni_totali"] < tradizionale["giorni_totali"]


def test_intervento_parziale_non_viene_gonfiato_al_profilo_completo():
    piano = cronoprogramma.stima(
        [_voce_100mq("Tinteggiature e finiture", 80, 3500)]
    )

    assert piano["profilo"] == "intervento_parziale"
    assert piano["giorni_totali"] == 5


def test_superficie_non_somma_posa_fornitura_rivestimenti_e_sfridi():
    voci = [
        _voce_100mq(
            "Demolizioni e rimozioni",
            15,
            920,
            descrizione="Demolizione pavimento appartamento",
            um="mq",
            qta=92,
        ),
        _voce_100mq(
            "Massetti, sottofondi e isolamenti",
            60,
            2024,
            descrizione="Massetto di sottofondo",
            um="mq",
            qta=92,
        ),
        _voce_100mq(
            "Pavimenti e rivestimenti",
            70,
            2576,
            descrizione="Posa in opera di pavimento in gres",
            um="mq",
            qta=92,
        ),
        _voce_100mq(
            "Pavimenti e rivestimenti",
            70,
            5089,
            descrizione="Fornitura di pavimenti e rivestimeni +15% tagli e sfridi",
            um="mq",
            qta=169.66,
        ),
    ]

    piano = cronoprogramma.stima(voci)

    assert piano["superficie_stimata_mq"] == 92
    assert piano["superficie_origine"] == "stimata_dalle_voci"
    assert piano["superficie_richiede_conferma"] is True


def test_superficie_configurata_prevale_sulla_stima_dalle_voci():
    piano = cronoprogramma.stima(
        _ristrutturazione_completa_100mq(), superficie_mq=87
    )

    assert piano["superficie_stimata_mq"] == 87
    assert piano["superficie_origine"] == "configurata"
    assert piano["superficie_richiede_conferma"] is False


def test_durate_manuali_sostituiscono_la_singola_fase_e_ricalcolano_il_totale():
    piano = cronoprogramma.stima(
        [_voce(*DEMOLIZIONI, 7000), _voce(*PAVIMENTI, 12000)],
        superficie_mq=100,
        durate_fasi={"15": 4, "70": 6},
    )

    assert [blocco["giorni"] for blocco in piano["blocchi"]] == [4, 6]
    assert [blocco["giorni_automatici"] for blocco in piano["blocchi"]] == [10, 12]
    assert all(blocco["manuale"] for blocco in piano["blocchi"])
    assert piano["giorni_totali"] == 10
    assert piano["durate_manuali"] == {"15": 4, "70": 6}


def test_durate_manuali_degli_impianti_restano_coordinate_in_parallelo():
    piano = cronoprogramma.stima(
        [_voce(*IDRICO, 4000), _voce(*ELETTRICO, 8000)],
        durate_fasi={35: 2, 45: 3},
    )

    assert piano["giorni_totali"] == 3
    assert all(blocco["parallela"] for blocco in piano["blocchi"])
