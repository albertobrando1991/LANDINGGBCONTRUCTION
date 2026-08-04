"""Accesso Postgres/Supabase con RLS attiva anche lato server."""
from __future__ import annotations

import inspect
import json
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


def resolve_db_url() -> str | None:
    """DSN Postgres Supabase. Alias supportati (ordine di priorità):
    CONNECTION_STRING_SUPABASE | SUPABASE_DB_URL | DATABASE_URL
    """
    for key in (
        "CONNECTION_STRING_SUPABASE",
        "SUPABASE_DB_URL",
        "DATABASE_URL",
    ):
        val = (os.environ.get(key) or "").strip().strip('"').strip("'")
        if val:
            return val
    return None


def _prepare_asyncpg_dsn(dsn: str) -> tuple[str, dict]:
    """Normalizza DSN Supabase per asyncpg (ssl, rimozione query libpq non supportate)."""
    import re
    import ssl
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    # SQLAlchemy-style prefixes
    dsn = dsn.replace("postgres://", "postgresql://", 1)
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    dsn = dsn.replace("postgresql+psycopg2://", "postgresql://", 1)

    parsed = urlparse(dsn)
    qs = parse_qs(parsed.query)
    kwargs: dict = {}

    host = (parsed.hostname or "").lower()
    is_supabase = "supabase.co" in host or "supabase.com" in host
    sslmode = (qs.get("sslmode") or qs.get("ssl") or [None])[0]
    want_ssl = is_supabase or (sslmode in ("require", "verify-full", "verify-ca", "true", "1"))

    # asyncpg non usa sslmode= nella query come libpq: togli e passa ssl=
    for k in list(qs.keys()):
        if k.lower() in ("sslmode", "ssl", "channel_binding"):
            qs.pop(k, None)

    clean = parsed._replace(query=urlencode({k: v[0] for k, v in qs.items()}))
    clean_dsn = urlunparse(clean)
    # rimuovi ? vuoto
    clean_dsn = re.sub(r"\?$", "", clean_dsn)

    if want_ssl:
        ctx = ssl.create_default_context()
        # sslmode=require (libpq): cifratura obbligatoria, senza verifica cert.
        # Utile su reti con TLS inspection / solo pooler IPv4, o se CA locale è incompleta.
        # Preferire verify-full in produzione quando possibile.
        insecure = (
            (sslmode or "").lower() in ("require", "prefer", "allow")
            or (os.environ.get("SUPABASE_SSL_NO_VERIFY") or "").strip().lower()
            in ("1", "true", "yes")
        )
        if insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl"] = ctx

    return clean_dsn, kwargs


async def init_pool() -> None:
    global _pool
    if _pool is not None:
        return
    dsn = resolve_db_url()
    if not dsn:
        return
    clean_dsn, kwargs = _prepare_asyncpg_dsn(dsn)
    _pool = await asyncpg.create_pool(
        clean_dsn,
        min_size=1,
        max_size=10,
        command_timeout=60,
        **kwargs,
    )


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool_ready() -> bool:
    return _pool is not None


def _claims_from_token(access_token: str) -> dict[str, Any]:
    """Decodifica i claim JWT senza verificare la firma (la verifica è in auth).
    Qui serve solo per propagare i claim a Postgres/RLS."""
    import jwt as pyjwt

    return pyjwt.decode(
        access_token,
        options={"verify_signature": False, "verify_aud": False, "verify_exp": False},
    )


async def _apply_jwt_claims(conn: asyncpg.Connection, claims: dict[str, Any]) -> None:
    """Imposta ruolo + claim così auth.uid() e RLS lavorano come su PostgREST."""
    sub = str(claims.get("sub") or "")
    await conn.execute("select set_config('role', 'authenticated', true)")
    await conn.execute(
        "select set_config('request.jwt.claims', $1, true)",
        json.dumps(claims, default=str),
    )
    # Compat: alcune installazioni leggono claim.sub singolo
    if sub:
        await conn.execute("select set_config('request.jwt.claim.sub', $1, true)", sub)
        await conn.execute(
            "select set_config('request.jwt.claim.role', $1, true)",
            str(claims.get("role") or "authenticated"),
        )


@asynccontextmanager
async def tenant_conn_claims(claims: dict[str, Any]) -> AsyncIterator[asyncpg.Connection]:
    """Connessione RLS con claim già risolti (legacy bridge o Supabase)."""
    if _pool is None:
        raise RuntimeError(
            "Pool Postgres non inizializzato "
            "(imposta CONNECTION_STRING_SUPABASE o SUPABASE_DB_URL)"
        )
    async with _pool.acquire() as conn:
        async with conn.transaction():
            await _apply_jwt_claims(conn, claims)
            yield conn


@asynccontextmanager
async def tenant_conn(access_token: str) -> AsyncIterator[asyncpg.Connection]:
    """Connessione con i claim dell'utente impostati:
         SET LOCAL role = 'authenticated';
         SET LOCAL request.jwt.claims = <claims json>;
       ⇒ RLS filtra esattamente come per il client browser.
       Usare per QUALSIASI operazione originata da una richiesta utente."""
    claims = _claims_from_token(access_token)
    async with tenant_conn_claims(claims) as conn:
        yield conn


@asynccontextmanager
async def public_conn() -> AsyncIterator[asyncpg.Connection]:
    """Connessione anon con i privilegi/RLS del Data API Supabase.

    È destinata esclusivamente a letture pubbliche esplicitamente concesse,
    come la configurazione brand del tenant. Non bypassa RLS.
    """
    if _pool is None:
        raise RuntimeError(
            "Pool Postgres non inizializzato "
            "(imposta CONNECTION_STRING_SUPABASE o SUPABASE_DB_URL)"
        )
    async with _pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("select set_config('role', 'anon', true)")
            await conn.execute(
                "select set_config('request.jwt.claims', $1, true)",
                json.dumps({"role": "anon"}),
            )
            yield conn


@asynccontextmanager
async def system_conn() -> AsyncIterator[asyncpg.Connection]:
    """Connessione senza contesto utente, RLS bypassata.
    Import consentito SOLO da backend/system_jobs/.
    Ispeziona lo stack del chiamante e alza RuntimeError altrove."""
    allowed = False
    for frame in inspect.stack():
        path = (frame.filename or "").replace("\\", "/")
        if "/system_jobs/" in path or path.endswith("/system_jobs"):
            allowed = True
            break
    if not allowed:
        raise RuntimeError(
            "system_conn() consentito solo da backend/system_jobs/ — "
            "usa tenant_conn per le richieste utente"
        )
    if _pool is None:
        raise RuntimeError(
            "Pool Postgres non inizializzato "
            "(imposta CONNECTION_STRING_SUPABASE o SUPABASE_DB_URL)"
        )
    async with _pool.acquire() as conn:
        yield conn


def record_to_dict(row: asyncpg.Record | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def records_to_list(rows: list[asyncpg.Record]) -> list[dict]:
    return [dict(r) for r in rows]
