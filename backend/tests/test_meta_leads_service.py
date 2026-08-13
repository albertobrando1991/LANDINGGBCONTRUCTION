import hashlib
import hmac
import json
import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import meta_leads_service as meta
import server


def _request(query: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/webhooks/meta",
            "query_string": query.encode("ascii"),
            "headers": [],
        }
    )


def test_meta_webhook_verification_is_registered_with_and_without_api_prefix():
    paths = {
        route.path
        for route in server.app.routes
        if "GET" in (getattr(route, "methods", None) or set())
    }
    assert "/api/webhooks/meta" in paths
    assert "/webhooks/meta" in paths


def test_meta_webhook_verification_returns_plain_challenge(monkeypatch):
    monkeypatch.setenv("META_VERIFY_TOKEN", "test-verify-token")
    response = asyncio.run(
        server.verify_meta_webhook(
            _request(
                "hub.mode=subscribe&hub.verify_token=test-verify-token&hub.challenge=test123"
            )
        )
    )
    assert response.status_code == 200
    assert response.body == b"test123"
    assert response.media_type == "text/plain"


def test_meta_webhook_verification_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("META_VERIFY_TOKEN", "test-verify-token")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            server.verify_meta_webhook(
                _request(
                    "hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=test123"
                )
            )
        )
    assert exc.value.status_code == 403


def test_verify_meta_signature_accepts_valid_hmac():
    raw = json.dumps({"entry": []}).encode("utf-8")
    signature = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()

    assert meta.verify_meta_signature(raw, signature, "secret") is True
    assert meta.verify_meta_signature(raw, signature, "wrong") is False


def test_extract_leadgen_events_from_meta_payload():
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page-1",
                "changes": [
                    {
                        "field": "leadgen",
                        "value": {
                            "leadgen_id": "lead-123",
                            "form_id": "form-1",
                            "page_id": "page-1",
                            "created_time": 1717000000,
                        },
                    }
                ],
            }
        ],
    }

    events = meta.extract_leadgen_events(payload)

    assert events == [
        {
            "leadgen_id": "lead-123",
            "form_id": "form-1",
            "page_id": "page-1",
            "ad_id": "",
            "created_time": 1717000000,
            "raw_value": payload["entry"][0]["changes"][0]["value"],
        }
    ]


def test_build_meta_lead_doc_maps_standard_and_italian_fields():
    event = {"leadgen_id": "lead-123", "form_id": "form-1", "page_id": "page-1"}
    graph_lead = {
        "id": "lead-123",
        "created_time": "2026-06-01T08:00:00+00:00",
        "campaign_id": "camp-1",
        "campaign_name": "Ristrutturazione Napoli",
        "field_data": [
            {"name": "full_name", "values": ["Mario Rossi"]},
            {"name": "email", "values": ["Mario@Example.com"]},
            {"name": "phone_number", "values": ["+39 333 123 4567"]},
            {"name": "citta", "values": ["Napoli"]},
            {"name": "metri quadri", "values": ["95 mq"]},
            {"name": "bagni", "values": ["2"]},
            {"name": "pacchetto", "values": ["Luxury"]},
        ],
    }

    doc = meta.build_meta_lead_doc(event, graph_lead, owner="Vincenzo Brancale")

    assert doc["origine"] == "meta_ads"
    assert doc["nome"] == "Mario Rossi"
    assert doc["email_norm"] == "mario@example.com"
    assert doc["phone_norm"] == "393331234567"
    assert doc["citta"] == "Napoli"
    assert doc["mq"] == 95
    assert doc["bagni"] == 2
    assert doc["livello"] == "luxury"
    assert doc["owner"] == "Vincenzo Brancale"
    assert doc["external_ids"]["meta_leadgen_id"] == "lead-123"
    assert doc["meta"]["campaign_name"] == "Ristrutturazione Napoli"
    assert doc["sla_due_at"].startswith("2026-06-01T08:15:00")


def test_build_meta_lead_doc_maps_qualified_meta_instant_form_fields():
    event = {"leadgen_id": "lead-qualified", "form_id": "form-qualified", "page_id": "page-1"}
    graph_lead = {
        "id": "lead-qualified",
        "created_time": "2026-08-13T09:00:00+00:00",
        "field_data": [
            {"name": "full_name", "values": ["Cliente Qualificato"]},
            {"name": "email", "values": ["cliente@example.com"]},
            {"name": "phone_number", "values": ["+39 333 000 0000"]},
            {
                "name": "Che tipo di immobile devi ristrutturare?",
                "values": ["Villa"],
            },
            {
                "name": "In che condizioni si trova l'immobile?",
                "values": ["Completamente da ristrutturare"],
            },
            {
                "name": "In quale città si trova l'immobile?",
                "values": ["Napoli"],
            },
            {
                "name": "Qual è l'indirizzo dell'immobile?",
                "values": ["Via Roma 10"],
            },
            {
                "name": "Quanti metri quadrati è l'immobile?",
                "values": ["145 mq"],
            },
            {
                "name": "Che tipo di ristrutturazione ti serve?",
                "values": ["Ristrutturazione completa"],
            },
            {
                "name": "Qual è il budget indicativo?",
                "values": ["120.000-200.000 €"],
            },
        ],
    }

    doc = meta.build_meta_lead_doc(event, graph_lead)

    assert doc["tipo_immobile"] == "villa"
    assert doc["stato_immobile"] == "Completamente da ristrutturare"
    assert doc["citta"] == "Napoli"
    assert doc["indirizzo"] == "Via Roma 10"
    assert doc["mq"] == 145
    assert doc["tipo_ristrutturazione"] == "Ristrutturazione completa"
    assert doc["budget_indicativo"] == "120.000-200.000 €"
    assert doc["livello"] == "luxury"


def test_fetch_meta_lead_formats_detailed_graph_api_error():
    class DummyResponse:
        status_code = 400

        def json(self):
            return {
                "error": {
                    "message": "Invalid OAuth access token",
                    "type": "OAuthException",
                    "code": 190,
                    "error_subcode": 463,
                }
            }

    def dummy_get(*args, **kwargs):
        return DummyResponse()

    with pytest.raises(meta.MetaLeadError) as exc_info:
        meta.fetch_meta_lead("lead-123", page_token="bad_token", get=dummy_get)

    err_msg = str(exc_info.value)
    assert "[HTTP 400]" in err_msg
    assert "code 190" in err_msg
    assert "subcode 463" in err_msg
    assert "Invalid OAuth access token" in err_msg

