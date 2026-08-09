"""API del controllo economico contrattuale per cantiere."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

import auth as authlib
import financial_service
from economic_note_pdf import genera_nota_economica_pdf


class RataPianoBody(BaseModel):
    numero: Optional[int] = Field(default=None, ge=1)
    tipo: Literal["acconto", "sal", "saldo"] = "sal"
    titolo: str = Field(min_length=2, max_length=300)
    importo: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    percentuale: Optional[Decimal] = Field(default=None, ge=0, le=100)
    data_scadenza: date
    modalita_pagamento: Optional[str] = Field(default=None, max_length=100)
    sal_id: Optional[UUID] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class PianoPagamentoBody(BaseModel):
    preventivo_id: UUID
    rate: list[RataPianoBody] = Field(min_length=1, max_length=30)
    email_automatica: bool = True
    whatsapp_automatico: bool = False
    whatsapp_consenso: bool = False
    giorni_preavviso: list[int] = Field(
        default_factory=lambda: [7, 1, 0], min_length=1, max_length=10
    )


class PagamentoBody(BaseModel):
    importo: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    data_pagamento: date = Field(default_factory=date.today)
    metodo: Optional[str] = Field(default=None, max_length=100)
    riferimento: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = Field(default=None, max_length=2000)


class CollegaSalBody(BaseModel):
    sal_id: Optional[UUID] = None


class ExtraBody(BaseModel):
    titolo: str = Field(min_length=2, max_length=200)
    descrizione: str = Field(min_length=2, max_length=2000)
    imponibile: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    iva_percentuale: Decimal = Field(default=Decimal("10"), ge=0, le=100)
    data_scadenza: Optional[date] = None
    sal_id: Optional[UUID] = None


class DocumentoBody(BaseModel):
    tipo: Literal["riepilogo_sal", "autorizzazione_extra"]
    riferimento_id: UUID


class FirmaDocumentoBody(BaseModel):
    decisione: Literal["sottoscritto", "rifiutato"]
    firmatario_nome: str = Field(min_length=2, max_length=200)


def _uuid(value: str, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{label} non valido") from exc


def _require_finance(tenant: dict) -> None:
    if tenant.get("role") not in financial_service.FINANCIAL_ROLES:
        raise HTTPException(status_code=403, detail="Accesso riservato ad amministrazione")


def register_financial_routes(api: APIRouter, db, get_tenant_conn) -> None:
    @api.get("/cantieri/{cantiere_id}/controllo-economico")
    async def controllo_economico(request: Request, cantiere_id: str):
        user = await authlib.get_current_user(request, db)
        cantiere_uuid = _uuid(cantiere_id, "Cantiere")
        async with get_tenant_conn(request, user) as (conn, tenant):
            _require_finance(tenant)
            return await financial_service.get_controllo_cantiere(
                conn, tenant["id"], cantiere_uuid
            )

    @api.post("/cantieri/{cantiere_id}/piano-pagamenti", status_code=201)
    async def crea_piano(
        request: Request, cantiere_id: str, body: PianoPagamentoBody
    ):
        user = await authlib.get_current_user(request, db)
        cantiere_uuid = _uuid(cantiere_id, "Cantiere")
        async with get_tenant_conn(request, user) as (conn, tenant):
            _require_finance(tenant)
            return await financial_service.crea_piano_pagamenti(
                conn,
                tenant["id"],
                cantiere_uuid,
                preventivo_id=str(body.preventivo_id),
                rate=[item.model_dump() for item in body.rate],
                email_automatica=body.email_automatica,
                whatsapp_automatico=body.whatsapp_automatico,
                whatsapp_consenso=body.whatsapp_consenso,
                giorni_preavviso=body.giorni_preavviso,
            )

    @api.get("/cantieri/{cantiere_id}/piano-pagamenti/suggerimento")
    async def suggerimento_piano(request: Request, cantiere_id: str):
        user = await authlib.get_current_user(request, db)
        cantiere_uuid = _uuid(cantiere_id, "Cantiere")
        async with get_tenant_conn(request, user) as (conn, tenant):
            _require_finance(tenant)
            return await financial_service.suggerisci_piano_pagamenti(
                conn, tenant["id"], cantiere_uuid
            )

    @api.post("/economics/incassi/{incasso_id}/pagamenti", status_code=201)
    async def registra_pagamento(
        request: Request, incasso_id: str, body: PagamentoBody
    ):
        user = await authlib.get_current_user(request, db)
        item_uuid = _uuid(incasso_id, "Rata")
        async with get_tenant_conn(request, user) as (conn, tenant):
            _require_finance(tenant)
            return await financial_service.registra_pagamento(
                conn,
                tenant["id"],
                item_uuid,
                **body.model_dump(),
            )

    @api.patch("/economics/incassi/{incasso_id}/sal")
    async def collega_sal(
        request: Request, incasso_id: str, body: CollegaSalBody
    ):
        user = await authlib.get_current_user(request, db)
        item_uuid = _uuid(incasso_id, "Rata")
        async with get_tenant_conn(request, user) as (conn, tenant):
            _require_finance(tenant)
            return await financial_service.collega_sal_rata(
                conn,
                tenant["id"],
                item_uuid,
                str(body.sal_id) if body.sal_id else None,
            )

    @api.post("/cantieri/{cantiere_id}/extra", status_code=201)
    async def crea_extra(request: Request, cantiere_id: str, body: ExtraBody):
        user = await authlib.get_current_user(request, db)
        cantiere_uuid = _uuid(cantiere_id, "Cantiere")
        async with get_tenant_conn(request, user) as (conn, tenant):
            _require_finance(tenant)
            data = body.model_dump()
            if data.get("sal_id"):
                data["sal_id"] = str(data["sal_id"])
            return await financial_service.crea_extra(
                conn, tenant["id"], cantiere_uuid, **data
            )

    @api.post("/cantieri/{cantiere_id}/documenti-economici", status_code=201)
    async def genera_documento(
        request: Request, cantiere_id: str, body: DocumentoBody
    ):
        user = await authlib.get_current_user(request, db)
        cantiere_uuid = _uuid(cantiere_id, "Cantiere")
        async with get_tenant_conn(request, user) as (conn, tenant):
            _require_finance(tenant)
            return await financial_service.genera_documento_economico(
                conn,
                tenant["id"],
                cantiere_uuid,
                tipo=body.tipo,
                riferimento_id=str(body.riferimento_id),
            )

    @api.get("/documenti-economici/{documento_id}/pdf")
    async def documento_pdf(request: Request, documento_id: str):
        user = await authlib.get_current_user(request, db)
        document_uuid = _uuid(documento_id, "Documento")
        async with get_tenant_conn(request, user) as (conn, tenant):
            if tenant.get("role") not in financial_service.FINANCIAL_ROLES | {"client"}:
                raise HTTPException(status_code=403, detail="Documento non disponibile")
            if tenant.get("role") == "client":
                row = await conn.fetchrow(
                    """
                    select v.documento_id as id, v.*, t.ragione_sociale,
                           t.slug, t.piva, t.theme, t.contatti
                    from public.portale_documenti_economici v
                    join public.tenants t on t.id = v.tenant_id
                    where v.tenant_id = $1::uuid and v.documento_id = $2::uuid
                    """,
                    tenant["id"],
                    document_uuid,
                )
            else:
                row = await conn.fetchrow(
                    """
                    select d.*, t.ragione_sociale, t.slug, t.piva, t.theme, t.contatti
                    from public.documenti_economici d
                    join public.tenants t on t.id = d.tenant_id
                    where d.tenant_id = $1::uuid and d.id = $2::uuid
                    """,
                    tenant["id"],
                    document_uuid,
                )
            if not row:
                raise HTTPException(status_code=404, detail="Documento non trovato")
            document = dict(row)
            pdf = genera_nota_economica_pdf(document)
            return Response(
                content=pdf,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": (
                        f'inline; filename="{document["tipo"]}-{document_uuid[:8]}.pdf"'
                    )
                },
            )

    @api.post("/documenti-economici/{documento_id}/firma", status_code=201)
    async def firma_documento(
        request: Request, documento_id: str, body: FirmaDocumentoBody
    ):
        user = await authlib.get_current_user(request, db)
        document_uuid = _uuid(documento_id, "Documento")
        async with get_tenant_conn(request, user) as (conn, tenant):
            if tenant.get("role") != "client":
                raise HTTPException(status_code=403, detail="Firma riservata al cliente")
            document = await conn.fetchrow(
                """
                select documento_id as id, cantiere_id
                from public.portale_documenti_economici
                where tenant_id = $1::uuid and documento_id = $2::uuid
                  and stato = 'inviato' and not gia_deciso
                """,
                tenant["id"],
                document_uuid,
            )
            if not document:
                raise HTTPException(status_code=404, detail="Documento non firmabile")
            ip = request.client.host if request.client else "0.0.0.0"
            row = await conn.fetchrow(
                """
                insert into public.documenti_economici_firme (
                  tenant_id, cantiere_id, documento_id, user_id,
                  decisione, firmatario_nome, ip, user_agent
                ) values (
                  $1::uuid, $2::uuid, $3::uuid, auth.uid(), $4, $5, $6::inet, $7
                ) returning *
                """,
                tenant["id"],
                str(document["cantiere_id"]),
                document_uuid,
                body.decisione,
                body.firmatario_nome.strip(),
                ip,
                request.headers.get("user-agent", "")[:500],
            )
            return dict(row)
