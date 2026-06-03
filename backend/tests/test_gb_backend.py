"""GB Construction Lead Engine - end-to-end backend tests."""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://api.gbconstruction.it").rstrip("/")
API = f"{BASE_URL}/api"


# --------------- Health ---------------
class TestHealth:
    def test_root(self, public_client):
        r = public_client.get(f"{API}/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"


# --------------- Estimate engine ---------------
class TestEstimate:
    def test_estimate_three_packages(self, public_client):
        body = {"config": {
            "tipo_immobile": "appartamento", "mq": 90, "livello": "premium",
            "bagni": 2, "camere": 3, "cucina": True,
            "ambienti": ["bagno", "cucina"], "stile": "Moderno minimal",
            "tempistiche": "Subito", "has_files": False,
        }}
        r = public_client.post(f"{API}/estimate", json=body)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "pacchetti" in data
        for key in ("essenziale", "premium", "luxury"):
            assert key in data["pacchetti"], f"missing {key}"
            pkg = data["pacchetti"][key]
            assert "range_basso" in pkg and "range_alto" in pkg and "costo_mq" in pkg
            assert pkg["range_basso"] > 0
            assert pkg["range_alto"] >= pkg["range_basso"]
        # premium dettaglio
        prem = data["pacchetti"]["premium"]
        assert "dettaglio" in prem or "voci" in prem or "categorie" in prem or "n_voci" in prem
        # alerts array
        assert "alerts" in data
        assert isinstance(data["alerts"], list)


# --------------- Public leads ---------------
class TestPublicLeads:
    def test_create_lead(self, public_client):
        payload = {
            "nome": "TEST Mario Rossi", "email": "test_lead_pytest@example.com",
            "telefono": "+39 333 1234567", "citta": "Milano",
            "privacy": True, "newsletter": False,
            "config": {
                "tipo_immobile": "appartamento", "mq": 100, "livello": "premium",
                "bagni": 2, "camere": 3, "cucina": True, "ambienti": ["bagno", "cucina"],
                "stile": "Moderno minimal", "tempistiche": "Subito", "has_files": False,
            }
        }
        r = public_client.post(f"{API}/leads", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data and "estimate" in data and "score" in data
        assert isinstance(data["score"], (int, float))
        assert data["estimate"]["pacchetti"]["premium"]["range_basso"] > 0

    def test_callback(self, public_client):
        r = public_client.post(f"{API}/callback", json={
            "nome": "TEST Callback", "telefono": "+39 333 0000000", "messaggio": "richiamatemi"
        })
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_projects(self, public_client):
        r = public_client.get(f"{API}/projects")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) > 0


# --------------- Auth ---------------
class TestAuth:
    def test_login_admin_sets_cookie(self, public_client):
        r = public_client.post(f"{API}/auth/login",
                               json={"email": "admin@gbconstruction.it", "password": "GBadmin2026!"})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["email"] == "admin@gbconstruction.it"
        assert data["role"] == "admin"
        # httpOnly cookie present
        cookie_header = r.headers.get("set-cookie", "")
        assert "access_token" in cookie_header
        assert "HttpOnly" in cookie_header or "httponly" in cookie_header.lower()

    def test_login_invalid(self, public_client):
        r = public_client.post(f"{API}/auth/login",
                               json={"email": "admin@gbconstruction.it", "password": "wrongpass"})
        assert r.status_code == 401

    def test_me_with_cookie(self, admin_client):
        r = admin_client.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_me_unauthenticated(self, public_client):
        s = requests.Session()
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_logout(self):
        s = requests.Session()
        s.post(f"{API}/auth/login",
               json={"email": "staff@gbconstruction.it", "password": "GBstaff2026!"})
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200


# --------------- Leads (protected) ---------------
class TestLeadsProtected:
    def test_list_leads_protected(self):
        r = requests.get(f"{API}/leads")
        assert r.status_code == 401

    def test_list_leads_seeded(self, admin_client):
        r = admin_client.get(f"{API}/leads")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 10, f"Expected ~12 seeded leads, got {len(data)}"

    def test_filter_status_nuovo(self, admin_client):
        r = admin_client.get(f"{API}/leads", params={"status": "nuovo"})
        assert r.status_code == 200
        for l in r.json():
            assert l["status"] == "nuovo"

    def test_filter_preventivi(self, admin_client):
        r = admin_client.get(f"{API}/leads", params={"status": "preventivi"})
        assert r.status_code == 200
        for l in r.json():
            assert l["status"] in ("preventivo_preparazione", "preventivo_inviato")

    def test_filter_da_contattare(self, admin_client):
        r = admin_client.get(f"{API}/leads", params={"status": "da_contattare"})
        assert r.status_code == 200
        for l in r.json():
            assert l["status"] in ("nuovo", "qualificato")

    def test_search_q(self, admin_client):
        r = admin_client.get(f"{API}/leads", params={"q": "Milano"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_patch_timeline(self, admin_client):
        leads = admin_client.get(f"{API}/leads").json()
        assert leads
        lead = leads[0]
        lid = lead["id"]
        # GET
        r = admin_client.get(f"{API}/leads/{lid}")
        assert r.status_code == 200
        # PATCH status change → timeline event + status_changed_at
        new_status = "qualificato" if lead.get("status") != "qualificato" else "follow_up"
        r = admin_client.patch(f"{API}/leads/{lid}", json={"status": new_status})
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated["status"] == new_status
        assert "status_changed_at" in updated
        # Timeline event for cambio_stato
        tipi = [ev.get("tipo") for ev in updated.get("timeline", [])]
        assert "cambio_stato" in tipi
        # POST timeline note
        r = admin_client.post(f"{API}/leads/{lid}/timeline",
                              json={"tipo": "nota", "testo": "TEST nota da pytest"})
        assert r.status_code == 200, r.text
        assert r.json()["testo"] == "TEST nota da pytest"

    @pytest.mark.timeout(30)
    def test_ai_suggest(self, admin_client):
        leads = admin_client.get(f"{API}/leads").json()
        lid = leads[0]["id"]
        r = admin_client.post(f"{API}/leads/{lid}/suggest", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "suggestion" in data
        assert isinstance(data["suggestion"], str) and len(data["suggestion"]) > 10


# --------------- Dashboard endpoints ---------------
class TestDashboard:
    def test_today(self, admin_client):
        r = admin_client.get(f"{API}/dashboard/today")
        assert r.status_code == 200
        d = r.json()
        for k in ("nuovi_count", "nuovi_caldi", "followup",
                  "preventivi_attesa", "sopralluoghi_count", "alert"):
            assert k in d, f"missing {k}"

    def test_pipeline(self, admin_client):
        r = admin_client.get(f"{API}/pipeline")
        assert r.status_code == 200
        d = r.json()
        assert "columns" in d
        assert len(d["columns"]) == 10
        for col in d["columns"]:
            assert "key" in col and "label" in col and "leads" in col and "valore" in col
            for l in col["leads"]:
                assert "giorni_in_stato" in l

    def test_sopralluoghi(self, admin_client):
        r = admin_client.get(f"{API}/sopralluoghi")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_preventivi(self, admin_client):
        r = admin_client.get(f"{API}/preventivi")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            assert "giorni_silenzio" in data[0]

    def test_cantieri(self, admin_client):
        r = admin_client.get(f"{API}/cantieri")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 3


# --------------- Reports ---------------
class TestReports:
    def test_reports_admin_only_403(self, staff_client):
        r = staff_client.get(f"{API}/reports")
        assert r.status_code == 403

    def test_reports_admin(self, admin_client):
        r = admin_client.get(f"{API}/reports")
        assert r.status_code == 200
        d = r.json()
        for k in ("kpi", "distribuzione", "geografia", "funnel", "timeline", "persi"):
            assert k in d
        assert "lead_ricevuti" in d["kpi"]

    @pytest.mark.timeout(40)
    def test_reports_insights(self, admin_client):
        r = admin_client.post(f"{API}/reports/insights", timeout=40)
        assert r.status_code == 200, r.text
        assert isinstance(r.json().get("insights"), str)
        assert len(r.json()["insights"]) > 20


# --------------- Settings / admin ---------------
class TestSettings:
    def test_coefficienti(self, admin_client):
        r = admin_client.get(f"{API}/coefficienti")
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, dict) and len(d) >= 10

    def test_voci_86(self, admin_client):
        r = admin_client.get(f"{API}/voci")
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d, list)
        assert len(d) >= 86, f"Expected 86 voci, got {len(d)}"

    def test_list_staff(self, admin_client):
        r = admin_client.get(f"{API}/staff")
        assert r.status_code == 200
        emails = [u["email"] for u in r.json()]
        assert "admin@gbconstruction.it" in emails

    def test_staff_create_admin_only(self, staff_client):
        r = staff_client.post(f"{API}/staff", json={
            "nome": "TEST Forbidden", "email": "test_forbidden@example.com",
            "password": "Test1234!", "role": "staff"
        })
        assert r.status_code == 403

    def test_staff_create(self, admin_client):
        email = f"test_pytest_{int(time.time())}@example.com"
        r = admin_client.post(f"{API}/staff", json={
            "nome": "TEST Pytest User", "email": email,
            "password": "Test1234!", "role": "staff"
        })
        assert r.status_code == 200, r.text
        assert r.json()["email"] == email
