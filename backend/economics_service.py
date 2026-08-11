"""Economics cantiere: costi, incassi, scadenze, marginalita ed export CSV."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException


ECONOMICS_ROLES = {"owner", "admin"}


def _dict(row: asyncpg.Record | None) -> dict | None:
    if row is None:
        return None
    result = dict(row)
    for key, value in list(result.items()):
        if isinstance(value, UUID):
            result[key] = str(value)
        elif isinstance(value, Decimal):
            result[key] = float(value)
    return result


async def _require_cantiere(
    conn: asyncpg.Connection, tenant_id: str, cantiere_id: str
) -> None:
    exists = await conn.fetchval(
        """
        select exists(
          select 1 from public.cantieri
          where tenant_id = $1::uuid and id = $2::uuid
        )
        """,
        tenant_id,
        cantiere_id,
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Cantiere non trovato")


async def _require_optional_reference(
    conn: asyncpg.Connection,
    tenant_id: str,
    table: str,
    value: str | None,
    label: str,
) -> None:
    if not value:
        return
    if table not in {"fornitori", "sal", "spese", "incassi", "personale"}:
        raise RuntimeError("Riferimento Economics non consentito")
    exists = await conn.fetchval(
        f"select exists(select 1 from public.{table} where tenant_id = $1::uuid and id = $2::uuid)",
        tenant_id,
        value,
    )
    if not exists:
        raise HTTPException(status_code=404, detail=f"{label} non trovato")


async def get_dashboard(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    cantiere_id: str | None = None,
) -> dict:
    if cantiere_id:
        await _require_cantiere(conn, tenant_id, cantiere_id)

    margins = await conn.fetch(
        """
        select * from public.marginalita_cantiere
        where tenant_id = $1::uuid
          and ($2::uuid is null or cantiere_id = $2::uuid)
        order by cliente, cantiere_id
        """,
        tenant_id,
        cantiere_id,
    )
    suppliers = await conn.fetch(
        """
        select * from public.fornitori
        where tenant_id = $1::uuid
        order by attivo desc, ragione_sociale
        """,
        tenant_id,
    )
    expenses = await conn.fetch(
        """
        select s.*, f.ragione_sociale as fornitore
        from public.spese s
        left join public.fornitori f
          on f.tenant_id = s.tenant_id and f.id = s.fornitore_id
        where s.tenant_id = $1::uuid
          and ($2::uuid is null or s.cantiere_id = $2::uuid)
        order by s.data_documento desc, s.created_at desc
        limit 500
        """,
        tenant_id,
        cantiere_id,
    )
    receipts = await conn.fetch(
        """
        select i.*, s.numero as sal_numero
        from public.incassi i
        left join public.sal s
          on s.tenant_id = i.tenant_id and s.id = i.sal_id
        where i.tenant_id = $1::uuid
          and ($2::uuid is null or i.cantiere_id = $2::uuid)
        order by i.data_prevista desc, i.created_at desc
        limit 500
        """,
        tenant_id,
        cantiere_id,
    )
    deadlines = await conn.fetch(
        """
        select * from public.scadenze
        where tenant_id = $1::uuid
          and ($2::uuid is null or cantiere_id = $2::uuid)
        order by (stato = 'aperta') desc, data_scadenza, created_at
        limit 500
        """,
        tenant_id,
        cantiere_id,
    )

    margin_rows = [_dict(row) for row in margins]
    total_revenue = sum(Decimal(str(row["ricavi_maturati"] or 0)) for row in margins)
    total_cost = sum(Decimal(str(row["costi_registrati"] or 0)) for row in margins)
    total_margin = total_revenue - total_cost
    return {
        "riepilogo": {
            "ricavi_maturati": float(total_revenue),
            "costi_registrati": float(total_cost),
            "margine": float(total_margin),
            "margine_percentuale": (
                round(float(total_margin / total_revenue * 100), 2)
                if total_revenue
                else None
            ),
            "incassato": sum(float(row["incassato"] or 0) for row in margins),
            "da_incassare": sum(float(row["da_incassare"] or 0) for row in margins),
            "scadenze_aperte": sum(int(row["scadenze_aperte"] or 0) for row in margins),
            "scadenze_scadute": sum(int(row["scadenze_scadute"] or 0) for row in margins),
        },
        "cantieri": margin_rows,
        "fornitori": [_dict(row) for row in suppliers],
        "spese": [_dict(row) for row in expenses],
        "incassi": [_dict(row) for row in receipts],
        "scadenze": [_dict(row) for row in deadlines],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def crea_fornitore(
    conn: asyncpg.Connection, tenant_id: str, data: dict[str, Any]
) -> dict:
    try:
        row = await conn.fetchrow(
            """
            insert into public.fornitori (
              tenant_id, ragione_sociale, piva, codice_fiscale,
              email, telefono, indirizzo, note
            ) values ($1::uuid, $2, $3, $4, $5, $6, $7, $8)
            returning *
            """,
            tenant_id,
            data["ragione_sociale"].strip(),
            data.get("piva"),
            data.get("codice_fiscale"),
            data.get("email"),
            data.get("telefono"),
            data.get("indirizzo"),
            data.get("note"),
        )
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            status_code=409, detail="Esiste gia un fornitore con questa Partita IVA"
        ) from exc
    return _dict(row)


async def aggiorna_fornitore(
    conn: asyncpg.Connection, tenant_id: str, fornitore_id: str, data: dict[str, Any]
) -> dict:
    return await _patch_row(
        conn,
        tenant_id,
        "fornitori",
        fornitore_id,
        data,
        {"ragione_sociale", "piva", "codice_fiscale", "email", "telefono", "indirizzo", "note", "attivo"},
        "Fornitore",
    )


async def crea_spesa(
    conn: asyncpg.Connection, tenant_id: str, data: dict[str, Any]
) -> dict:
    await _require_cantiere(conn, tenant_id, data["cantiere_id"])
    await _require_optional_reference(
        conn, tenant_id, "fornitori", data.get("fornitore_id"), "Fornitore"
    )
    attachment = data.get("allegato_path")
    expected_prefix = f"{tenant_id}/cantiere-{data['cantiere_id']}/"
    if attachment and not attachment.startswith(expected_prefix):
        raise HTTPException(status_code=400, detail="Allegato fuori dal cantiere selezionato")
    payment_date = data.get("data_pagamento")
    if data.get("stato") == "pagata" and payment_date is None:
        payment_date = date.today()
    row = await conn.fetchrow(
        """
        insert into public.spese (
          tenant_id, cantiere_id, fornitore_id, categoria, descrizione,
          numero_documento, data_documento, imponibile, iva_percentuale,
          stato, data_pagamento, allegato_path, note
        ) values (
          $1::uuid, $2::uuid, $3::uuid, $4, $5,
          $6, $7, $8, $9, $10, $11, $12, $13
        ) returning *
        """,
        tenant_id,
        data["cantiere_id"],
        data.get("fornitore_id"),
        data["categoria"],
        data["descrizione"].strip(),
        data.get("numero_documento"),
        data["data_documento"],
        data["imponibile"],
        data["iva_percentuale"],
        data.get("stato", "registrata"),
        payment_date,
        attachment,
        data.get("note"),
    )
    return _dict(row)


async def aggiorna_spesa(
    conn: asyncpg.Connection, tenant_id: str, spesa_id: str, data: dict[str, Any]
) -> dict:
    if data.get("stato") == "pagata" and "data_pagamento" not in data:
        data = {**data, "data_pagamento": date.today()}
    return await _patch_row(
        conn,
        tenant_id,
        "spese",
        spesa_id,
        data,
        {"stato", "data_pagamento", "note"},
        "Spesa",
    )


async def crea_incasso(
    conn: asyncpg.Connection, tenant_id: str, data: dict[str, Any]
) -> dict:
    await _require_cantiere(conn, tenant_id, data["cantiere_id"])
    await _require_optional_reference(conn, tenant_id, "sal", data.get("sal_id"), "SAL")
    received_date = data.get("data_incasso")
    if data.get("stato") == "incassato" and received_date is None:
        received_date = date.today()
    row = await conn.fetchrow(
        """
        insert into public.incassi (
          tenant_id, cantiere_id, sal_id, descrizione, importo,
          data_prevista, data_incasso, stato, metodo, note
        ) values ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9, $10)
        returning *
        """,
        tenant_id,
        data["cantiere_id"],
        data.get("sal_id"),
        data["descrizione"].strip(),
        data["importo"],
        data["data_prevista"],
        received_date,
        data.get("stato", "previsto"),
        data.get("metodo"),
        data.get("note"),
    )
    return _dict(row)


async def aggiorna_incasso(
    conn: asyncpg.Connection, tenant_id: str, incasso_id: str, data: dict[str, Any]
) -> dict:
    if data.get("stato") == "incassato" and "data_incasso" not in data:
        data = {**data, "data_incasso": date.today()}
    return await _patch_row(
        conn,
        tenant_id,
        "incassi",
        incasso_id,
        data,
        {"stato", "data_incasso", "metodo", "note"},
        "Incasso",
    )


async def crea_scadenza(
    conn: asyncpg.Connection, tenant_id: str, data: dict[str, Any]
) -> dict:
    await _require_cantiere(conn, tenant_id, data["cantiere_id"])
    await _require_optional_reference(conn, tenant_id, "spese", data.get("spesa_id"), "Spesa")
    await _require_optional_reference(conn, tenant_id, "incassi", data.get("incasso_id"), "Incasso")
    row = await conn.fetchrow(
        """
        insert into public.scadenze (
          tenant_id, cantiere_id, spesa_id, incasso_id, tipo,
          titolo, importo, data_scadenza, note
        ) values ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7, $8, $9)
        returning *
        """,
        tenant_id,
        data["cantiere_id"],
        data.get("spesa_id"),
        data.get("incasso_id"),
        data["tipo"],
        data["titolo"].strip(),
        data.get("importo"),
        data["data_scadenza"],
        data.get("note"),
    )
    return _dict(row)


async def aggiorna_scadenza(
    conn: asyncpg.Connection, tenant_id: str, scadenza_id: str, data: dict[str, Any]
) -> dict:
    if data.get("stato") == "completata" and "completata_at" not in data:
        data = {**data, "completata_at": datetime.now(timezone.utc)}
    return await _patch_row(
        conn,
        tenant_id,
        "scadenze",
        scadenza_id,
        data,
        {"stato", "completata_at", "note"},
        "Scadenza",
    )


async def get_costi_fissi(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    attivo: bool | None = None,
) -> dict:
    rows = await conn.fetch(
        """
        select *,
          (
            attivo
            and data_inizio <= current_date
            and (data_fine is null or data_fine >= current_date)
          ) as corrente
        from public.costi_fissi
        where tenant_id = $1::uuid
          and ($2::boolean is null or attivo = $2::boolean)
        order by attivo desc, categoria, descrizione
        """,
        tenant_id,
        attivo,
    )
    items = [_dict(row) for row in rows]
    return {
        "righe": items,
        "totale_mensile": round(
            sum(
                float(item.get("importo_mensile") or 0)
                for item in items
                if item.get("corrente")
            ),
            2,
        ),
    }


def _validate_period(data_inizio: date, data_fine: date | None) -> None:
    if data_fine is not None and data_fine < data_inizio:
        raise HTTPException(
            status_code=400,
            detail="La data finale non puo precedere la data iniziale",
        )


async def crea_costo_fisso(
    conn: asyncpg.Connection, tenant_id: str, data: dict[str, Any]
) -> dict:
    _validate_period(data["data_inizio"], data.get("data_fine"))
    row = await conn.fetchrow(
        """
        insert into public.costi_fissi (
          tenant_id, categoria, descrizione, importo_mensile,
          data_inizio, data_fine, attivo, note
        ) values ($1::uuid, $2, $3, $4, $5, $6, $7, $8)
        returning *
        """,
        tenant_id,
        data.get("categoria", "altro"),
        data["descrizione"].strip(),
        data["importo_mensile"],
        data["data_inizio"],
        data.get("data_fine"),
        data.get("attivo", True),
        data.get("note"),
    )
    return _dict(row)


async def aggiorna_costo_fisso(
    conn: asyncpg.Connection,
    tenant_id: str,
    costo_fisso_id: str,
    data: dict[str, Any],
) -> dict:
    current = await conn.fetchrow(
        """
        select data_inizio, data_fine
        from public.costi_fissi
        where tenant_id = $1::uuid and id = $2::uuid
        """,
        tenant_id,
        costo_fisso_id,
    )
    if not current:
        raise HTTPException(status_code=404, detail="Costo fisso non trovato")
    _validate_period(
        data.get("data_inizio", current["data_inizio"]),
        data.get("data_fine", current["data_fine"]),
    )
    return await _patch_row(
        conn,
        tenant_id,
        "costi_fissi",
        costo_fisso_id,
        data,
        {
            "categoria",
            "descrizione",
            "importo_mensile",
            "data_inizio",
            "data_fine",
            "attivo",
            "note",
        },
        "Costo fisso",
    )


async def get_subappalti_dashboard(
    conn: asyncpg.Connection,
    tenant_id: str,
    *,
    cantiere_id: str | None = None,
) -> dict:
    if cantiere_id:
        await _require_cantiere(conn, tenant_id, cantiere_id)
    rows = await conn.fetch(
        """
        select
          f.id as fornitore_id,
          f.ragione_sociale,
          s.cantiere_id,
          count(*) as numero_spese,
          coalesce(sum(s.totale), 0)::numeric(14,2) as totale_speso,
          coalesce(
            sum(s.totale) filter (where s.stato = 'pagata'), 0
          )::numeric(14,2) as totale_pagato,
          max(s.data_documento) as ultima_spesa
        from public.spese s
        join public.fornitori f
          on f.tenant_id = s.tenant_id and f.id = s.fornitore_id
        where s.tenant_id = $1::uuid
          and s.categoria = 'subappalto'
          and s.stato <> 'annullata'
          and ($2::uuid is null or s.cantiere_id = $2::uuid)
        group by f.id, f.ragione_sociale, s.cantiere_id
        order by totale_speso desc, f.ragione_sociale
        """,
        tenant_id,
        cantiere_id,
    )
    items = [_dict(row) for row in rows]
    return {
        "righe": items,
        "totale_speso": round(
            sum(float(item.get("totale_speso") or 0) for item in items), 2
        ),
        "totale_pagato": round(
            sum(float(item.get("totale_pagato") or 0) for item in items), 2
        ),
    }


async def _patch_row(
    conn: asyncpg.Connection,
    tenant_id: str,
    table: str,
    row_id: str,
    data: dict[str, Any],
    allowed: set[str],
    label: str,
) -> dict:
    updates = [(key, value) for key, value in data.items() if key in allowed]
    if not updates:
        raise HTTPException(status_code=400, detail="Nessuna modifica valida")
    assignments = ", ".join(
        f"{column} = ${index}" for index, (column, _) in enumerate(updates, start=1)
    )
    values = [value for _, value in updates]
    tenant_index = len(values) + 1
    id_index = len(values) + 2
    row = await conn.fetchrow(
        f"""
        update public.{table}
        set {assignments}
        where tenant_id = ${tenant_index}::uuid and id = ${id_index}::uuid
        returning *
        """,
        *values,
        tenant_id,
        row_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"{label} non trovato")
    return _dict(row)


async def export_csv(
    conn: asyncpg.Connection, tenant_id: str, *, cantiere_id: str | None = None
) -> str:
    dashboard = await get_dashboard(conn, tenant_id, cantiere_id=cantiere_id)
    project_names = {
        row["cantiere_id"]: row["cliente"] for row in dashboard["cantieri"]
    }
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "tipo",
            "data",
            "cantiere",
            "controparte",
            "descrizione",
            "imponibile",
            "iva",
            "totale",
            "stato",
            "riferimento",
        ]
    )
    for expense in dashboard["spese"]:
        writer.writerow(
            [
                "spesa",
                expense["data_documento"],
                project_names.get(expense["cantiere_id"], expense["cantiere_id"]),
                expense.get("fornitore") or "",
                expense["descrizione"],
                f"{expense['imponibile']:.2f}",
                f"{expense['iva_importo']:.2f}",
                f"{expense['totale']:.2f}",
                expense["stato"],
                expense.get("numero_documento") or "",
            ]
        )
    for receipt in dashboard["incassi"]:
        writer.writerow(
            [
                "incasso",
                receipt.get("data_incasso") or receipt["data_prevista"],
                project_names.get(receipt["cantiere_id"], receipt["cantiere_id"]),
                "cliente",
                receipt["descrizione"],
                "",
                "",
                f"{receipt['importo']:.2f}",
                receipt["stato"],
                f"SAL {receipt['sal_numero']}" if receipt.get("sal_numero") else "",
            ]
        )
    return "\ufeff" + output.getvalue()
