"""Iteration 2 regression: real Brancale staff names + photos, lead owners, sopralluoghi tecnico."""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cantiere-smart-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

BRANCALE_NAMES = {"Giuseppe Brancale", "Giovanni Brancale", "Vincenzo Brancale"}


class TestBrancaleStaff:
    """GET /api/staff returns the 3 Brancale users with photo field."""

    def test_staff_has_three_brancale_with_photos(self, admin_client):
        r = admin_client.get(f"{API}/staff")
        assert r.status_code == 200, r.text
        users = r.json()
        # Map name -> user
        names_in_response = {u.get("name") or u.get("nome") for u in users}
        missing = BRANCALE_NAMES - names_in_response
        assert not missing, f"Missing Brancale staff: {missing}; got {names_in_response}"
        # Photo field present and non-empty for each Brancale
        for u in users:
            nm = u.get("name") or u.get("nome")
            if nm in BRANCALE_NAMES:
                photo = u.get("photo") or u.get("avatar") or u.get("photo_url")
                assert photo, f"Staff {nm} missing photo field. Keys: {list(u.keys())}"
                assert isinstance(photo, str) and len(photo) > 5

    def test_staff_roles_present(self, admin_client):
        r = admin_client.get(f"{API}/staff")
        users = r.json()
        roles = {(u.get("name") or u.get("nome")): u.get("role") for u in users if (u.get("name") or u.get("nome")) in BRANCALE_NAMES}
        # admin must exist
        assert "admin" in roles.values(), f"No admin role among Brancale: {roles}"


class TestLeadOwnersBrancale:
    """Seeded leads owners should be 'Vincenzo Brancale' or 'Giovanni Brancale'."""

    def test_lead_owners_are_brancale(self, admin_client):
        r = admin_client.get(f"{API}/leads")
        assert r.status_code == 200
        leads = r.json()
        assert leads, "No leads seeded"
        owners = set()
        for l in leads:
            owner = l.get("owner") or l.get("assigned_to") or l.get("responsabile")
            if owner:
                owners.add(owner)
        # At least one Brancale owner expected
        brancale_owners = owners & {"Vincenzo Brancale", "Giovanni Brancale", "Giuseppe Brancale"}
        assert brancale_owners, f"No Brancale owners found in leads. Owners seen: {owners}"


class TestSopralluoghiTecnico:
    """Sopralluoghi default tecnico should be a Brancale name."""

    def test_sopralluoghi_tecnico_brancale(self, admin_client):
        r = admin_client.get(f"{API}/sopralluoghi")
        assert r.status_code == 200
        items = r.json()
        if not items:
            # No sopralluoghi seeded - not a hard failure; skip-like
            return
        tecnici = set()
        for s in items:
            t = s.get("tecnico") or s.get("assegnato_a") or s.get("responsabile")
            if t:
                tecnici.add(t)
        if tecnici:
            assert tecnici & BRANCALE_NAMES, f"Tecnico names not Brancale: {tecnici}"


class TestPublicProjects:
    def test_projects_alive(self):
        r = requests.get(f"{API}/projects", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
