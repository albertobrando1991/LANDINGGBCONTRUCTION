"""Bridge JWT legacy (Mongo) → tenant GB Construction su Postgres/RLS.

Questa landing resta su dominio GB. Il tenant di default è sempre
`gbconstruction`. Gli utenti staff Mongo sono mappati a UUID fissi
presenti in seed (auth.users + tenant_members).
"""
from __future__ import annotations

import os
from typing import Any, Optional

# Allineati a supabase/seed.sql
GB_TENANT_ID = "a0000000-0000-4000-8000-000000000001"
GB_TENANT_SLUG = os.environ.get("DEFAULT_TENANT_SLUG", "gbconstruction")

# email lowercase → (supabase_user_uuid, tenant_role)
LEGACY_STAFF_MAP: dict[str, tuple[str, str]] = {
    "admin@gbconstruction.it": ("f1000000-0000-4000-8000-000000000001", "owner"),
    "info@gbconstruction.it": ("3573af1c-1be2-4296-8c59-cb5bd2ed3eb3", "admin"),
    "info@alantis.it": ("cd543ef2-cbae-49fc-bd34-db5739be0fda", "admin"),
    "staff@gbconstruction.it": ("f1000000-0000-4000-8000-000000000002", "staff"),
    "operations@gbconstruction.it": ("f1000000-0000-4000-8000-000000000003", "operations"),
}

LEGACY_ROLE_MAP: dict[str, tuple[str, str]] = {
    "admin": ("f1000000-0000-4000-8000-000000000001", "owner"),
    "staff": ("f1000000-0000-4000-8000-000000000002", "staff"),
    "operations": ("f1000000-0000-4000-8000-000000000003", "operations"),
}


def map_legacy_user(user: dict) -> dict:
    """Arricchisce l'utente Mongo con id Supabase e claim tenant GB."""
    if not user:
        return user
    if user.get("auth_provider") == "supabase" and user.get("app_tenants"):
        return user

    email = (user.get("email") or "").strip().lower()
    mapped = LEGACY_STAFF_MAP.get(email)
    role_mongo = (user.get("role") or "staff").lower()

    if mapped:
        supabase_uid, tenant_role = mapped
    else:
        # Fallback su identita tecniche gia presenti nel seed: il ruolo deriva
        # dal JWT legacy firmato e nessun ObjectId raggiunge PostgreSQL.
        supabase_uid, tenant_role = LEGACY_ROLE_MAP.get(
            role_mongo, LEGACY_ROLE_MAP["staff"]
        )

    out = dict(user)
    out["supabase_user_id"] = str(supabase_uid)
    # per current_tenant / membership checks
    out["id"] = str(supabase_uid)
    out["sub"] = str(supabase_uid)
    out["app_tenants"] = [{"t": GB_TENANT_ID, "r": tenant_role, "slug": GB_TENANT_SLUG}]
    out.setdefault("auth_provider", out.get("auth_provider") or "legacy")
    return out


def claims_for_user(user: dict) -> dict[str, Any]:
    """Claim JWT sintetici per SET request.jwt.claims (RLS auth.uid())."""
    user = map_legacy_user(user)
    sub = str(user.get("supabase_user_id") or user.get("sub") or user.get("id") or "")
    return {
        "sub": sub,
        "role": "authenticated",
        "email": user.get("email"),
        "app_tenants": user.get("app_tenants") or [],
        "aud": "authenticated",
    }


def default_tenant_slug(explicit: Optional[str] = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip().lower()
    return GB_TENANT_SLUG
