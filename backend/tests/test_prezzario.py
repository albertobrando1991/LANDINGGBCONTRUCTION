"""Test prezzario: wizard propagation logic (puro) + guard sistema."""
import asyncio
from decimal import Decimal
from collections import defaultdict

import prezzario_service
from fastapi import HTTPException


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


def test_default_usa_lock_transazionale_tenant_scoped():
    tenant_id = "a0000000-0000-4000-8000-000000000001"
    prezzario_id = "b0000000-0000-4000-8000-000000000001"

    class Conn:
        async def fetchval(self, sql, *args):
            assert "pg_advisory_xact_lock" in sql
            assert args == (f"edilos:prezzario-default:{tenant_id}",)

        async def fetchrow(self, sql, *args):
            assert args == (prezzario_id, tenant_id)
            return {"id": prezzario_id, "tenant_id": tenant_id, "is_default": True}

        async def execute(self, sql, *args):
            assert "set is_default = false" in sql
            assert args == (tenant_id,)

    row = asyncio.run(
        prezzario_service.imposta_default(Conn(), tenant_id, prezzario_id)
    )
    assert row["id"] == prezzario_id
    assert row["is_default"] is True


def test_crea_voce_solo_su_prezzario_modificabile():
    class Conn:
        async def fetchrow(self, sql, *args):
            if "select is_sistema" in sql:
                return {"is_sistema": False}
            assert "insert into public.prezzario_voci" in sql
            return {
                "id": "c0000000-0000-4000-8000-000000000001",
                "descrizione": args[6],
                "prezzo_unitario": Decimal(str(args[8])),
            }

    row = asyncio.run(
        prezzario_service.crea_voce(
            Conn(),
            "a0000000-0000-4000-8000-000000000001",
            "b0000000-0000-4000-8000-000000000002",
            {
                "codice": "GB-001",
                "super_categoria": "Lavorazioni",
                "categoria": "Extra",
                "sub_categoria": None,
                "descrizione": "Nuova lavorazione",
                "um": "cad",
                "prezzo_unitario": Decimal("125.50"),
                "tipo": "a_misura",
            },
        )
    )
    assert row["descrizione"] == "Nuova lavorazione"
    assert row["prezzo_unitario"] == 125.5


def test_modifica_voce_blocca_prezzario_campania():
    class Conn:
        async def fetchrow(self, sql, *args):
            return {"is_sistema": True}

    try:
        asyncio.run(
            prezzario_service.aggiorna_voce(
                Conn(), "tenant", "prezzario", "voce", {"prezzo_unitario": 10}
            )
        )
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError("Il prezzario Campania doveva restare in sola lettura")
