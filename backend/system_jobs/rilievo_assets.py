"""Storage privilegiato per asset rilievo gia autorizzati dal backend tenant-aware."""

from __future__ import annotations

from fastapi import HTTPException

from system_jobs.client_invites import _supabase_admin

ALLOWED_BUCKETS = frozenset({"planimetrie", "foto-cantiere"})


def _bucket(name: str):
    if name not in ALLOWED_BUCKETS:
        raise HTTPException(status_code=400, detail="Archivio rilievo non valido")
    try:
        return _supabase_admin().storage.from_(name)
    except HTTPException as exc:
        if exc.status_code == 503:
            raise HTTPException(
                status_code=503, detail="Archivio rilievo non configurato sul server"
            ) from exc
        raise


def upload_asset(
    bucket: str,
    path: str,
    content: bytes,
    content_type: str,
    *,
    upsert: bool = False,
) -> None:
    try:
        _bucket(bucket).upload(
            path,
            content,
            {
                "content-type": content_type,
                "upsert": "true" if upsert else "false",
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Caricamento archivio rilievo non riuscito"
        ) from exc


def signed_asset_urls(
    bucket: str, paths: list[str], expires_in: int = 300
) -> list[str]:
    try:
        responses = _bucket(bucket).create_signed_urls(paths, expires_in)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="Anteprime rilievo non disponibili"
        ) from exc
    urls = [
        str(item.get("signedURL") or item.get("signedUrl") or "") for item in responses
    ]
    if len(urls) != len(paths) or any(not url for url in urls):
        raise HTTPException(status_code=502, detail="Anteprime rilievo non disponibili")
    return urls
