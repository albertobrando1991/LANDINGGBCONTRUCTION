"""Operazioni Supabase Auth privilegiate per gli inviti al portale cliente."""

from __future__ import annotations

import os

from fastapi import HTTPException

import email_service


def _supabase_credentials() -> tuple[str, str]:
    url = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    secret = (
        os.environ.get("SUPABASE_SECRET_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or ""
    ).strip()
    if not url or not secret:
        raise HTTPException(
            status_code=503,
            detail="Inviti cliente non configurati sul server",
        )
    return url, secret


def _supabase_admin():
    url, secret = _supabase_credentials()
    from supabase import ClientOptions, create_client

    return create_client(
        url,
        secret,
        options=ClientOptions(auto_refresh_token=False, persist_session=False),
    )


def _action_link(response) -> str:
    properties = getattr(response, "properties", None)
    return str(getattr(properties, "action_link", "") or "").strip()


def _send_gb_invite(
    *, email: str, nome: str | None, action_url: str, context: str
) -> None:
    try:
        email_service.send_client_portal_invite(
            to_email=email,
            nome=nome,
            action_url=action_url,
            context=context,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Invito creato ma email GB non consegnata; riprova tra poco",
        ) from exc


def find_or_invite_user(
    email: str, nome: str | None = None, *, context: str = "preventivo"
):
    """Trova/crea l'utente Auth e invia soltanto l'email ufficiale GB."""

    if not email_service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Servizio email ufficiale GB non configurato",
        )

    admin = _supabase_admin().auth.admin
    normalized = email.strip().lower()
    public_url = (
        os.environ.get("APP_PUBLIC_URL") or "https://app.gbconstruction.it"
    ).rstrip("/")
    set_password_url = f"{public_url}/set-password"
    portal_url = f"{public_url}/portal"
    users = admin.list_users(page=1, per_page=1000)
    if hasattr(users, "users"):
        users = users.users
    for user in users or []:
        if str(getattr(user, "email", "") or "").strip().lower() == normalized:
            confirmed = bool(
                getattr(user, "email_confirmed_at", None)
                or getattr(user, "confirmed_at", None)
            )
            if confirmed:
                _send_gb_invite(
                    email=normalized,
                    nome=nome,
                    action_url=portal_url,
                    context=context,
                )
                return user, False

            link = admin.generate_link(
                {
                    "type": "magiclink",
                    "email": normalized,
                    "options": {
                        "redirect_to": set_password_url,
                        "data": {"name": (nome or "").strip() or normalized},
                    },
                }
            )
            action_url = _action_link(link)
            if not action_url:
                raise HTTPException(
                    status_code=502,
                    detail="Supabase non ha generato il link di accesso cliente",
                )
            _send_gb_invite(
                email=normalized,
                nome=nome,
                action_url=action_url,
                context=context,
            )
            return user, False

    generated = admin.generate_link(
        {
            "type": "invite",
            "email": normalized,
            "options": {
                "redirect_to": set_password_url,
                "data": {"name": (nome or "").strip() or normalized},
            },
        },
    )
    action_url = _action_link(generated)
    if not action_url:
        raise HTTPException(
            status_code=502,
            detail="Supabase non ha generato il link di invito cliente",
        )
    _send_gb_invite(
        email=normalized,
        nome=nome,
        action_url=action_url,
        context=context,
    )
    user = getattr(generated, "user", None) or generated
    return user, True


def send_password_reset(email: str) -> bool:
    """Genera un recovery link senza usare le email standard di Supabase."""

    if not email_service.is_configured():
        raise RuntimeError("Servizio email ufficiale GB non configurato")

    normalized = email.strip().lower()
    admin = _supabase_admin().auth.admin
    users = admin.list_users(page=1, per_page=1000)
    if hasattr(users, "users"):
        users = users.users
    user = next(
        (
            item
            for item in users or []
            if str(getattr(item, "email", "") or "").strip().lower() == normalized
        ),
        None,
    )
    if not user:
        return False

    public_url = (
        os.environ.get("APP_PUBLIC_URL") or "https://app.gbconstruction.it"
    ).rstrip("/")
    generated = admin.generate_link(
        {
            "type": "recovery",
            "email": normalized,
            "options": {"redirect_to": f"{public_url}/set-password"},
        }
    )
    action_url = _action_link(generated)
    if not action_url:
        raise RuntimeError("Supabase non ha generato il link di recupero")

    metadata = getattr(user, "user_metadata", None) or {}
    email_service.send_client_password_reset(
        to_email=normalized,
        nome=metadata.get("name") if isinstance(metadata, dict) else None,
        action_url=action_url,
    )
    return True
