import os
import pytest
import requests

BASE_URL = os.environ.get("GB_E2E_BASE_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = os.environ.get("GB_E2E_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("GB_E2E_ADMIN_PASSWORD", "")
STAFF_EMAIL = os.environ.get("GB_E2E_STAFF_EMAIL", "")
STAFF_PASSWORD = os.environ.get("GB_E2E_STAFF_PASSWORD", "")


@pytest.fixture(scope="session")
def api_base():
    return API


@pytest.fixture
def public_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(email, password):
    if not BASE_URL or not email or not password:
        pytest.fail(
            "E2E live abilitato senza GB_E2E_BASE_URL e credenziali GB_E2E_*"
        )
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
