import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://cantiere-smart-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@gbconstruction.it"
ADMIN_PASSWORD = "GBadmin2026!"
STAFF_EMAIL = "staff@gbconstruction.it"
STAFF_PASSWORD = "GBstaff2026!"


@pytest.fixture(scope="session")
def api_base():
    return API


@pytest.fixture
def public_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(email, password):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def admin_client():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def staff_client():
    return _login(STAFF_EMAIL, STAFF_PASSWORD)
