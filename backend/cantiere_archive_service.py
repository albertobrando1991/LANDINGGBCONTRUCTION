"""Archivio privato del cantiere accessibile tramite backend autenticato."""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import PurePosixPath
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from system_jobs.client_documents import download_document, upload_document


MAX_BYTES = 25 * 1024 * 1024
ALLOWED_MIME = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _prefix(tenant_id: str, cantiere_id: str) -> str:
    return f"{tenant_id}/cantiere-{cantiere_id}/"


def _safe_filename(value: str | None) -> str:
    name = PurePosixPath(str(value or "documento").replace("\\", "/")).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._")
    return (cleaned or "documento")[:120]


def _display_name(name: str) -> str:
    return re.sub(r"^(?:\d{13}-)?[0-9a-f-]{36}-", "", name, flags=re.I)


async def list_documents(conn, tenant_id: str, cantiere_id: str) -> list[dict]:
    prefix = _prefix(tenant_id, cantiere_id)
    rows = await conn.fetch(
        """
        select id, name, metadata, created_at
        from storage.objects
        where bucket_id = 'documenti'
          and name like $1
        order by created_at desc
        limit 100
        """,
        prefix + "%",
    )
    result = []
    for row in rows:
        path = str(row["name"])
        relative = path[len(prefix) :]
        if not relative or "/" in relative:
            continue
        metadata = row["metadata"] or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        result.append(
            {
                "id": str(row["id"]),
                "name": relative,
                "displayName": _display_name(relative),
                "path": path,
                "createdAt": row["created_at"].isoformat(),
                "size": int(metadata.get("size") or metadata.get("contentLength") or 0),
                "contentType": metadata.get("mimetype")
                or metadata.get("contentType")
                or "",
            }
        )
    return result


async def upload(
    conn,
    tenant_id: str,
    cantiere_id: str,
    file: UploadFile,
    *,
    client_id: str | None = None,
) -> dict:
    content = await file.read(MAX_BYTES + 1)
    if not content or len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Il documento deve essere compreso tra 1 byte e 25 MB",
        )
    mime = (file.content_type or "application/octet-stream").lower()
    if mime not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail="Formato non supportato: usa PDF, immagini, Word o Excel",
        )
    filename = _safe_filename(file.filename)
    token = client_id or f"{int(time.time() * 1000)}-{uuid4()}"
    path = f"{_prefix(tenant_id, cantiere_id)}{token}-{filename}"
    if client_id:
        exists = await conn.fetchval(
            "select exists(select 1 from storage.objects where bucket_id = 'documenti' and name = $1)",
            path,
        )
        if exists:
            return {
                "path": path,
                "displayName": file.filename or filename,
                "size": len(content),
                "contentType": mime,
            }
    try:
        await asyncio.to_thread(upload_document, path, content, mime)
    except Exception:
        if not client_id or not await conn.fetchval(
            "select exists(select 1 from storage.objects where bucket_id = 'documenti' and name = $1)",
            path,
        ):
            raise
    return {
        "path": path,
        "displayName": file.filename or filename,
        "size": len(content),
        "contentType": mime,
    }


async def download(tenant_id: str, cantiere_id: str, path: str) -> bytes:
    if not str(path or "").startswith(_prefix(tenant_id, cantiere_id)):
        raise HTTPException(status_code=403, detail="Documento non autorizzato")
    try:
        return await asyncio.to_thread(download_document, path)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Documento non disponibile") from exc
