"""Job idempotente dei promemoria economici email/WhatsApp."""

from __future__ import annotations

import asyncio

import db
from payment_reminders import processa_promemoria


async def run() -> dict:
    await db.init_pool()
    async with db.system_conn() as conn:
        return await processa_promemoria(conn)


if __name__ == "__main__":
    print(asyncio.run(run()))
