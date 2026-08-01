"""Test prezzario: wizard propagation logic (puro) + guard sistema."""
from decimal import Decimal
from collections import defaultdict


def test_wizard_propagation_math():
    """Replica la logica di delta medio usata da applica_wizard."""
    chiavi = [
        {"id": "a", "categoria": "Pavimenti", "old": 52.0, "new": 62.4},  # +20%
        {"id": "b", "categoria": "Pavimenti", "old": 48.0, "new": 52.8},  # +10%
    ]
    deltas = defaultdict(list)
    for c in chiavi:
        deltas[c["categoria"]].append((c["new"] - c["old"]) / c["old"])
    avg = sum(deltas["Pavimenti"]) / len(deltas["Pavimenti"])
    assert abs(avg - 0.15) < 1e-9
    non_chiave = 40.0
    propagated = round(non_chiave * (1 + avg), 2)
    assert propagated == 46.0


def test_um_mapping_campania():
    from predictive_data import VOCI_STANDARD

    um_map = {
        "m²": "mq",
        "m": "ml",
        "m³": "mc",
        "cad": "cad",
        "h": "h",
        "a corpo": "corpo",
        "gg": "n",  # giorni noleggio → conteggio
    }
    allowed = {"mq", "ml", "mc", "cad", "corpo", "kg", "h", "n"}
    for row in VOCI_STANDARD:
        um = row[3]
        mapped = um_map.get(um, um)
        assert mapped in allowed, f"{row[0]} um={um} → {mapped}"


def test_ventotto_wizard_codes():
    wizard = {
        "VS-001", "VS-002", "VS-003", "VS-006", "VS-007", "VS-045", "VS-010", "VS-048",
        "VS-009", "VS-035", "VS-036", "VS-038", "VS-037", "VS-040", "VS-043", "VS-013",
        "VS-016", "VS-014", "VS-021", "VS-022", "VS-060", "VS-029", "VS-030", "VS-034",
        "VS-073", "VS-054", "VS-049", "VS-084",
    }
    assert len(wizard) == 28
    from predictive_data import VOCI_STANDARD
    codes = {r[0] for r in VOCI_STANDARD}
    missing = wizard - codes
    assert not missing, f"codici wizard assenti da predictive_data: {missing}"
