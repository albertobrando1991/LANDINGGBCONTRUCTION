"""Risoluzione tenant sui domini di produzione GB Construction."""

import asyncio

import pytest
from starlette.requests import Request

import tenancy


def _request(*, host: str, query: str = "", tenant_header: str | None = None):
    headers = [(b"host", host.encode("ascii"))]
    if tenant_header is not None:
        headers.append((b"x-tenant-slug", tenant_header.encode("ascii")))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/api/tenant/config",
            "raw_path": b"/api/tenant/config",
            "query_string": query.encode("ascii"),
            "headers": headers,
            "server": (host, 443),
            "client": ("127.0.0.1", 12345),
        }
    )


def test_domini_produzione_usano_tenant_gb_default():
    for host in (
        "gbconstruction.it",
        "www.gbconstruction.it",
        "app.gbconstruction.it",
        "api.gbconstruction.it",
    ):
        assert tenancy.extract_tenant_slug(_request(host=host)) == "gbconstruction"


def test_hostname_alantis_non_seleziona_un_tenant():
    request = _request(host="demo.alantis.it")
    assert tenancy.extract_tenant_slug(request) == "gbconstruction"


def test_query_tenant_resta_disponibile_per_test_controllati():
    request = _request(host="localhost", query="tenant=demo")
    assert tenancy.extract_tenant_slug(request) == "demo"


def test_header_tenant_valido_ha_priorita_sulla_query():
    request = _request(
        host="gbconstruction.it",
        query="tenant=demo",
        tenant_header="gbconstruction",
    )
    assert tenancy.extract_tenant_slug(request) == "gbconstruction"


def test_slug_non_valido_non_viene_propagato():
    request = _request(host="localhost", query="tenant=../demo")
    assert tenancy.extract_tenant_slug(request) == "gbconstruction"


def test_claim_tenant_senza_ruolo_usa_il_minimo_privilegio():
    memberships = tenancy.tenants_from_user(
        {"app_tenants": [{"t": "tenant-id"}]}
    )
    assert memberships == [{"tenant_id": "tenant-id", "role": "client"}]


class _FakeConn:
    def __init__(self, row):
        self.row = row
        self.calls = []

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        return self.row


def test_resolve_cantiere_uuid_accetta_uuid_senza_query():
    conn = _FakeConn(None)
    value = "0b1f767b-dda4-4993-9b5c-13d78e408c80"
    assert asyncio.run(tenancy.resolve_cantiere_uuid(conn, "tenant", value)) == value
    assert conn.calls == []


def test_resolve_cantiere_uuid_mappa_id_legacy_nel_tenant():
    conn = _FakeConn({"id": "0b1f767b-dda4-4993-9b5c-13d78e408c80"})
    result = asyncio.run(
        tenancy.resolve_cantiere_uuid(conn, "tenant-id", "6a2598f54cc46468f40fdf07")
    )
    assert result == "0b1f767b-dda4-4993-9b5c-13d78e408c80"
    assert conn.calls[0][1] == ("tenant-id", "6a2598f54cc46468f40fdf07")


def test_resolve_cantiere_uuid_rifiuta_legacy_assente():
    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            tenancy.resolve_cantiere_uuid(_FakeConn(None), "tenant-id", "missing")
        )
    assert exc_info.value.status_code == 404
