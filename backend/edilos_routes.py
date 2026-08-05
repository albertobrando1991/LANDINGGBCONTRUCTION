"""API EdilOS Fase 1: prezzario, computi, mapping AI, preventivi."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, EmailStr, Field, TypeAdapter, ValidationError

import auth as authlib
import boq_service
import db as db_pg
import email_service
import lead_bridge
import mapping_engine
import prezzario_service
import tenancy
from engines.metriche import estrai_metriche
from preventivo_pdf import genera_pdf_preventivo

router = APIRouter(tags=["edilos"])
logger = logging.getLogger("gb.edilos")
EMAIL_ADDRESS_ADAPTER = TypeAdapter(EmailStr)


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
    rendi_default: bool = True


class WizardBody(BaseModel):
    correzioni: Dict[str, float] = Field(default_factory=dict)


class RipristinaBody(BaseModel):
    prezzario_id: Optional[str] = None
    voce_ids: Optional[List[str]] = None
    categoria: Optional[str] = None


class CreaComputoBody(BaseModel):
    lead_id: Optional[str] = None
    cantiere_id: Optional[str] = None
    prezzario_id: Optional[str] = None
    tipo: str = "estimativo"


class AggiungiVoceBody(BaseModel):
    prezzario_voce_id: str
    qta: float = Field(default=1, ge=0)


class AggiornaVoceBody(BaseModel):
    qta: Optional[float] = Field(default=None, ge=0)
    prezzo_unitario: Optional[float] = Field(default=None, ge=0)
    descrizione: Optional[str] = Field(default=None, min_length=1, max_length=500)
    validata_umano: Optional[bool] = None


class RiordinaBody(BaseModel):
    ordine: List[str]


class PreventivoBody(BaseModel):
    sconto: float = 0
    iva: float = 10


class PreventivoStatoBody(BaseModel):
    stato: Literal["accettato", "rifiutato", "scaduto"]


class PreventivoInviaBody(BaseModel):
    destinatario: Optional[EmailStr] = None
    oggetto: Optional[str] = Field(default=None, min_length=1, max_length=200)
    messaggio: Optional[str] = Field(default=None, min_length=1, max_length=5000)


class GeneraDaAiBody(BaseModel):
    lead_id: Optional[str] = None
    prezzario_id: Optional[str] = None
    analisi_ai: Dict[str, Any] = Field(default_factory=dict)
    config_lead: Optional[Dict[str, Any]] = None


class ValidaAiBody(BaseModel):
    voce_ids: Optional[List[str]] = None


def register_edilos_routes(api: APIRouter, db, get_tenant_conn):
    """Monta le route su un APIRouter esistente (prefix /api)."""

    def actor_name(user: dict) -> str:
        return str(
            user.get("name")
            or user.get("nome")
            or user.get("email")
            or "staff"
        )

    @api.get("/tenant/config")
    async def tenant_config(request: Request):
        slug = tenancy.extract_tenant_slug(request)
        async with db_pg.public_conn() as conn:
            # La policy RLS tenants_public_brand limita gia' la lettura ai
            # tenant attivi; `anon` puo' selezionare soltanto queste colonne.
            row = await conn.fetchrow(
                """
                select slug, ragione_sociale, theme, contatti
                from public.tenants
                where slug = $1
                """,
                slug,
            )
        if not row:
            raise HTTPException(status_code=404, detail="Tenant non trovato")
        return tenancy.public_tenant_config(row)

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
                conn,
                tenant["id"],
                prezzario_id,
                body.nome,
                rendi_default=body.rendi_default,
            )

    @api.post("/prezzario/{prezzario_id}/default")
    async def prezzario_default(request: Request, prezzario_id: str):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await prezzario_service.imposta_default(
                conn, tenant["id"], prezzario_id
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
    @api.get("/computi")
    async def lista_computi(request: Request):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.lista_computi(conn, tenant["id"])

    @api.post("/computi")
    async def crea_computo(request: Request, body: CreaComputoBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            lead_id = await lead_bridge.resolve_lead_id(
                conn, db, tenant["id"], body.lead_id
            )
            return await boq_service.crea_computo(
                conn,
                tenant["id"],
                lead_id=lead_id,
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

    @api.delete("/computi/voci/{voce_id}")
    async def delete_voce(request: Request, voce_id: str):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.rimuovi_voce(conn, tenant["id"], voce_id)

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
                conn,
                tenant["id"],
                computo_id,
                sconto=body.sconto,
                iva=body.iva,
                autore=actor_name(user),
            )

    @api.post("/computi/da-ai")
    async def da_ai(request: Request, body: GeneraDaAiBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            lead_id = await lead_bridge.resolve_lead_id(
                conn, db, tenant["id"], body.lead_id
            )
            return await mapping_engine.genera_computo_da_ai(
                conn,
                tenant["id"],
                analisi_ai=body.analisi_ai,
                lead_id=lead_id,
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

    @api.get("/preventivi/{preventivo_id}/eventi")
    async def preventivo_eventi(request: Request, preventivo_id: str):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.lista_eventi_preventivo(
                conn, tenant["id"], preventivo_id
            )

    @api.patch("/preventivi/{preventivo_id}/stato")
    async def preventivo_stato(
        request: Request, preventivo_id: str, body: PreventivoStatoBody
    ):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.aggiorna_stato_preventivo(
                conn,
                tenant["id"],
                preventivo_id,
                body.stato,
                autore=actor_name(user),
            )

    @api.post("/preventivi/{preventivo_id}/invia")
    async def preventivo_invia(
        request: Request, preventivo_id: str, body: PreventivoInviaBody
    ):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            preventivo = await boq_service.get_preventivo(
                conn, tenant["id"], preventivo_id, for_update=True
            )
            if preventivo["stato"] != "bozza":
                raise HTTPException(
                    status_code=409,
                    detail="Puoi inviare soltanto un preventivo in bozza",
                )
            lead = None
            if preventivo.get("lead_id"):
                lead = await conn.fetchrow(
                    """
                    select nome, email from public.leads
                    where id = $1::uuid and tenant_id = $2::uuid
                    """,
                    preventivo["lead_id"],
                    tenant["id"],
                )
            raw_recipient = str(
                body.destinatario or (lead["email"] if lead else "") or ""
            ).strip()
            try:
                destinatario = str(
                    EMAIL_ADDRESS_ADAPTER.validate_python(raw_recipient)
                )
            except ValidationError:
                raise HTTPException(
                    status_code=400, detail="Email destinatario non valida"
                )

            ragione_sociale = tenant.get("ragione_sociale") or "GB Construction"
            nome_cliente = str((lead["nome"] if lead else "") or "Cliente").strip()
            oggetto = (
                (body.oggetto or "").strip()
                or f"Preventivo {preventivo['numero']} - {ragione_sociale}"
            )
            messaggio = (
                (body.messaggio or "").strip()
                or (
                    f"Gentile {nome_cliente},\n\n"
                    f"in allegato trova il preventivo {preventivo['numero']} "
                    f"preparato da {ragione_sociale}.\n\n"
                    "Per qualsiasi chiarimento può rispondere direttamente a questa email.\n\n"
                    f"Cordiali saluti,\n{ragione_sociale}"
                )
            )
            pdf_data = dict(preventivo)
            pdf_data["stato"] = "inviato"
            pdf = genera_pdf_preventivo(pdf_data, tenant)
            idempotency_seed = (
                f"{tenant['id']}:{preventivo_id}:invio-iniziale".encode("utf-8")
            )
            idempotency_hash = hashlib.sha256(idempotency_seed).hexdigest()
            idempotency_key = f"preventivo-{idempotency_hash}"
            try:
                delivery = await asyncio.to_thread(
                    email_service.send_custom_email,
                    to_email=destinatario,
                    subject=oggetto,
                    body_text=messaggio,
                    attachments=[
                        {
                            "filename": f"{preventivo['numero']}.pdf",
                            "content": pdf,
                            "mime": "application/pdf",
                        }
                    ],
                    reply_to=email_service._notification_email(),
                    idempotency_key=idempotency_key,
                )
            except Exception as exc:
                logger.exception(
                    "Invio preventivo %s non riuscito: %s", preventivo_id, exc
                )
                raise HTTPException(
                    status_code=502,
                    detail="Invio preventivo non riuscito. Riprova più tardi.",
                )
            updated = await boq_service.registra_invio_preventivo(
                conn,
                tenant["id"],
                preventivo,
                destinatario=destinatario,
                oggetto=oggetto,
                provider=delivery["transport"],
                provider_message_id=delivery.get("message_id") or "",
                idempotency_key=idempotency_key,
                autore=actor_name(user),
            )
            return {
                "ok": True,
                "preventivo": updated,
                "destinatario": destinatario,
                "provider": delivery["transport"],
            }
