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


async def validated_contract_payload_for_document(
    tenant_id: str, document_id: str
) -> dict:
    """Carica un contratto dopo che la route utente ha autorizzato il documento.

    La route verifica prima la visibilita del documento con RLS. Questo secondo
    controllo privilegiato recupera i dati completi necessari a rigenerare lo
    stesso PDF prodotto per lo staff, senza ampliare le policy delle tabelle
    operative ai clienti.
    """
    import contract_workflow_service
    import db
    from fastapi import HTTPException

    async with db.system_conn() as conn:
        document = await conn.fetchrow(
            """
            select preventivo_id
            from public.documenti_cliente
            where tenant_id = $1::uuid and id = $2::uuid
              and tipo = 'contratto' and contratto_id is not null
            """,
            tenant_id,
            document_id,
        )
        if not document:
            raise HTTPException(status_code=404, detail="Contratto non disponibile")
        return await contract_workflow_service.validated_contract_payload(
            conn, tenant_id, str(document["preventivo_id"])
        )
