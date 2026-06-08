import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_credit_service as credits


def test_credit_pack_presets_start_from_20_eur():
    assert credits.PACK_PRESETS[0]["amount_eur"] == 20
    assert credits.PACK_PRESETS[0]["credits"] == 20000
    assert all(preset["amount_eur"] >= 20 for preset in credits.PACK_PRESETS)


def test_base_pack_is_enabled_at_20_eur():
    assert credits.BASE_PACK_ENABLED is True
    assert credits.BASE_PACK_CREDITS == 20000


def test_unlimited_email_is_enabled_for_alantis():
    assert credits.email_has_unlimited_generations("INFO@ALANTIS.IT")
    assert not credits.email_has_unlimited_generations("cliente@example.com")


def test_credit_alerts_warn_before_balance_runs_out():
    alerts = credits.build_alerts(credits.LOW_BALANCE_THRESHOLD_CREDITS)

    assert alerts[0]["type"] == "low_balance"
    assert alerts[0]["severity"] == "warning"


def test_credit_alerts_mark_public_generation_insufficient():
    required_full_public = (
        credits.RATE_CARD["ai_architect_preliminary"]["credits"]
        + credits.RATE_CARD["ai_architect_render_public"]["credits"]
    )

    alerts = credits.build_alerts(required_full_public - 1)

    assert alerts[0]["type"] == "insufficient_for_full_public_job"
    assert alerts[0]["severity"] == "danger"


def test_public_generation_with_insufficient_credits_gets_neutral_message(monkeypatch):
    async def blocked(*args, **kwargs):
        raise HTTPException(status_code=402, detail="Crediti AI insufficienti")

    monkeypatch.setattr(credits, "require_available", blocked)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            credits.require_available_for_generation(
                object(),
                credits.RATE_CARD["ai_architect_preliminary"]["credits"],
                public_message=True,
            )
        )

    assert exc.value.status_code == 503
    assert "Il servizio AI non e' momentaneamente disponibile" in exc.value.detail
    assert "Crediti AI insufficienti" not in exc.value.detail


def test_unlimited_user_bypasses_credit_check(monkeypatch):
    async def blocked(*args, **kwargs):
        raise HTTPException(status_code=402, detail="Crediti AI insufficienti")

    monkeypatch.setattr(credits, "require_available", blocked)

    asyncio.run(
        credits.require_available_for_generation(
            object(),
            credits.RATE_CARD["ai_architect_preliminary"]["credits"],
            user={"email": "info@alantis.it"},
        )
    )


def test_public_render_regeneration_uses_public_room_limit(monkeypatch):
    monkeypatch.setattr(credits, "PUBLIC_RENDER_ROOM_LIMIT", 2)
    job = {"usage_context": "public"}

    total = credits.regeneration_credits(job, ["room_render"])

    assert total == 900
