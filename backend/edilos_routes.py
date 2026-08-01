"""API EdilOS Fase 1: prezzario, computi, mapping AI, preventivi."""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

import auth as authlib
import boq_service
import mapping_engine
import prezzario_service
from engines.metriche import estrai_metriche
from preventivo_pdf import genera_pdf_preventivo

router = APIRouter(tags=["edilos"])


def _token(request: Request) -> str:
    t = authlib._extract_token(request)
    if not t:
        raise HTTPException(status_code=401, detail="Non autenticato")
    return t


async def _user(request: Request, db) -> dict:
    return await authlib.get_current_user(request, db)


# ---------- Prezzario ----------
class DuplicaBody(BaseModel):
    nome: str


class WizardBody(BaseModel):
    correzioni: Dict[str, float] = Field(default_factory=dict)


class RipristinaBody(BaseModel):
    prezzario_id: Optional[str] = None
    voce_ids: Optional[List[str]] = None
    categoria: Optional[str] = None


def register_edilos_routes(api: APIRouter, db, get_tenant_conn):
    """Monta le route su un APIRouter esistente (prefix /api)."""

    @api.get("/prezzario")
    async def lista_prezzari(request: Request):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await prezzario_service.lista_prezzari(conn, tenant["id"])

    @api.post("/prezzario/{prezzario_id}/duplica")
    async def duplica(request: Request, prezzario_id: str, body: DuplicaBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await prezzario_service.duplica_prezzario(
                conn, tenant["id"], prezzario_id, body.nome
            )

    @api.get("/prezzario/{prezzario_id}/voci")
    async def voci(request: Request, prezzario_id: str, q: Optional[str] = None, categoria: Optional[str] = None):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await prezzario_service.lista_voci(
                conn, tenant["id"], prezzario_id, q=q, categoria=categoria
            )

    @api.get("/prezzario/{prezzario_id}/wizard")
    async def wizard_get(request: Request, prezzario_id: str):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await prezzario_service.voci_wizard(conn, tenant["id"], prezzario_id)

    @api.post("/prezzario/{prezzario_id}/wizard")
    async def wizard_post(request: Request, prezzario_id: str, body: WizardBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            corr = {k: Decimal(str(v)) for k, v in body.correzioni.items()}
            return await prezzario_service.applica_wizard(
                conn, tenant["id"], prezzario_id, corr
            )

    @api.post("/prezzario/ripristina")
    async def ripristina(request: Request, body: RipristinaBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            n = await prezzario_service.ripristina_campania(
                conn,
                tenant["id"],
                prezzario_id=body.prezzario_id,
                voce_ids=body.voce_ids,
                categoria=body.categoria,
            )
            return {"ripristinate": n}

    @api.post("/prezzario/{prezzario_id}/importa-csv")
    async def importa(request: Request, prezzario_id: str, file: UploadFile = File(...)):
        user = await _user(request, db)
        data = await file.read()
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await prezzario_service.importa_csv(
                conn, tenant["id"], prezzario_id, data
            )

    # ---------- Computi ----------
    class CreaComputoBody(BaseModel):
        lead_id: Optional[str] = None
        cantiere_id: Optional[str] = None
        prezzario_id: Optional[str] = None
        tipo: str = "estimativo"

    class AggiungiVoceBody(BaseModel):
        prezzario_voce_id: str
        qta: float = 1

    class AggiornaVoceBody(BaseModel):
        qta: Optional[float] = None
        prezzo_unitario: Optional[float] = None
        descrizione: Optional[str] = None
        validata_umano: Optional[bool] = None

    class RiordinaBody(BaseModel):
        ordine: List[str]

    class PreventivoBody(BaseModel):
        sconto: float = 0
        iva: float = 10

    class GeneraDaAiBody(BaseModel):
        lead_id: Optional[str] = None
        prezzario_id: Optional[str] = None
        analisi_ai: Dict[str, Any] = Field(default_factory=dict)
        config_lead: Optional[Dict[str, Any]] = None

    class ValidaAiBody(BaseModel):
        voce_ids: Optional[List[str]] = None

    @api.get("/computi")
    async def lista_computi(request: Request):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.lista_computi(conn, tenant["id"])

    @api.post("/computi")
    async def crea_computo(request: Request, body: CreaComputoBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.crea_computo(
                conn,
                tenant["id"],
                lead_id=body.lead_id,
                cantiere_id=body.cantiere_id,
                prezzario_id=body.prezzario_id,
                tipo=body.tipo,
            )

    @api.get("/computi/{computo_id}")
    async def get_computo(request: Request, computo_id: str):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.get_computo(conn, tenant["id"], computo_id)

    @api.post("/computi/{computo_id}/voci")
    async def add_voce(request: Request, computo_id: str, body: AggiungiVoceBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.aggiungi_voce(
                conn, tenant["id"], computo_id, body.prezzario_voce_id, body.qta
            )

    @api.patch("/computi/voci/{voce_id}")
    async def patch_voce(request: Request, voce_id: str, body: AggiornaVoceBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.aggiorna_voce(
                conn, tenant["id"], voce_id, **body.model_dump(exclude_none=True)
            )

    @api.post("/computi/{computo_id}/riordina")
    async def riordina(request: Request, computo_id: str, body: RiordinaBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            await boq_service.riordina_voci(conn, tenant["id"], computo_id, body.ordine)
            return {"ok": True}

    @api.post("/computi/{computo_id}/duplica")
    async def dup_computo(request: Request, computo_id: str, tipo: Optional[str] = None):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.duplica_computo(conn, tenant["id"], computo_id, tipo=tipo)

    @api.post("/computi/{computo_id}/valida-ai")
    async def valida_ai(request: Request, computo_id: str, body: ValidaAiBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            n = await boq_service.valida_voci_ai(
                conn, tenant["id"], computo_id, voce_ids=body.voce_ids
            )
            return {"validate": n}

    @api.post("/computi/{computo_id}/conferma")
    async def conferma(request: Request, computo_id: str):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.conferma_computo(conn, tenant["id"], computo_id)

    @api.post("/computi/{computo_id}/preventivo")
    async def to_preventivo(request: Request, computo_id: str, body: PreventivoBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.computo_to_preventivo(
                conn, tenant["id"], computo_id, sconto=body.sconto, iva=body.iva
            )

    @api.post("/computi/da-ai")
    async def da_ai(request: Request, body: GeneraDaAiBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await mapping_engine.genera_computo_da_ai(
                conn,
                tenant["id"],
                analisi_ai=body.analisi_ai,
                lead_id=body.lead_id,
                config_lead=body.config_lead,
                prezzario_id=body.prezzario_id,
            )

    @api.post("/metriche/estrai")
    async def metriche_estrai(request: Request, body: GeneraDaAiBody):
        await _user(request, db)
        m = estrai_metriche(body.analisi_ai)
        return m.model_dump()

    @api.get("/preventivi/{preventivo_id}/pdf")
    async def preventivo_pdf(request: Request, preventivo_id: str):
        from fastapi.responses import Response
        import json

        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            row = await conn.fetchrow(
                "select * from public.preventivi where id = $1::uuid and tenant_id = $2::uuid",
                preventivo_id,
                tenant["id"],
            )
            if not row:
                raise HTTPException(status_code=404, detail="Preventivo non trovato")
            prev = dict(row)
            if isinstance(prev.get("snapshot_voci"), str):
                prev["snapshot_voci"] = json.loads(prev["snapshot_voci"])
            pdf = genera_pdf_preventivo(prev, tenant)
            return Response(
                content=pdf,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'inline; filename="{prev.get("numero") or "preventivo"}.pdf"'
                },
            )
