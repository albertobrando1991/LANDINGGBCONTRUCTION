"""Job idempotente per caricare il listino ufficiale Campania 2026."""
from __future__ import annotations

import asyncio

import db
from campania_prezzario import sync_official_prezzari


async def run() -> dict:
    await db.init_pool()
    async with db.system_conn() as conn:
        return await sync_official_prezzari(conn)


if __name__ == "__main__":
    print(asyncio.run(run()))
