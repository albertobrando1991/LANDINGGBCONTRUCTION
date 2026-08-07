"""Operazioni Supabase Auth privilegiate per gli inviti al portale cliente."""

from __future__ import annotations

import os

from fastapi import HTTPException


def _supabase_admin():
    url = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    secret = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not secret:
        raise HTTPException(
            status_code=503,
            detail="Inviti cliente non configurati sul server",
        )
    from supabase import create_client
    from supabase.lib.client_options import ClientOptions

    return create_client(
        url,
        secret,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )


def find_or_invite_user(email: str, nome: str | None = None):
    """Trova un utente Auth o invia un invito con redirect al portale."""

    admin = _supabase_admin().auth.admin
    normalized = email.strip().lower()
    users = admin.list_users(page=1, per_page=1000)
    if hasattr(users, "users"):
        users = users.users
    for user in users or []:
        if str(getattr(user, "email", "") or "").strip().lower() == normalized:
            return user, False
    public_url = (
        os.environ.get("APP_PUBLIC_URL") or "https://app.gbconstruction.it"
    ).rstrip("/")
    invited = admin.invite_user_by_email(
        normalized,
        {
            "redirect_to": f"{public_url}/set-password",
            "data": {"name": (nome or "").strip() or normalized},
        },
    )
    user = getattr(invited, "user", None) or invited
    return user, True
