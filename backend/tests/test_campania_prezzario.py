from decimal import Decimal

from campania_prezzario import EXPECTED_ROWS, load_official_rows


def test_asset_ufficiale_campania_2026_e_completo():
    rows = load_official_rows()

    assert len(rows) == EXPECTED_ROWS == 31_755
    assert rows[0][0] == "CAM26_A00.010.100.A"
    assert rows[-1][0] == "CAM26_V08.030.010.D"
    assert rows[0][6] == Decimal("217.67")
    assert sum(row[6] == 0 for row in rows) == 5
    assert len({row[0] for row in rows}) == EXPECTED_ROWS


def test_unita_ufficiali_vengono_preservate_e_normalizzate():
    rows = load_official_rows()
    units = {row[5] for row in rows}

    assert {"mq", "mc", "cad", "corpo", "cad/30gg", "ha", "t"} <= units
    assert "a corpo" not in units
