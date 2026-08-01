"""Verifica CONNECTION_STRING_SUPABASE / pool asyncpg (senza stampare secret)."""
from __future__ import annotations

import asyncio
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env", override=True)

import db  # noqa: E402


async def main() -> int:
    url = db.resolve_db_url()
    if not url:
        print("FAIL: nessuna connection string (CONNECTION_STRING_SUPABASE / SUPABASE_DB_URL)")
        return 2
    clean, kw = db._prepare_asyncpg_dsn(url)
    host = "?"
    if "@" in clean:
        host = clean.split("@", 1)[1].split("/", 1)[0].split(":", 1)[0]
    print("resolved: YES")
    print("host:", host)
    print("ssl:", "ssl" in kw)
    try:
        infos = socket.getaddrinfo(host, 5432)
        print("dns:", infos[0][4][0] if infos else "empty")
    except Exception as exc:
        print("dns_fail:", type(exc).__name__, str(exc)[:120])
        print("HINT: DNS non risolve il progetto Supabase (offline, VPN, o progetto in pausa).")
    try:
        await db.init_pool()
        print("pool_ready:", db.pool_ready())
        async with db._pool.acquire() as conn:
            ver = await conn.fetchval("select version()")
            print("postgres:", (ver or "")[:70])
            try:
                n = await conn.fetchval("select count(*) from public.tenants")
                print("tenants:", n)
            except Exception as exc:
                print("schema:", type(exc).__name__, str(exc)[:140])
                print("HINT: applica le migration su questo progetto (supabase db push / SQL editor).")
        await db.close_pool()
        print("OK")
        return 0
    except Exception as exc:
        print("CONNECT:", type(exc).__name__, str(exc)[:250])
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
