import hashlib
import hmac
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import meta_leads_service as meta


def test_verify_meta_signature_accepts_valid_hmac():
    raw = json.dumps({"entry": []}).encode("utf-8")
    signature = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()

    assert meta.verify_meta_signature(raw, signature, "secret") is True
    assert meta.verify_meta_signature(raw, signature, "wrong") is False


def test_extract_leadgen_events_from_meta_payload():
    payload = {
        "object": "page",
        "entry": [{
            "id": "page-1",
            "changes": [{
                "field": "leadgen",
                "value": {
                    "leadgen_id": "lead-123",
                    "form_id": "form-1",
                    "page_id": "page-1",
                    "created_time": 1717000000,
                },
            }],
        }],
    }

    events = meta.extract_leadgen_events(payload)

    assert events == [{
        "leadgen_id": "lead-123",
        "form_id": "form-1",
        "page_id": "page-1",
        "ad_id": "",
        "created_time": 1717000000,
        "raw_value": payload["entry"][0]["changes"][0]["value"],
    }]


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
