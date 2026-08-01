"""Accesso Postgres/Supabase con RLS attiva anche lato server."""
from __future__ import annotations

import inspect
import json
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


async def init_pool() -> None:
    global _pool
    if _pool is not None:
        return
    dsn = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        return
    _pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10, command_timeout=60)


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


@asynccontextmanager
async def tenant_conn(access_token: str) -> AsyncIterator[asyncpg.Connection]:
    """Connessione con i claim dell'utente impostati:
         SET LOCAL role = 'authenticated';
         SET LOCAL request.jwt.claims = <claims json>;
       ⇒ RLS filtra esattamente come per il client browser.
       Usare per QUALSIASI operazione originata da una richiesta utente."""
    if _pool is None:
        raise RuntimeError("Pool Postgres non inizializzato (SUPABASE_DB_URL mancante)")
    claims = _claims_from_token(access_token)
    async with _pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("select set_config('role', 'authenticated', true)")
            await conn.execute(
                "select set_config('request.jwt.claims', $1, true)",
                json.dumps(claims),
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
        raise RuntimeError("Pool Postgres non inizializzato (SUPABASE_DB_URL mancante)")
    async with _pool.acquire() as conn:
        yield conn


def record_to_dict(row: asyncpg.Record | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def records_to_list(rows: list[asyncpg.Record]) -> list[dict]:
    return [dict(r) for r in rows]
