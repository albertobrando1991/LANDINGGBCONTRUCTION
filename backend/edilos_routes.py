"""API EdilOS: prezzario, computi, preventivi, libretto misure e SAL."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    File,
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
import boq_service
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
    importo: Optional[Decimal] = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    data_scadenza: date
    note: Optional[str] = Field(default=None, max_length=2000)


class ScadenzaPatchBody(BaseModel):
    stato: Optional[Literal["aperta", "completata", "annullata"]] = None
    completata_at: Optional[datetime] = None
    note: Optional[str] = Field(default=None, max_length=2000)


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

    def require_economics_role(tenant: dict) -> None:
        if tenant.get("role") not in economics_service.ECONOMICS_ROLES:
            raise HTTPException(
                status_code=403,
                detail="Permessi insufficienti per i dati economici",
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
    ):
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
            return await boq_service.crea_variante(
                conn, tenant["id"], computo_id
            )

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
    async def economics_dashboard(
        request: Request, cantiere_id: Optional[str] = None
    ):
        user = await _user(request, db)
        cantiere_uuid = (
            str(tenancy.uuid_or_400(cantiere_id, "Cantiere"))
            if cantiere_id
            else None
        )
        async with get_tenant_conn(request, user) as (conn, tenant):
            require_economics_role(tenant)
            return await economics_service.get_dashboard(
                conn, tenant["id"], cantiere_id=cantiere_uuid
            )

    @api.post("/economics/fornitori", status_code=201)
    async def economics_crea_fornitore(
        request: Request, body: FornitoreCreateBody
    ):
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
    async def economics_crea_scadenza(
        request: Request, body: ScadenzaCreateBody
    ):
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
    async def economics_export_csv(
        request: Request, cantiere_id: Optional[str] = None
    ):
        user = await _user(request, db)
        cantiere_uuid = (
            str(tenancy.uuid_or_400(cantiere_id, "Cantiere"))
            if cantiere_id
            else None
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
                destinatario = str(EMAIL_ADDRESS_ADAPTER.validate_python(raw_recipient))
            except ValidationError:
                raise HTTPException(
                    status_code=400, detail="Email destinatario non valida"
                )

            ragione_sociale = tenant.get("ragione_sociale") or "GB Construction"
            nome_cliente = str((lead["nome"] if lead else "") or "Cliente").strip()
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
