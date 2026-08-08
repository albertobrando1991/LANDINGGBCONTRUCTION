"""API EdilOS: prezzario, computi, preventivi, libretto misure e SAL."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
)

import auth as authlib
import acca_pdf_parser
import cronoprogramma
import boq_service
import client_portal_service
import db as db_pg
import email_service
import economics_service
import lead_bridge
import libretto_service
import mapping_engine
import prezzario_service
import sal_service
import tenancy
from engines.metriche import estrai_metriche
from contratto_appalto_pdf import genera_pdf_contratto, numero_contratto
from preventivo_pdf import genera_pdf_preventivo
from sal_pdf import genera_pdf_sal

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


class PrezzarioVoceCreateBody(BaseModel):
    codice: Optional[str] = Field(default=None, max_length=100)
    super_categoria: str = Field(min_length=1, max_length=200)
    categoria: str = Field(min_length=1, max_length=200)
    sub_categoria: Optional[str] = Field(default=None, max_length=200)
    descrizione: str = Field(min_length=2, max_length=1000)
    um: Literal["mq", "ml", "mc", "cad", "corpo", "kg", "h", "n"]
    prezzo_unitario: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    tipo: Literal["a_misura", "a_corpo"] = "a_misura"


class PrezzarioVocePatchBody(BaseModel):
    codice: Optional[str] = Field(default=None, max_length=100)
    super_categoria: Optional[str] = Field(default=None, min_length=1, max_length=200)
    categoria: Optional[str] = Field(default=None, min_length=1, max_length=200)
    sub_categoria: Optional[str] = Field(default=None, max_length=200)
    descrizione: Optional[str] = Field(default=None, min_length=2, max_length=1000)
    um: Optional[Literal["mq", "ml", "mc", "cad", "corpo", "kg", "h", "n"]] = None
    prezzo_unitario: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    tipo: Optional[Literal["a_misura", "a_corpo"]] = None
    attiva: Optional[bool] = None


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


class AggiungiVoceLiberaBody(BaseModel):
    descrizione: str = Field(min_length=1, max_length=500)
    um: str = Field(min_length=1, max_length=50)
    qta: float = Field(default=1, ge=0)
    prezzo_unitario: float = Field(ge=0)


class AggiornaVoceBody(BaseModel):
    qta: Optional[float] = Field(default=None, ge=0)
    prezzo_unitario: Optional[float] = Field(default=None, ge=0)
    descrizione: Optional[str] = Field(default=None, min_length=1, max_length=500)
    validata_umano: Optional[bool] = None
    fase: Optional[str] = Field(default=None, min_length=1, max_length=120)
    # Stringa vuota ammessa: azzera l'area assegnata alla voce.
    area: Optional[str] = Field(default=None, max_length=120)


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


class CreaMisuraBody(BaseModel):
    client_uuid: UUID
    data_misura: date
    qta: Decimal = Field(max_digits=12, decimal_places=3)
    computo_voce_id: Optional[UUID] = None
    descrizione: Optional[str] = Field(default=None, max_length=1000)
    parti: int = Field(default=1, ge=1)
    lunghezza: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=10, decimal_places=3
    )
    larghezza: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=10, decimal_places=3
    )
    altezza: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=10, decimal_places=3
    )
    foto_paths: List[str] = Field(default_factory=list, max_length=20)

    @field_validator("qta")
    @classmethod
    def qta_non_zero(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("La quantita non puo essere zero")
        return value

    @field_validator("descrizione")
    @classmethod
    def normalizza_descrizione(cls, value: Optional[str]) -> Optional[str]:
        normalized = (value or "").strip()
        return normalized or None

    @field_validator("foto_paths")
    @classmethod
    def valida_foto_paths(cls, values: List[str]) -> List[str]:
        normalized = [str(value).strip() for value in values]
        if any(not value or len(value) > 500 for value in normalized):
            raise ValueError("Percorso foto non valido")
        if len(set(normalized)) != len(normalized):
            raise ValueError("La stessa foto non puo essere indicata piu volte")
        return normalized


class GeneraSalBody(BaseModel):
    periodo_da: date
    periodo_a: date


class SalStatoBody(BaseModel):
    stato: Literal["emesso", "approvato"]


class FornitoreCreateBody(BaseModel):
    ragione_sociale: str = Field(min_length=2, max_length=200)
    piva: Optional[str] = Field(default=None, max_length=32)
    codice_fiscale: Optional[str] = Field(default=None, max_length=32)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(default=None, max_length=40)
    indirizzo: Optional[str] = Field(default=None, max_length=300)
    note: Optional[str] = Field(default=None, max_length=2000)


class FornitorePatchBody(BaseModel):
    ragione_sociale: Optional[str] = Field(default=None, min_length=2, max_length=200)
    piva: Optional[str] = Field(default=None, max_length=32)
    codice_fiscale: Optional[str] = Field(default=None, max_length=32)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(default=None, max_length=40)
    indirizzo: Optional[str] = Field(default=None, max_length=300)
    note: Optional[str] = Field(default=None, max_length=2000)
    attivo: Optional[bool] = None


class SpesaCreateBody(BaseModel):
    cantiere_id: UUID
    fornitore_id: Optional[UUID] = None
    categoria: Literal[
        "materiali",
        "manodopera",
        "subappalto",
        "noleggio",
        "trasporto",
        "utenze",
        "professionisti",
        "altro",
    ] = "altro"
    descrizione: str = Field(min_length=2, max_length=500)
    numero_documento: Optional[str] = Field(default=None, max_length=100)
    data_documento: date = Field(default_factory=date.today)
    imponibile: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    iva_percentuale: Decimal = Field(default=Decimal("22"), ge=0, le=100)
    stato: Literal["registrata", "pagata", "annullata"] = "registrata"
    data_pagamento: Optional[date] = None
    allegato_path: Optional[str] = Field(default=None, max_length=1000)
    note: Optional[str] = Field(default=None, max_length=2000)


class SpesaPatchBody(BaseModel):
    stato: Optional[Literal["registrata", "pagata", "annullata"]] = None
    data_pagamento: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class IncassoCreateBody(BaseModel):
    cantiere_id: UUID
    sal_id: Optional[UUID] = None
    descrizione: str = Field(min_length=2, max_length=500)
    importo: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    data_prevista: date
    data_incasso: Optional[date] = None
    stato: Literal["previsto", "incassato", "annullato"] = "previsto"
    metodo: Optional[str] = Field(default=None, max_length=100)
    note: Optional[str] = Field(default=None, max_length=2000)


class IncassoPatchBody(BaseModel):
    stato: Optional[Literal["previsto", "incassato", "annullato"]] = None
    data_incasso: Optional[date] = None
    metodo: Optional[str] = Field(default=None, max_length=100)
    note: Optional[str] = Field(default=None, max_length=2000)


class ScadenzaCreateBody(BaseModel):
    cantiere_id: UUID
    spesa_id: Optional[UUID] = None
    incasso_id: Optional[UUID] = None
    tipo: Literal["incasso", "pagamento", "adempimento"]
    titolo: str = Field(min_length=2, max_length=300)
    importo: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=14, decimal_places=2
    )
    data_scadenza: date
    note: Optional[str] = Field(default=None, max_length=2000)


class ScadenzaPatchBody(BaseModel):
    stato: Optional[Literal["aperta", "completata", "annullata"]] = None
    completata_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class PortaleInvitaBody(BaseModel):
    email: EmailStr
    nome: Optional[str] = Field(default=None, max_length=200)


class PortaleCondivisioneBody(BaseModel):
    tipo: Literal["foto", "documento"]
    bucket: Literal["foto-cantiere", "documenti"]
    storage_path: str = Field(min_length=10, max_length=1000)
    titolo: str = Field(min_length=1, max_length=200)
    descrizione: Optional[str] = Field(default=None, max_length=1000)


def _request_ip(request: Request) -> str:
    candidate = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if not candidate and request.client:
        candidate = request.client.host
    try:
        return str(ipaddress.ip_address(candidate or "0.0.0.0"))
    except ValueError:
        return "0.0.0.0"


def register_edilos_routes(api: APIRouter, db, get_tenant_conn):
    """Monta le route su un APIRouter esistente (prefix /api)."""

    def actor_name(user: dict) -> str:
        return str(user.get("name") or user.get("nome") or user.get("email") or "staff")

    def require_libretto_role(tenant: dict) -> None:
        if tenant.get("role") not in libretto_service.LIBRETTO_ROLES:
            raise HTTPException(
                status_code=403,
                detail="Permessi insufficienti per il libretto di misura",
            )

    def require_sal_role(tenant: dict) -> None:
        if tenant.get("role") not in sal_service.SAL_ROLES:
            raise HTTPException(
                status_code=403,
                detail="Permessi insufficienti per la gestione SAL",
            )

    def require_prezzario_write_role(tenant: dict) -> None:
        if tenant.get("role") not in {"owner", "admin"}:
            raise HTTPException(
                status_code=403,
                detail="Permessi insufficienti per modificare il prezzario",
            )

    def require_economics_role(tenant: dict) -> None:
        if tenant.get("role") not in economics_service.ECONOMICS_ROLES:
            raise HTTPException(
                status_code=403,
                detail="Permessi insufficienti per i dati economici",
            )

    def require_client_role(tenant: dict) -> None:
        if tenant.get("role") != "client":
            raise HTTPException(status_code=403, detail="Accesso riservato al cliente")

    def require_portal_admin_role(tenant: dict) -> None:
        if tenant.get("role") not in client_portal_service.PORTAL_ADMIN_ROLES:
            raise HTTPException(
                status_code=403,
                detail="Permessi insufficienti per invitare clienti",
            )

    def require_portal_internal_role(tenant: dict) -> None:
        if tenant.get("role") not in client_portal_service.INTERNAL_ROLES:
            raise HTTPException(
                status_code=403,
                detail="Permessi insufficienti per gestire il portale",
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
    async def voci(
        request: Request,
        prezzario_id: str,
        q: Optional[str] = None,
        categoria: Optional[str] = None,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=1, le=100),
    ):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await prezzario_service.lista_voci(
                conn,
                tenant["id"],
                prezzario_id,
                q=q,
                categoria=categoria,
                page=page,
                page_size=page_size,
            )

    @api.post("/prezzario/{prezzario_id}/voci", status_code=201)
    async def crea_voce_prezzario(
        request: Request, prezzario_id: str, body: PrezzarioVoceCreateBody
    ):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_prezzario_write_role(tenant)
            return await prezzario_service.crea_voce(
                conn, tenant["id"], prezzario_id, body.model_dump()
            )

    @api.patch("/prezzario/{prezzario_id}/voci/{voce_id}")
    async def aggiorna_voce_prezzario(
        request: Request,
        prezzario_id: str,
        voce_id: str,
        body: PrezzarioVocePatchBody,
    ):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_prezzario_write_role(tenant)
            return await prezzario_service.aggiorna_voce(
                conn,
                tenant["id"],
                prezzario_id,
                voce_id,
                body.model_dump(exclude_unset=True),
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
    async def importa(
        request: Request, prezzario_id: str, file: UploadFile = File(...)
    ):
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

    @api.post("/computi/importa-pdf", status_code=201)
    async def importa_computo_pdf(
        request: Request,
        file: UploadFile = File(...),
        lead_id: Optional[str] = Form(default=None),
        cantiere_id: Optional[str] = Form(default=None),
        prezzario_id: Optional[str] = Form(default=None),
        auto_preventivo: bool = Form(default=True),
        sconto: float = Form(default=0),
        iva: float = Form(default=10),
    ):
        user = await _user(request, db)
        filename = (file.filename or "computo-acca.pdf").strip()
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Carica un file PDF")
        if sconto < 0 or sconto > 100:
            raise HTTPException(status_code=400, detail="Sconto non valido")
        if iva < 0 or iva > 100:
            raise HTTPException(status_code=400, detail="IVA non valida")
        async with get_tenant_conn(request, user) as (conn, tenant):
            if tenant.get("role") not in {"owner", "admin", "staff", "operations"}:
                raise HTTPException(
                    status_code=403,
                    detail="Permessi insufficienti per importare un computo",
                )
            data = await file.read(15 * 1024 * 1024 + 1)
            if len(data) > 15 * 1024 * 1024:
                raise HTTPException(
                    status_code=413, detail="PDF troppo grande (massimo 15 MB)"
                )
            parsed = acca_pdf_parser.parse_acca_pdf(data)
            canonical_lead_id = None
            if lead_id and lead_id.strip():
                canonical_lead_id = await lead_bridge.resolve_lead_id(
                    conn, db, tenant["id"], lead_id.strip()
                )
            canonical_cantiere_id = (
                str(tenancy.uuid_or_400(cantiere_id.strip(), "Cantiere"))
                if cantiere_id and cantiere_id.strip()
                else None
            )
            canonical_prezzario_id = (
                str(tenancy.uuid_or_400(prezzario_id.strip(), "Prezzario"))
                if prezzario_id and prezzario_id.strip()
                else None
            )
            result = await boq_service.importa_computo_acca(
                conn,
                tenant["id"],
                filename=filename[:255],
                parsed=parsed,
                lead_id=canonical_lead_id,
                cantiere_id=canonical_cantiere_id,
                prezzario_id=canonical_prezzario_id,
            )
            result["preventivo"] = None
            if auto_preventivo and result["automazione"]["pronto_preventivo"]:
                importazione = result["importazione"]
                automazione = result["automazione"]
                preventivo = await boq_service.computo_to_preventivo(
                    conn,
                    tenant["id"],
                    result["id"],
                    sconto=sconto,
                    iva=iva,
                    autore=actor_name(user),
                    consenti_computo_editabile=True,
                )
                result = await boq_service.get_computo(
                    conn, tenant["id"], result["id"]
                )
                result["importazione"] = importazione
                result["automazione"] = automazione
                result["preventivo"] = preventivo
                result["stato_flusso"] = "bozza_preventivo_creata"
            else:
                result["stato_flusso"] = (
                    "revisione_richiesta"
                    if result["automazione"]["richiede_revisione"]
                    else "computo_pronto"
                )
            return result

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

    @api.post("/computi/{computo_id}/voci-libere")
    async def add_voce_libera(
        request: Request, computo_id: str, body: AggiungiVoceLiberaBody
    ):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.aggiungi_voce_libera(
                conn,
                tenant["id"],
                computo_id,
                body.descrizione,
                body.um,
                body.qta,
                body.prezzo_unitario,
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
    async def dup_computo(
        request: Request,
        computo_id: str,
        tipo: Optional[Literal["estimativo", "esecutivo", "variante"]] = None,
    ):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.duplica_computo(
                conn, tenant["id"], computo_id, tipo=tipo
            )

    @api.post("/computi/{computo_id}/varianti")
    async def crea_variante(request: Request, computo_id: str):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.crea_variante(conn, tenant["id"], computo_id)

    @api.get("/computi/{computo_id}/confronto-variante")
    async def confronto_variante(request: Request, computo_id: str):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            return await boq_service.get_confronto_variante(
                conn, tenant["id"], computo_id
            )

    @api.post("/computi/{computo_id}/valida-ai")
    async def valida_ai(request: Request, computo_id: str, body: ValidaAiBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            n = await boq_service.valida_voci_ai(
                conn, tenant["id"], computo_id, voce_ids=body.voce_ids
            )
            return {"validate": n}

    @api.post("/computi/{computo_id}/riclassifica")
    async def riclassifica(
        request: Request, computo_id: str, forza: bool = False
    ):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            n = await boq_service.riclassifica_computo(
                conn, tenant["id"], computo_id, forza=forza
            )
            return {"riclassificate": n}

    @api.get("/computi/{computo_id}/controlli")
    async def controlli_computo(request: Request, computo_id: str):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            computo = await boq_service.get_computo(conn, tenant["id"], computo_id)
            return {
                "controlli": computo["controlli"],
                "riepilogo_fasi": computo["riepilogo_fasi"],
                "n_senza_fase": computo["n_senza_fase"],
                "cronoprogramma": cronoprogramma.stima(computo["voci"]),
            }

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

    # ---------- Libretto di misura ----------
    @api.get("/campo/cantieri")
    async def campo_cantieri(request: Request):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_libretto_role(tenant)
            return await libretto_service.lista_cantieri_campo(conn, tenant["id"])

    @api.get("/cantieri/{cantiere_id}/libretto-misure")
    async def libretto_misure(
        request: Request,
        cantiere_id: str,
        data_da: Optional[date] = None,
        data_a: Optional[date] = None,
        computo_voce_id: Optional[str] = None,
        limit: int = Query(default=100, ge=1, le=200),
    ):
        user = await _user(request, db)
        cantiere_uuid = str(tenancy.uuid_or_400(cantiere_id, "Cantiere"))
        voce_uuid = (
            str(tenancy.uuid_or_400(computo_voce_id, "Voce di computo"))
            if computo_voce_id
            else None
        )
        if data_da and data_a and data_da > data_a:
            raise HTTPException(
                status_code=400,
                detail="La data iniziale non puo essere successiva alla data finale",
            )
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_libretto_role(tenant)
            return await libretto_service.lista_misure(
                conn,
                tenant["id"],
                cantiere_uuid,
                data_da=data_da,
                data_a=data_a,
                computo_voce_id=voce_uuid,
                limit=limit,
            )

    @api.post("/cantieri/{cantiere_id}/libretto-misure", status_code=201)
    async def crea_misura(
        request: Request,
        cantiere_id: str,
        body: CreaMisuraBody,
        response: Response,
    ):
        user = await _user(request, db)
        cantiere_uuid = str(tenancy.uuid_or_400(cantiere_id, "Cantiere"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_libretto_role(tenant)
            misura, created = await libretto_service.registra_misura(
                conn,
                tenant["id"],
                cantiere_uuid,
                client_uuid=str(body.client_uuid),
                data_misura=body.data_misura,
                qta=body.qta,
                computo_voce_id=(
                    str(body.computo_voce_id) if body.computo_voce_id else None
                ),
                descrizione=body.descrizione,
                parti=body.parti,
                lunghezza=body.lunghezza,
                larghezza=body.larghezza,
                altezza=body.altezza,
                foto_paths=body.foto_paths,
            )
            response.status_code = 201 if created else 200
            return {"created": created, "misura": misura}

    # ---------- SAL ----------
    @api.get("/cantieri/{cantiere_id}/sal")
    async def cantiere_sal(request: Request, cantiere_id: str):
        user = await _user(request, db)
        cantiere_uuid = str(tenancy.uuid_or_400(cantiere_id, "Cantiere"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_sal_role(tenant)
            return await sal_service.lista_sal(conn, tenant["id"], cantiere_uuid)

    @api.post("/cantieri/{cantiere_id}/sal", status_code=201)
    async def genera_cantiere_sal(
        request: Request, cantiere_id: str, body: GeneraSalBody
    ):
        user = await _user(request, db)
        cantiere_uuid = str(tenancy.uuid_or_400(cantiere_id, "Cantiere"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_sal_role(tenant)
            return await sal_service.genera_sal(
                conn,
                tenant["id"],
                cantiere_uuid,
                periodo_da=body.periodo_da,
                periodo_a=body.periodo_a,
            )

    @api.get("/sal/{sal_id}")
    async def sal_dettaglio(request: Request, sal_id: str):
        user = await _user(request, db)
        sal_uuid = str(tenancy.uuid_or_400(sal_id, "SAL"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_sal_role(tenant)
            return await sal_service.get_sal(conn, tenant["id"], sal_uuid)

    @api.get("/sal/{sal_id}/pdf")
    async def sal_pdf(request: Request, sal_id: str):
        user = await _user(request, db)
        sal_uuid = str(tenancy.uuid_or_400(sal_id, "SAL"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_sal_role(tenant)
            documento = await sal_service.get_sal_documento(
                conn, tenant["id"], sal_uuid
            )
            pdf = genera_pdf_sal(documento)
            numero = int(documento["sal"].get("numero") or 0)
            return Response(
                content=pdf,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="SAL-{numero:02d}-con-libretto.pdf"'
                    )
                },
            )

    @api.patch("/sal/{sal_id}/stato")
    async def sal_stato(request: Request, sal_id: str, body: SalStatoBody):
        user = await _user(request, db)
        sal_uuid = str(tenancy.uuid_or_400(sal_id, "SAL"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_sal_role(tenant)
            return await sal_service.aggiorna_stato(
                conn, tenant["id"], sal_uuid, body.stato
            )

    # ---------- Economics cantiere ----------
    @api.get("/economics")
    async def economics_dashboard(request: Request, cantiere_id: Optional[str] = None):
        user = await _user(request, db)
        cantiere_uuid = (
            str(tenancy.uuid_or_400(cantiere_id, "Cantiere")) if cantiere_id else None
        )
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_economics_role(tenant)
            return await economics_service.get_dashboard(
                conn, tenant["id"], cantiere_id=cantiere_uuid
            )

    @api.post("/economics/fornitori", status_code=201)
    async def economics_crea_fornitore(request: Request, body: FornitoreCreateBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_economics_role(tenant)
            return await economics_service.crea_fornitore(
                conn, tenant["id"], body.model_dump()
            )

    @api.patch("/economics/fornitori/{fornitore_id}")
    async def economics_aggiorna_fornitore(
        request: Request, fornitore_id: str, body: FornitorePatchBody
    ):
        user = await _user(request, db)
        item_id = str(tenancy.uuid_or_400(fornitore_id, "Fornitore"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_economics_role(tenant)
            return await economics_service.aggiorna_fornitore(
                conn,
                tenant["id"],
                item_id,
                body.model_dump(exclude_unset=True),
            )

    @api.post("/economics/spese", status_code=201)
    async def economics_crea_spesa(request: Request, body: SpesaCreateBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_economics_role(tenant)
            return await economics_service.crea_spesa(
                conn, tenant["id"], body.model_dump()
            )

    @api.patch("/economics/spese/{spesa_id}")
    async def economics_aggiorna_spesa(
        request: Request, spesa_id: str, body: SpesaPatchBody
    ):
        user = await _user(request, db)
        item_id = str(tenancy.uuid_or_400(spesa_id, "Spesa"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_economics_role(tenant)
            return await economics_service.aggiorna_spesa(
                conn,
                tenant["id"],
                item_id,
                body.model_dump(exclude_unset=True),
            )

    @api.post("/economics/incassi", status_code=201)
    async def economics_crea_incasso(request: Request, body: IncassoCreateBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_economics_role(tenant)
            return await economics_service.crea_incasso(
                conn, tenant["id"], body.model_dump()
            )

    @api.patch("/economics/incassi/{incasso_id}")
    async def economics_aggiorna_incasso(
        request: Request, incasso_id: str, body: IncassoPatchBody
    ):
        user = await _user(request, db)
        item_id = str(tenancy.uuid_or_400(incasso_id, "Incasso"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_economics_role(tenant)
            return await economics_service.aggiorna_incasso(
                conn,
                tenant["id"],
                item_id,
                body.model_dump(exclude_unset=True),
            )

    @api.post("/economics/scadenze", status_code=201)
    async def economics_crea_scadenza(request: Request, body: ScadenzaCreateBody):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_economics_role(tenant)
            return await economics_service.crea_scadenza(
                conn, tenant["id"], body.model_dump()
            )

    @api.patch("/economics/scadenze/{scadenza_id}")
    async def economics_aggiorna_scadenza(
        request: Request, scadenza_id: str, body: ScadenzaPatchBody
    ):
        user = await _user(request, db)
        item_id = str(tenancy.uuid_or_400(scadenza_id, "Scadenza"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_economics_role(tenant)
            return await economics_service.aggiorna_scadenza(
                conn,
                tenant["id"],
                item_id,
                body.model_dump(exclude_unset=True),
            )

    @api.get("/economics/export.csv")
    async def economics_export_csv(request: Request, cantiere_id: Optional[str] = None):
        user = await _user(request, db)
        cantiere_uuid = (
            str(tenancy.uuid_or_400(cantiere_id, "Cantiere")) if cantiere_id else None
        )
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_economics_role(tenant)
            content = await economics_service.export_csv(
                conn, tenant["id"], cantiere_id=cantiere_uuid
            )
            return Response(
                content=content,
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": 'attachment; filename="economics-cantieri.csv"'
                },
            )

    # ---------- Portale cliente finale ----------
    @api.get("/portal")
    async def portale_cliente_dashboard(request: Request):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_client_role(tenant)
            return await client_portal_service.get_portal_dashboard(conn, tenant["id"])

    @api.post(
        "/portal/cantieri/{cantiere_id}/varianti/{variante_id}/approva",
        status_code=201,
    )
    async def portale_cliente_approva_variante(
        request: Request, cantiere_id: str, variante_id: str
    ):
        user = await _user(request, db)
        cantiere_uuid = str(tenancy.uuid_or_400(cantiere_id, "Cantiere"))
        variante_uuid = str(tenancy.uuid_or_400(variante_id, "Variante"))
        user_id = str(
            user.get("supabase_user_id") or user.get("sub") or user.get("id") or ""
        )
        user_uuid = str(tenancy.uuid_or_400(user_id, "Utente"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_client_role(tenant)
            return await client_portal_service.approva_variante(
                conn,
                tenant["id"],
                cantiere_uuid,
                variante_uuid,
                user_uuid,
                ip=_request_ip(request),
                user_agent=request.headers.get("user-agent"),
            )

    @api.get("/cantieri/{cantiere_id}/portale")
    async def cantiere_portale_admin(request: Request, cantiere_id: str):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_portal_internal_role(tenant)
            cantiere_uuid = await tenancy.resolve_cantiere_uuid(
                conn, tenant["id"], cantiere_id
            )
            return await client_portal_service.get_cantiere_portal_admin(
                conn, tenant["id"], cantiere_uuid
            )

    @api.post("/cantieri/{cantiere_id}/portale/invita", status_code=201)
    async def cantiere_portale_invita(
        request: Request, cantiere_id: str, body: PortaleInvitaBody
    ):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_portal_admin_role(tenant)
            cantiere_uuid = await tenancy.resolve_cantiere_uuid(
                conn, tenant["id"], cantiere_id
            )
            return await client_portal_service.invita_cliente(
                conn,
                tenant["id"],
                cantiere_uuid,
                email=str(body.email),
                nome=body.nome,
            )

    @api.patch("/cantieri/{cantiere_id}/portale/clienti/{client_user_id}/disattiva")
    async def cantiere_portale_disattiva(
        request: Request, cantiere_id: str, client_user_id: str
    ):
        user = await _user(request, db)
        client_uuid = str(tenancy.uuid_or_400(client_user_id, "Cliente"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_portal_admin_role(tenant)
            cantiere_uuid = await tenancy.resolve_cantiere_uuid(
                conn, tenant["id"], cantiere_id
            )
            return await client_portal_service.disattiva_cliente(
                conn, tenant["id"], cantiere_uuid, client_uuid
            )

    @api.post("/cantieri/{cantiere_id}/portale/condivisioni", status_code=201)
    async def cantiere_portale_condividi(
        request: Request, cantiere_id: str, body: PortaleCondivisioneBody
    ):
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_portal_internal_role(tenant)
            cantiere_uuid = await tenancy.resolve_cantiere_uuid(
                conn, tenant["id"], cantiere_id
            )
            return await client_portal_service.condividi_asset(
                conn,
                tenant["id"],
                cantiere_uuid,
                **body.model_dump(),
            )

    @api.delete("/cantieri/{cantiere_id}/portale/condivisioni/{condivisione_id}")
    async def cantiere_portale_revoca(
        request: Request, cantiere_id: str, condivisione_id: str
    ):
        user = await _user(request, db)
        share_uuid = str(tenancy.uuid_or_400(condivisione_id, "Condivisione"))
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_portal_internal_role(tenant)
            cantiere_uuid = await tenancy.resolve_cantiere_uuid(
                conn, tenant["id"], cantiere_id
            )
            return await client_portal_service.revoca_condivisione(
                conn, tenant["id"], cantiere_uuid, share_uuid
            )

    @api.post("/metriche/estrai")
    async def metriche_estrai(request: Request, body: GeneraDaAiBody):
        await _user(request, db)
        m = estrai_metriche(body.analisi_ai)
        return m.model_dump()

    @api.get("/preventivi/{preventivo_id}/pdf")
    async def preventivo_pdf(
        request: Request,
        preventivo_id: str,
        dettaglio: Literal["analitico", "sintetico"] = "analitico",
    ):
        from fastapi.responses import Response
        import json

        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            row = await conn.fetchrow(
                """
                select p.*,
                       coalesce(l.nome, cl.nome) as cliente_nome,
                       coalesce(l.email, cl.email) as cliente_email,
                       coalesce(l.telefono, cl.telefono) as cliente_telefono,
                       coalesce(l.indirizzo, cl.indirizzo) as cliente_indirizzo,
                       coalesce(l.citta, cl.citta) as cliente_citta,
                       ca.indirizzo as cantiere_indirizzo,
                       t.piva as tenant_piva
                from public.preventivi p
                join public.tenants t on t.id = p.tenant_id
                left join public.leads l
                  on l.id = p.lead_id and l.tenant_id = p.tenant_id
                left join public.clienti cl
                  on cl.id = p.cliente_id and cl.tenant_id = p.tenant_id
                left join public.computi co
                  on co.id = p.computo_id and co.tenant_id = p.tenant_id
                left join public.cantieri ca
                  on ca.id = co.cantiere_id and ca.tenant_id = p.tenant_id
                where p.id = $1::uuid and p.tenant_id = $2::uuid
                """,
                preventivo_id,
                tenant["id"],
            )
            if not row:
                raise HTTPException(status_code=404, detail="Preventivo non trovato")
            prev = dict(row)
            if isinstance(prev.get("snapshot_voci"), str):
                prev["snapshot_voci"] = json.loads(prev["snapshot_voci"])
            tenant_pdf = {**tenant, "piva": prev.pop("tenant_piva", None)}
            pdf = genera_pdf_preventivo(prev, tenant_pdf, dettaglio=dettaglio)
            return Response(
                content=pdf,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'inline; filename="{prev.get("numero") or "preventivo"}.pdf"'
                },
            )

    @api.get("/preventivi/{preventivo_id}/contratto/pdf")
    async def contratto_appalto_pdf(request: Request, preventivo_id: str):
        """Compila il contratto dal preventivo e applica la firma GB."""
        user = await _user(request, db)
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_portal_internal_role(tenant)
            row = await conn.fetchrow(
                """
                select p.*,
                       coalesce(l.nome, cl.nome) as cliente_nome,
                       coalesce(l.email, cl.email) as cliente_email,
                       coalesce(l.telefono, cl.telefono) as cliente_telefono,
                       coalesce(l.indirizzo, cl.indirizzo) as cliente_indirizzo,
                       coalesce(l.citta, cl.citta) as cliente_citta,
                       cl.cf as cliente_cf,
                       cl.piva as cliente_piva,
                       ca.indirizzo as cantiere_indirizzo,
                       co.stato as computo_stato,
                       t.piva as tenant_piva
                from public.preventivi p
                join public.tenants t on t.id = p.tenant_id
                left join public.leads l
                  on l.id = p.lead_id and l.tenant_id = p.tenant_id
                left join public.clienti cl
                  on cl.id = p.cliente_id and cl.tenant_id = p.tenant_id
                left join public.computi co
                  on co.id = p.computo_id and co.tenant_id = p.tenant_id
                left join public.cantieri ca
                  on ca.id = co.cantiere_id and ca.tenant_id = p.tenant_id
                where p.id = $1::uuid and p.tenant_id = $2::uuid
                """,
                preventivo_id,
                tenant["id"],
            )
            if not row:
                raise HTTPException(status_code=404, detail="Preventivo non trovato")
            preventivo = dict(row)
            if preventivo.get("computo_stato") != "confermato":
                raise HTTPException(
                    status_code=409,
                    detail="Conferma il computo prima di generare il contratto firmato",
                )
            if preventivo.get("stato") in {"rifiutato", "scaduto"}:
                raise HTTPException(
                    status_code=409,
                    detail="Non puoi generare un contratto da un preventivo chiuso",
                )
            if not preventivo.get("cliente_nome") or not preventivo.get(
                "cantiere_indirizzo"
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Completa cliente e indirizzo del cantiere prima di "
                        "generare il contratto"
                    ),
                )
            tenant_pdf = {**tenant, "piva": preventivo.pop("tenant_piva", None)}
            pdf = genera_pdf_contratto(preventivo, tenant_pdf)
            filename = numero_contratto(preventivo.get("numero"))
            return Response(
                content=pdf,
                media_type="application/pdf",
                headers={"Content-Disposition": f'inline; filename="{filename}.pdf"'},
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
            computo_stato = await conn.fetchval(
                """
                select c.stato
                from public.computi c
                where c.id = $1::uuid and c.tenant_id = $2::uuid
                """,
                preventivo["computo_id"],
                tenant["id"],
            )
            if computo_stato != "confermato":
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Il preventivo e ancora modificabile: conferma prima "
                        "le voci del computo, poi procedi con l'invio"
                    ),
                )
            contact = await conn.fetchrow(
                """
                select coalesce(l.nome, cl.nome) as nome,
                       coalesce(l.email, cl.email) as email,
                       coalesce(l.telefono, cl.telefono) as telefono,
                       coalesce(l.indirizzo, cl.indirizzo) as indirizzo,
                       coalesce(l.citta, cl.citta) as citta,
                       ca.indirizzo as cantiere_indirizzo
                from public.preventivi p
                left join public.leads l
                  on l.id = p.lead_id and l.tenant_id = p.tenant_id
                left join public.clienti cl
                  on cl.id = p.cliente_id and cl.tenant_id = p.tenant_id
                left join public.computi co
                  on co.id = p.computo_id and co.tenant_id = p.tenant_id
                left join public.cantieri ca
                  on ca.id = co.cantiere_id and ca.tenant_id = p.tenant_id
                where p.id = $1::uuid and p.tenant_id = $2::uuid
                """,
                preventivo_id,
                tenant["id"],
            )
            raw_recipient = str(
                body.destinatario or (contact["email"] if contact else "") or ""
            ).strip()
            try:
                destinatario = str(EMAIL_ADDRESS_ADAPTER.validate_python(raw_recipient))
            except ValidationError:
                raise HTTPException(
                    status_code=400, detail="Email destinatario non valida"
                )

            ragione_sociale = tenant.get("ragione_sociale") or "GB Construction"
            nome_cliente = str(
                (contact["nome"] if contact else "") or "Cliente"
            ).strip()
            oggetto = (
                body.oggetto or ""
            ).strip() or f"Preventivo {preventivo['numero']} - {ragione_sociale}"
            messaggio = (body.messaggio or "").strip() or (
                f"Gentile {nome_cliente},\n\n"
                f"in allegato trova il preventivo {preventivo['numero']} "
                f"preparato da {ragione_sociale}.\n\n"
                "Per qualsiasi chiarimento può rispondere direttamente a questa email.\n\n"
                f"Cordiali saluti,\n{ragione_sociale}"
            )
            pdf_data = dict(preventivo)
            pdf_data["stato"] = "inviato"
            if contact:
                pdf_data.update(
                    {
                        "cliente_nome": contact["nome"],
                        "cliente_email": contact["email"],
                        "cliente_telefono": contact["telefono"],
                        "cliente_indirizzo": contact["indirizzo"],
                        "cliente_citta": contact["citta"],
                        "cantiere_indirizzo": contact["cantiere_indirizzo"],
                    }
                )
            pdf = genera_pdf_preventivo(pdf_data, tenant)
            idempotency_seed = f"{tenant['id']}:{preventivo_id}:invio-iniziale".encode(
                "utf-8"
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
