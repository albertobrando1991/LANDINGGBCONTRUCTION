"""Storage privilegiato per file già autorizzati dai servizi tenant-aware."""

from __future__ import annotations

from system_jobs.client_invites import _supabase_admin

BUCKET = "documenti"


def upload_document(path: str, content: bytes, content_type: str) -> None:
    _supabase_admin().storage.from_(BUCKET).upload(
        path,
        content,
        {"content-type": content_type, "upsert": "false"},
    )


def download_document(path: str) -> bytes:
    return _supabase_admin().storage.from_(BUCKET).download(path)


def remove_document(path: str) -> None:
    _supabase_admin().storage.from_(BUCKET).remove([path])
