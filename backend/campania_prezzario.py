"""Lettura e sincronizzazione del Prezzario Regione Campania 2026 ufficiale."""
from __future__ import annotations

import csv
import io
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

import asyncpg

ASSET_PATH = Path(__file__).resolve().parent / "data" / "campania_2026_articoli.zip"
EXPECTED_YEAR = 2026
EXPECTED_ROWS = 31_755


def _unit(value: str) -> str:
    normalized = (value or "cad").strip()
    return {
        "a corpo": "corpo",
        "m²": "mq",
        "m³": "mc",
    }.get(normalized, normalized)


def load_official_rows(path: Path = ASSET_PATH) -> list[tuple]:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(names) != 1:
            raise RuntimeError("Archivio Campania 2026 non valido")
        text = archive.read(names[0]).decode("utf-8-sig")

    rows: list[tuple] = []
    reader = csv.reader(io.StringIO(text, newline=""), delimiter="|")
    next(reader, None)
    for line_number, row in enumerate(reader, start=2):
        if not row or not row[0].strip():
            continue
        if len(row) < 9:
            raise RuntimeError(f"Riga ufficiale {line_number} incompleta")
        try:
            raw_price = row[8].strip()
            price = Decimal(raw_price.replace(",", ".") if raw_price else "0").quantize(
                Decimal("0.01")
            )
        except InvalidOperation as exc:
            raise RuntimeError(f"Prezzo non valido alla riga {line_number}") from exc
        rows.append(
            (
                row[0].strip(),
                row[2].strip() or "Generale",
                row[3].strip() or row[2].strip() or "Generale",
                row[4].strip() or None,
                row[5].strip() or row[4].strip(),
                _unit(row[6]),
                price,
                "a_corpo" if _unit(row[6]) == "corpo" else "a_misura",
            )
        )
    if len(rows) != EXPECTED_ROWS:
        raise RuntimeError(
            f"Prezzario Campania incompleto: attese {EXPECTED_ROWS}, trovate {len(rows)}"
        )
    if len({row[0] for row in rows}) != len(rows):
        raise RuntimeError("Il prezzario ufficiale contiene codici duplicati")
    return rows


async def sync_official_prezzari(conn: asyncpg.Connection) -> dict:
    rows = load_official_rows()
    targets = await conn.fetch(
        """
        select id, tenant_id from public.prezzari
        where fonte = 'campania' and anno = $1
        order by id
        """,
        EXPECTED_YEAR,
    )
    synced = 0
    for target in targets:
        current = await conn.fetchval(
            """select count(*) from public.prezzario_voci
               where prezzario_id = $1 and codice like 'CAM26_%' and attiva = true""",
            target["id"],
        )
        if int(current or 0) == EXPECTED_ROWS:
            continue
        await conn.execute(
            "update public.prezzari set is_sistema = false where id = $1",
            target["id"],
        )
        # Le vecchie voci VS possono essere referenziate da computi confermati:
        # restano come storico inattivo, senza rompere gli snapshot esistenti.
        await conn.execute(
            """update public.prezzario_voci set attiva = false
               where prezzario_id = $1 and codice not like 'CAM26_%'""",
            target["id"],
        )
        records = [
            (
                target["tenant_id"],
                target["id"],
                *row,
            )
            for row in rows
        ]
        await conn.executemany(
            """
            insert into public.prezzario_voci (
              tenant_id, prezzario_id, codice, super_categoria, categoria,
              sub_categoria, descrizione, um, prezzo_unitario,
              prezzo_riferimento, tipo, chiave_wizard, attiva
            ) values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $9, $10, false, true)
            on conflict (tenant_id, prezzario_id, codice) where codice is not null
            do update set
              super_categoria = excluded.super_categoria,
              categoria = excluded.categoria,
              sub_categoria = excluded.sub_categoria,
              descrizione = excluded.descrizione,
              um = excluded.um,
              prezzo_unitario = excluded.prezzo_unitario,
              prezzo_riferimento = excluded.prezzo_riferimento,
              tipo = excluded.tipo,
              attiva = true
            """,
            records,
        )
        await conn.execute(
            "update public.prezzari set is_sistema = true where id = $1",
            target["id"],
        )
        synced += 1
    return {"prezzari_sincronizzati": synced, "voci_per_prezzario": len(rows)}
