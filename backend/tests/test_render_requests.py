from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import ai_architect_service
import server


LEAD_ID = "64b64c8f2f9b2d7a1c000001"
JOB_ID = "64b64c8f2f9b2d7a1c000002"


def _request(path: str = "/api/render-requests"):
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        method="POST",
        headers={},
        client=SimpleNamespace(host="127.0.0.1"),
    )


def _fake_db():
    return SimpleNamespace(
        leads=SimpleNamespace(
            find_one=AsyncMock(
                return_value={
                    "_id": LEAD_ID,
                    "nome": "Cliente Test",
                    "email": "cliente@example.com",
                }
            ),
            update_one=AsyncMock(),
        ),
        ai_architect_jobs=SimpleNamespace(update_one=AsyncMock()),
    )


def test_richiesta_render_da_300_euro_non_avvia_generazione(monkeypatch):
    fake_db = _fake_db()
    create_job = AsyncMock(return_value={"id": JOB_ID})
    process_job = AsyncMock(
        side_effect=AssertionError("La generazione non deve partire dal client")
    )

    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setattr(
        server.ai_architect_service,
        "enforce_upload_rate_limit",
        AsyncMock(),
    )
    monkeypatch.setattr(server.ai_architect_service, "create_job", create_job)
    monkeypatch.setattr(server.ai_architect_service, "process_job", process_job)

    result = asyncio.run(
        server.create_render_request(
            _request(),
            planimetria=SimpleNamespace(filename="casa.pdf"),
            plan_type_selected="auto",
            project_variant_selected="family",
            style_selected="Minimal contemporaneo",
            project_goal="Ristrutturazione completa",
            priorities='["piu luce", "open space"]',
            requested_rooms=(
                '["Soggiorno", "Cucina", "Camera matrimoniale", "Bagno", "Studio"]'
            ),
            sqm=95,
            residents=4,
            budget="100.000",
            notes="Render per living, cucina e camere",
            lead_id=LEAD_ID,
        )
    )

    assert result == {
        "id": JOB_ID,
        "status": "requested",
        "price_eur": 300,
        "payment_status": "pending_staff_confirmation",
        "message": "Richiesta inviata allo staff GB Construction.",
    }
    process_job.assert_not_awaited()

    create_kwargs = create_job.await_args.kwargs
    assert create_kwargs["lead_id"] == LEAD_ID
    assert create_kwargs["created_by_role"] == "client"
    assert create_kwargs["created_by_email"] == "cliente@example.com"

    job_update = fake_db.ai_architect_jobs.update_one.await_args.args[1]["$set"]
    assert job_update["status"] == "requested"
    assert job_update["processing_mode"] == "manual_staff_fulfillment"
    assert job_update["service_price_eur"] == 300
    assert job_update["requested_rooms"] == [
        "Soggiorno",
        "Cucina",
        "Camera matrimoniale",
        "Bagno",
        "Studio",
    ]
    assert job_update["render_room_limit"] >= 5

    lead_update = fake_db.leads.update_one.await_args.args[1]
    assert lead_update["$set"]["render_request_id"] == JOB_ID
    assert lead_update["$addToSet"]["tags"] == "Render personalizzati"
    assert lead_update["$push"]["timeline"]["tipo"] == "render_richiesti"


def test_richiesta_render_resta_fuori_dal_perimetro_ai_staff(monkeypatch):
    async def must_not_authenticate(_request):
        raise AssertionError("La richiesta commerciale non richiede login staff")

    async def ok_response(_request):
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(server, "current_user", must_not_authenticate)

    response = asyncio.run(
        server.ai_architect_staff_access(_request(), ok_response)
    )

    assert response.status_code == 200


def test_endpoint_render_request_e_registrato():
    route = next(
        route
        for route in server.api.routes
        if route.path == "/api/render-requests" and "POST" in route.methods
    )
    assert route.endpoint is server.create_render_request


def test_gli_ambienti_scelti_dal_cliente_vengono_generati_per_primi(monkeypatch):
    monkeypatch.setattr(
        ai_architect_service,
        "_analysis_rooms",
        lambda job, min_confidence=0.45: [
            {"name": "Cucina"},
            {"name": "Soggiorno"},
            {"name": "Ripostiglio"},
        ],
    )

    rooms = ai_architect_service._room_names_for_generation(
        {
            "requested_rooms": ["Studio", "Camera matrimoniale", "Bagno"],
            "render_room_limit": 6,
            "priorities": [],
        }
    )

    assert rooms[:3] == ["Studio", "Camera matrimoniale", "Bagno"]
    assert len(rooms) == 6
