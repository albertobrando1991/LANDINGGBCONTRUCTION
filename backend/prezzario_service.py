"""Servizio prezzario multi-tenant: lista, duplica, wizard, ripristina, import CSV."""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import asyncpg
from fastapi import HTTPException


def _d(row: asyncpg.Record | None) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for k, v in list(out.items()):
        if isinstance(v, UUID):
            out[k] = str(v)
        elif isinstance(v, Decimal):
            out[k] = float(v)
    return out


async def lista_prezzari(conn: asyncpg.Connection, tenant_id: str) -> list[dict]:
    rows = await conn.fetch(
        """
        select p.*,
               (select count(*) from public.prezzario_voci v where v.prezzario_id = p.id) as n_voci
        from public.prezzari p
        where p.tenant_id = $1::uuid
        order by p.is_default desc, p.created_at
        """,
        tenant_id,
    )
    return [_d(r) for r in rows]


async def duplica_prezzario(
    conn: asyncpg.Connection, tenant_id: str, prezzario_id: str, nome: str
) -> dict:
    src = await conn.fetchrow(
        "select * from public.prezzari where id = $1::uuid and tenant_id = $2::uuid",
        prezzario_id,
        tenant_id,
    )
    if not src:
        raise HTTPException(status_code=404, detail="Prezzario non trovato")

    new_id = await conn.fetchval(
        """
        insert into public.prezzari (tenant_id, nome, fonte, anno, is_default, is_sistema)
        values ($1::uuid, $2, 'custom', $3, false, false)
        returning id
        """,
        tenant_id,
        nome,
        src["anno"],
    )
    await conn.execute(
        """
        insert into public.prezzario_voci (
          tenant_id, prezzario_id, codice, super_categoria, categoria, sub_categoria,
          descrizione, um, prezzo_unitario, prezzo_riferimento, tipo, chiave_wizard, attiva
        )
        select tenant_id, $1::uuid, codice, super_categoria, categoria, sub_categoria,
               descrizione, um, prezzo_unitario, prezzo_unitario, tipo, chiave_wizard, attiva
        from public.prezzario_voci
        where prezzario_id = $2::uuid and tenant_id = $3::uuid
        """,
        new_id,
        prezzario_id,
        tenant_id,
    )
    row = await conn.fetchrow("select * from public.prezzari where id = $1", new_id)
    return _d(row)


async def voci_wizard(
    conn: asyncpg.Connection, tenant_id: str, prezzario_id: str
) -> list[dict]:
    rows = await conn.fetch(
        """
        select * from public.prezzario_voci
        where tenant_id = $1::uuid and prezzario_id = $2::uuid and chiave_wizard = true
        order by super_categoria, categoria, descrizione
        """,
        tenant_id,
        prezzario_id,
    )
    return [_d(r) for r in rows]


async def applica_wizard(
    conn: asyncpg.Connection,
    tenant_id: str,
    prezzario_id: str,
    correzioni: dict[str, Decimal],
) -> dict:
    """Aggiorna le voci chiave. Propaga il delta % medio alle non-chiave della stessa categoria."""
    sistema = await conn.fetchval(
        "select is_sistema from public.prezzari where id = $1::uuid and tenant_id = $2::uuid",
        prezzario_id,
        tenant_id,
    )
    if sistema is None:
        raise HTTPException(status_code=404, detail="Prezzario non trovato")
    if sistema:
        raise HTTPException(
            status_code=409,
            detail="Il prezzario Campania è di sola lettura: duplicalo per modificarlo",
        )

    wizard = await conn.fetch(
        """
        select id, categoria, prezzo_unitario from public.prezzario_voci
        where tenant_id = $1::uuid and prezzario_id = $2::uuid and chiave_wizard = true
        """,
        tenant_id,
        prezzario_id,
    )
    by_id = {str(r["id"]): r for r in wizard}
    cat_deltas: dict[str, list[float]] = defaultdict(list)
    updated_keys = 0

    for vid, new_price in correzioni.items():
        row = by_id.get(str(vid))
        if not row:
            continue
        old = float(row["prezzo_unitario"] or 0)
        new = float(new_price)
        if old > 0:
            cat_deltas[row["categoria"]].append((new - old) / old)
        await conn.execute(
            "update public.prezzario_voci set prezzo_unitario = $1 where id = $2::uuid and tenant_id = $3::uuid",
            new,
            vid,
            tenant_id,
        )
        updated_keys += 1

    propagated = 0
    for cat, deltas in cat_deltas.items():
        if not deltas:
            continue
        avg = sum(deltas) / len(deltas)
        if abs(avg) < 1e-9:
            continue
        result = await conn.execute(
            """
            update public.prezzario_voci
            set prezzo_unitario = round(prezzo_unitario * (1 + $1::numeric), 2)
            where tenant_id = $2::uuid and prezzario_id = $3::uuid
              and categoria = $4 and chiave_wizard = false and attiva = true
            """,
            avg,
            tenant_id,
            prezzario_id,
            cat,
        )
        # result like "UPDATE N"
        try:
            propagated += int(result.split()[-1])
        except Exception:
            pass

    return {
        "voci_chiave_aggiornate": updated_keys,
        "voci_propagate": propagated,
        "categorie_toccate": list(cat_deltas.keys()),
    }


async def ripristina_campania(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    prezzario_id: Optional[str] = None,
    voce_ids: Optional[list[str]] = None,
    categoria: Optional[str] = None,
) -> int:
    clauses = ["tenant_id = $1::uuid", "prezzo_riferimento is not null"]
    args: list[Any] = [tenant_id]
    if prezzario_id:
        args.append(prezzario_id)
        clauses.append(f"prezzario_id = ${len(args)}::uuid")
    if voce_ids:
        args.append(voce_ids)
        clauses.append(f"id = any(${len(args)}::uuid[])")
    if categoria:
        args.append(categoria)
        clauses.append(f"categoria = ${len(args)}")

    # non toccare prezzario di sistema (trigger lo bloccherebbe)
    sql = f"""
        update public.prezzario_voci v
        set prezzo_unitario = prezzo_riferimento
        from public.prezzari p
        where v.prezzario_id = p.id and p.is_sistema = false
          and {' and '.join(clauses).replace('tenant_id', 'v.tenant_id')}
    """
    # fix alias: rewrite clauses carefully
    sql = """
        update public.prezzario_voci v
        set prezzo_unitario = v.prezzo_riferimento
        from public.prezzari p
        where v.prezzario_id = p.id
          and p.is_sistema = false
          and v.tenant_id = $1::uuid
          and v.prezzo_riferimento is not null
    """
    args = [tenant_id]
    if prezzario_id:
        args.append(prezzario_id)
        sql += f" and v.prezzario_id = ${len(args)}::uuid"
    if voce_ids:
        args.append(voce_ids)
        sql += f" and v.id = any(${len(args)}::uuid[])"
    if categoria:
        args.append(categoria)
        sql += f" and v.categoria = ${len(args)}"

    result = await conn.execute(sql, *args)
    try:
        return int(result.split()[-1])
    except Exception:
        return 0


async def importa_csv(
    conn: asyncpg.Connection, tenant_id: str, prezzario_id: str, file_bytes: bytes
) -> dict:
    sistema = await conn.fetchval(
        "select is_sistema from public.prezzari where id = $1::uuid and tenant_id = $2::uuid",
        prezzario_id,
        tenant_id,
    )
    if sistema is None:
        raise HTTPException(status_code=404, detail="Prezzario non trovato")
    if sistema:
        raise HTTPException(
            status_code=409,
            detail="Il prezzario Campania è di sola lettura: duplicalo per modificare",
        )

    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    inserted = 0
    scarti: list[dict] = []
    um_ok = {"mq", "ml", "mc", "cad", "corpo", "kg", "h", "n"}

    for i, row in enumerate(reader, start=2):
        try:
            descrizione = (row.get("descrizione") or row.get("voce") or "").strip()
            if not descrizione:
                raise ValueError("descrizione mancante")
            um = (row.get("um") or "cad").strip().lower()
            if um not in um_ok:
                raise ValueError(f"um non valida: {um}")
            prezzo = Decimal(str(row.get("prezzo_unitario") or row.get("prezzo") or "0"))
            if prezzo < 0:
                raise ValueError("prezzo negativo")
            categoria = (row.get("categoria") or "Generale").strip()
            super_c = (row.get("super_categoria") or categoria).strip()
            codice = (row.get("codice") or "").strip() or None
            tipo = "a_corpo" if um == "corpo" else "a_misura"
            await conn.execute(
                """
                insert into public.prezzario_voci (
                  tenant_id, prezzario_id, codice, super_categoria, categoria,
                  descrizione, um, prezzo_unitario, prezzo_riferimento, tipo, chiave_wizard, attiva
                ) values ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $8, $9, false, true)
                """,
                tenant_id,
                prezzario_id,
                codice,
                super_c,
                categoria,
                descrizione,
                um,
                float(prezzo),
                tipo,
            )
            inserted += 1
        except Exception as exc:
            scarti.append({"riga": i, "errore": str(exc)})

    return {"importate": inserted, "scarti": scarti, "n_scarti": len(scarti)}


async def lista_voci(
    conn: asyncpg.Connection,
    tenant_id: str,
    prezzario_id: str,
    *,
    q: Optional[str] = None,
    categoria: Optional[str] = None,
) -> list[dict]:
    sql = """
        select * from public.prezzario_voci
        where tenant_id = $1::uuid and prezzario_id = $2::uuid and attiva = true
    """
    args: list[Any] = [tenant_id, prezzario_id]
    if categoria:
        args.append(categoria)
        sql += f" and categoria = ${len(args)}"
    if q:
        args.append(f"%{q}%")
        sql += f" and (descrizione ilike ${len(args)} or codice ilike ${len(args)})"
    sql += " order by super_categoria, categoria, descrizione"
    rows = await conn.fetch(sql, *args)
    return [_d(r) for r in rows]
