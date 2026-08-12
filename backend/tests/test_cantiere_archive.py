from __future__ import annotations

import asyncio
import io
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import UploadFile

import cantiere_archive_service


TENANT = "a0000000-0000-4000-8000-000000000001"
CANTIERE = "10000000-0000-4000-8000-000000000001"


def test_elenco_archivio_filtra_prefisso_canonico():
    conn = AsyncMock()
    conn.fetch.return_value = [
        {
            "id": "file-1",
            "name": f"{TENANT}/cantiere-{CANTIERE}/1700000000000-aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa-SAL.pdf",
            "metadata": {"size": 123, "mimetype": "application/pdf"},
            "created_at": datetime(2026, 8, 11, tzinfo=timezone.utc),
        }
    ]

    result = asyncio.run(
        cantiere_archive_service.list_documents(conn, TENANT, CANTIERE)
    )

    assert result[0]["displayName"] == "SAL.pdf"
    assert result[0]["size"] == 123
    assert conn.fetch.await_args.args[1] == f"{TENANT}/cantiere-{CANTIERE}/%"


def test_upload_archivio_usa_uuid_cantiere(monkeypatch):
    captured = {}

    def fake_upload(path, content, mime):
        captured.update(path=path, content=content, mime=mime)

    monkeypatch.setattr(cantiere_archive_service, "upload_document", fake_upload)
    file = UploadFile(
        file=io.BytesIO(b"pdf"),
        filename="Verbale cantiere.pdf",
        headers={"content-type": "application/pdf"},
    )

    result = asyncio.run(
        cantiere_archive_service.upload(SimpleNamespace(), TENANT, CANTIERE, file)
    )

    assert captured["path"].startswith(f"{TENANT}/cantiere-{CANTIERE}/")
    assert captured["path"].endswith("-Verbale-cantiere.pdf")
    assert result["contentType"] == "application/pdf"


def test_upload_archivio_con_client_id_e_idempotente(monkeypatch):
    client_id = "70000000-0000-4000-8000-000000000001"
    conn = AsyncMock()
    conn.fetchval.return_value = True

    def unexpected_upload(*_args):
        raise AssertionError("un retry idempotente non deve ricaricare il file")

    monkeypatch.setattr(
        cantiere_archive_service, "upload_document", unexpected_upload
    )
    file = UploadFile(
        file=io.BytesIO(b"foto"),
        filename="Foto avanzamento.jpg",
        headers={"content-type": "image/jpeg"},
    )

    result = asyncio.run(
        cantiere_archive_service.upload(
            conn,
            TENANT,
            CANTIERE,
            file,
            client_id=client_id,
        )
    )

    assert result["path"].endswith(f"/{client_id}-Foto-avanzamento.jpg")
    assert result["displayName"] == "Foto avanzamento.jpg"
    assert conn.fetchval.await_count == 1
