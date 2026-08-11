import asyncio

import ai_service
import server


REPORT = {
    "kpi": {"lead_ricevuti": 8},
    "meta": {"period_label": "Ultimi 30 giorni"},
}


def test_report_insight_fallback_declares_source_without_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("APIKEY_OPENAI", raising=False)

    text, source = asyncio.run(ai_service.generate_insights({"lead_ricevuti": 8}))

    assert ai_service.ai_available() is False
    assert source == "fallback"
    assert "lead" in text.lower()


def test_report_insight_declares_ai_source_after_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        ai_service,
        "_chat_completion",
        lambda _system, _prompt: "Azione AI verificata",
    )

    text, source = asyncio.run(
        ai_service.generate_insights(
            {"lead_ricevuti": 8, "period_label": "Ultimi 30 giorni"}
        )
    )

    assert ai_service.ai_available() is True
    assert text == "Azione AI verificata"
    assert source == "ai"


def test_report_fallback_does_not_check_or_charge_credits(monkeypatch):
    calls = {"check": 0, "charge": 0}

    async def fake_report(_period):
        return REPORT

    async def fake_check(*_args, **_kwargs):
        calls["check"] += 1

    async def fake_charge(*_args, **_kwargs):
        calls["charge"] += 1

    async def fake_generate(_stats):
        return "Suggerimento standard", "fallback"

    monkeypatch.setattr(server, "_sales_report", fake_report)
    monkeypatch.setattr(server.ai_service, "ai_available", lambda: False)
    monkeypatch.setattr(server.ai_service, "generate_insights", fake_generate)
    monkeypatch.setattr(
        server.ai_credit_service, "require_available_for_generation", fake_check
    )
    monkeypatch.setattr(server.ai_credit_service, "charge_credits", fake_charge)

    result = asyncio.run(
        server.reports_insights(period="30d", user={"id": "admin-1"})
    )

    assert result == {"insights": "Suggerimento standard", "source": "fallback"}
    assert calls == {"check": 0, "charge": 0}


def test_report_ai_success_checks_and_charges_once(monkeypatch):
    calls = {"check": 0, "charge": 0, "metadata": None}

    async def fake_report(_period):
        return REPORT

    async def fake_check(*_args, **_kwargs):
        calls["check"] += 1

    async def fake_charge(*_args, **kwargs):
        calls["charge"] += 1
        calls["metadata"] = kwargs.get("metadata")

    async def fake_generate(_stats):
        return "Insight generato", "ai"

    monkeypatch.setattr(server, "_sales_report", fake_report)
    monkeypatch.setattr(server.ai_service, "ai_available", lambda: True)
    monkeypatch.setattr(server.ai_service, "generate_insights", fake_generate)
    monkeypatch.setattr(
        server.ai_credit_service, "require_available_for_generation", fake_check
    )
    monkeypatch.setattr(server.ai_credit_service, "charge_credits", fake_charge)

    result = asyncio.run(
        server.reports_insights(period="30d", user={"id": "admin-1"})
    )

    assert result == {"insights": "Insight generato", "source": "ai"}
    assert calls["check"] == 1
    assert calls["charge"] == 1
    assert calls["metadata"]["period"] == "30d"
