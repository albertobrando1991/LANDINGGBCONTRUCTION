"""Risoluzione tenant da header/hostname e controllo ruoli."""
from __future__ import annotations

import os
import re
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, Request

BASE_DOMAIN = os.environ.get("APP_BASE_DOMAIN", "alantis.it")
DEFAULT_TENANT_SLUG = os.environ.get("DEFAULT_TENANT_SLUG", "gbconstruction")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$")
PUBLIC_TENANT_FIELDS = ("slug", "ragione_sociale", "theme", "contatti")


def extract_tenant_slug(request: Request) -> Optional[str]:
    header = (request.headers.get("X-Tenant-Slug") or "").strip().lower()
    if header and SLUG_RE.match(header):
        return header

    host = (request.headers.get("Host") or request.url.hostname or "").split(":")[0].lower()
    base = BASE_DOMAIN.lower()
    if host.endswith("." + base):
        slug = host[: -(len(base) + 1)]
        if slug and "." not in slug and SLUG_RE.match(slug):
            return slug

    # Landing GB: hostname gbconstruction.it / www / api non sono slug tenant
    if "gbconstruction" in host:
        return DEFAULT_TENANT_SLUG

    q = (request.query_params.get("tenant") or "").strip().lower()
    if q and SLUG_RE.match(q):
        return q
    return DEFAULT_TENANT_SLUG


def tenants_from_user(user: dict) -> list[dict]:
    """Lista tenant dal claim Supabase app_tenants o dal campo legacy."""
    raw = user.get("app_tenants") or user.get("tenants") or []
    if isinstance(raw, str):
        return []
    out = []
    for item in raw:
        if isinstance(item, dict):
            tid = item.get("t") or item.get("tenant_id") or item.get("id")
            role = item.get("r") or item.get("role") or "staff"
            if tid:
                out.append({"tenant_id": str(tid), "role": str(role)})
    return out


def public_tenant_config(row: Any) -> dict:
    """Serializza soltanto i campi brand consentiti dall'endpoint pubblico."""
    source = dict(row or {})
    return {key: source.get(key) for key in PUBLIC_TENANT_FIELDS}


async def current_tenant(request: Request, user: dict, conn=None) -> dict:
    """Risolve il tenant da header X-Tenant-Slug oppure da hostname
    <slug>.alantis.it. Verifica che l'utente sia membro, 403 altrimenti."""
    slug = extract_tenant_slug(request)
    memberships = tenants_from_user(user)

    if conn is None:
        # fallback senza Postgres: usa solo claim JWT
        if not memberships:
            raise HTTPException(status_code=403, detail="Nessun tenant associato all'utente")
        if slug:
            # senza DB non possiamo risolvere lo slug → richiedi claim con slug o id
            for m in memberships:
                if m.get("slug") == slug or m.get("tenant_id") == slug:
                    return {"id": m["tenant_id"], "slug": slug, "role": m["role"]}
            raise HTTPException(status_code=403, detail="Non sei membro di questo tenant")
        m0 = memberships[0]
        return {"id": m0["tenant_id"], "slug": slug or "", "role": m0["role"]}

    if slug:
        row = await conn.fetchrow(
            "select id, slug, ragione_sociale, theme, contatti, piano, attivo "
            "from public.tenants where slug = $1 and attivo = true",
            slug,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Tenant non trovato")
        uid = user.get("supabase_user_id") or user.get("id") or user.get("sub")
        member = await conn.fetchrow(
            "select role from public.tenant_members where tenant_id = $1 and user_id = $2::uuid",
            row["id"],
            uid,
        )
        if not member:
            raise HTTPException(status_code=403, detail="Non sei membro di questo tenant")
        return {
            "id": str(row["id"]),
            "slug": row["slug"],
            "ragione_sociale": row["ragione_sociale"],
            "theme": row["theme"],
            "contatti": row["contatti"],
            "piano": row["piano"],
            "role": str(member["role"]),
        }

    # nessun slug: primo membership
    uid = user.get("supabase_user_id") or user.get("id") or user.get("sub")
    row = await conn.fetchrow(
        """
        select t.id, t.slug, t.ragione_sociale, t.theme, t.contatti, t.piano, m.role
        from public.tenant_members m
        join public.tenants t on t.id = m.tenant_id
        where m.user_id = $1::uuid and t.attivo = true
        order by m.created_at
        limit 1
        """,
        uid,
    )
    if not row:
        raise HTTPException(status_code=403, detail="Nessun tenant associato all'utente")
    return {
        "id": str(row["id"]),
        "slug": row["slug"],
        "ragione_sociale": row["ragione_sociale"],
        "theme": row["theme"],
        "contatti": row["contatti"],
        "piano": row["piano"],
        "role": str(row["role"]),
    }


async def require_tenant_role(request: Request, user: dict, roles: list[str], conn=None) -> dict:
    tenant = await current_tenant(request, user, conn=conn)
    if tenant.get("role") not in roles:
        raise HTTPException(status_code=403, detail="Permessi insufficienti per questa operazione")
    return tenant


def uuid_or_400(value: str, label: str = "ID") -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{label} non valido")
