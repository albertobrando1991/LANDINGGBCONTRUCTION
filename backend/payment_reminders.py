"""Invio idempotente dei promemoria rate via email e WhatsApp Cloud API."""

from __future__ import annotations

import asyncio
import os
import re
from datetime import date
from typing import Any

import asyncpg
import requests

import email_service


def _money(value: Any) -> str:
    raw = f"{float(value or 0):,.2f}"
    return "EUR " + raw.replace(",", "X").replace(".", ",").replace("X", ".")


def _date_it(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    return str(value or "-")


def _normalize_whatsapp_recipient(value: Any) -> str:
    """Converte un numero italiano nel formato E.164 senza il segno +."""
    digits = re.sub(r"\D", "", str(value or ""))
    if digits.startswith("00"):
        digits = digits[2:]
    if (digits.startswith("3") and len(digits) == 10) or digits.startswith("0"):
        digits = f"39{digits}"
    if not 8 <= len(digits) <= 15:
        raise RuntimeError("Numero WhatsApp del cliente non valido")
    return digits


def _message(row: dict) -> tuple[str, str]:
    subject = f"Promemoria pagamento rata {row['numero_rata']} - GB Construction"
    paid = float(row.get("pagato") or 0)
    residual = max(0.0, float(row.get("importo") or 0) - paid)
    body = (
        f"Gentile {row.get('cliente_nome') or 'Cliente'},\n\n"
        f"ti ricordiamo la scadenza della rata {row['numero_rata']} relativa al "
        f"cantiere {row.get('cliente_cantiere') or ''}.\n\n"
        f"Riepilogo:\n"
        f"- Descrizione: {row.get('descrizione') or '-'}\n"
        f"- Data prevista: {_date_it(row.get('data_prevista'))}\n"
        f"- Importo rata: {_money(row.get('importo'))}\n"
        f"- Già registrato: {_money(paid)}\n"
        f"- Residuo da pagare: {_money(residual)}\n"
        f"- Modalità: {row.get('modalita_pagamento') or row.get('metodo') or 'come da contratto'}\n\n"
        "Se hai già effettuato il pagamento, ignora questo promemoria e inviaci "
        "la relativa contabile.\n\nGB Construction"
    )
    return subject, body


def _send_whatsapp(row: dict, body: str) -> str:
    token = (os.environ.get("WHATSAPP_ACCESS_TOKEN") or "").strip()
    phone_id = (os.environ.get("WHATSAPP_PHONE_NUMBER_ID") or "").strip()
    template = (os.environ.get("WHATSAPP_PAYMENT_TEMPLATE") or "").strip()
    version = (os.environ.get("META_GRAPH_API_VERSION") or "v23.0").strip()
    if not token or not phone_id or not template:
        raise RuntimeError(
            "WhatsApp Cloud API non configurata: servono token, phone number ID e template approvato"
        )
    payload = {
        "messaging_product": "whatsapp",
        "to": _normalize_whatsapp_recipient(row["destinatario"]),
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": "it"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(row.get("cliente_nome") or "Cliente")},
                        {"type": "text", "text": str(row.get("numero_rata") or "-")},
                        {"type": "text", "text": _date_it(row.get("data_prevista"))},
                        {"type": "text", "text": _money(row.get("residuo"))},
                    ],
                }
            ],
        },
    }
    response = requests.post(
        f"https://graph.facebook.com/{version}/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(f"WhatsApp API HTTP {response.status_code}: {response.text[:250]}")
    data = response.json()
    messages = data.get("messages") or []
    return str(messages[0].get("id") if messages else "")


async def processa_promemoria(
    conn: asyncpg.Connection,
    *,
    tenant_id: str | None = None,
    oggi: date | None = None,
    limit: int = 50,
) -> dict:
    """Invia notifiche dovute; ogni riga viene rivendicata prima della rete."""
    current = oggi or date.today()
    import financial_service

    # Un riavvio durante una chiamata provider non deve bloccare una notifica
    # per sempre. La riga torna ritentabile dopo trenta minuti.
    await conn.execute(
        """
        update public.notifiche_pagamento
        set stato = 'fallita',
            errore = 'Invio interrotto: riprogrammato automaticamente'
        where stato = 'in_corso'
          and updated_at < now() - interval '30 minutes'
          and ($1::uuid is null or tenant_id = $1::uuid)
        """,
        tenant_id,
    )

    plans = await conn.fetch(
        """
        select id, tenant_id from public.piani_pagamento
        where stato = 'attivo' and ($1::uuid is null or tenant_id = $1::uuid)
        """,
        tenant_id,
    )
    for plan in plans:
        await financial_service.pianifica_promemoria(
            conn, str(plan["tenant_id"]), str(plan["id"])
        )
    rows = await conn.fetch(
        """
        select n.*, i.numero_rata, i.descrizione, i.importo, i.data_prevista,
               i.metodo, i.modalita_pagamento,
               p.cliente_nome, c.cliente as cliente_cantiere,
               coalesce(sum(pc.importo), 0)::numeric(14,2) as pagato,
               (i.importo - coalesce(sum(pc.importo), 0))::numeric(14,2) as residuo
        from public.notifiche_pagamento n
        join public.incassi i
          on i.tenant_id = n.tenant_id and i.id = n.incasso_id
        join public.piani_pagamento p
          on p.tenant_id = i.tenant_id and p.id = i.piano_pagamento_id
        join public.cantieri c
          on c.tenant_id = n.tenant_id and c.id = n.cantiere_id
        left join public.pagamenti_cliente pc
          on pc.tenant_id = i.tenant_id and pc.incasso_id = i.id
        where n.stato in ('programmata', 'fallita')
          and n.programmata_per <= $1::date
          and n.tentativi < 5
          and i.stato in ('previsto', 'parziale')
          and p.stato = 'attivo'
          and ($2::uuid is null or n.tenant_id = $2::uuid)
        group by n.id, i.id, p.id, c.id
        order by n.programmata_per, n.created_at
        limit $3
        """,
        current,
        tenant_id,
        limit,
    )
    sent = failed = skipped = 0
    for record in rows:
        row = dict(record)
        claimed = await conn.fetchrow(
            """
            update public.notifiche_pagamento
            set stato = 'in_corso', tentativi = tentativi + 1, errore = null
            where id = $1::uuid and tenant_id = $2::uuid
              and stato in ('programmata', 'fallita')
            returning id
            """,
            str(row["id"]),
            str(row["tenant_id"]),
        )
        if not claimed:
            skipped += 1
            continue
        try:
            subject, body = _message(row)
            if row["canale"] == "email":
                result = await asyncio.to_thread(
                    email_service.send_custom_email,
                    to_email=row["destinatario"],
                    subject=subject,
                    body_text=body,
                    idempotency_key=f"payment-reminder-{row['id']}",
                )
                provider_id = result.get("message_id") or result.get("transport")
            else:
                provider_id = await asyncio.to_thread(_send_whatsapp, row, body)
            await conn.execute(
                """
                update public.notifiche_pagamento
                set stato = 'inviata', provider_id = $1, inviata_at = now(), errore = null
                where id = $2::uuid and tenant_id = $3::uuid
                """,
                provider_id,
                str(row["id"]),
                str(row["tenant_id"]),
            )
            sent += 1
        except Exception as exc:  # il log DB deve conservare il fallimento provider
            await conn.execute(
                """
                update public.notifiche_pagamento
                set stato = 'fallita', errore = $1
                where id = $2::uuid and tenant_id = $3::uuid
                """,
                str(exc)[:1000],
                str(row["id"]),
                str(row["tenant_id"]),
            )
            failed += 1
    return {"candidate": len(rows), "inviate": sent, "fallite": failed, "saltate": skipped}
