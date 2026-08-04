"""Risoluzione tenant sui domini di produzione GB Construction."""

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
