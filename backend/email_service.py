from __future__ import annotations

import html
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Dict, Optional

logger = logging.getLogger("gb.email")


def _env(name: str, fallback: str = "") -> str:
    return (os.environ.get(name) or fallback).strip()


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on", "ssl"}


def _smtp_port() -> int:
    try:
        return int(_env("SMTP_PORT", "465"))
    except ValueError:
        return 465


def is_configured() -> bool:
    return bool(
        _env("SMTP_HOST")
        and _env("SMTP_USERNAME", _env("SMTP_USER"))
        and _env("SMTP_PASSWORD")
    )


def _sender_email() -> str:
    return _env("MAIL_FROM_EMAIL", _env("SMTP_FROM_EMAIL", _env("SMTP_USERNAME", _env("SMTP_USER"))))


def _sender_name() -> str:
    return _env("MAIL_FROM_NAME", _env("SMTP_FROM_NAME", "GB Construction"))


def _notification_email() -> str:
    return _env("LEAD_NOTIFICATION_EMAIL", _env("MAIL_TO", _sender_email()))


def _dashboard_lead_url(lead_id: Optional[str]) -> str:
    if not lead_id:
        return ""
    public_url = _env("APP_PUBLIC_URL", "https://gbconstruction.it").rstrip("/")
    return f"{public_url}/dashboard/lead/{lead_id}"


def _safe(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value).strip())


def _format_eur(value: Any) -> str:
    try:
        amount = int(round(float(value)))
    except (TypeError, ValueError):
        return "-"
    return f"EUR {amount:,}".replace(",", ".")


def _selected_package(lead: Dict[str, Any]) -> Dict[str, Any]:
    estimate = lead.get("estimate") or {}
    packages = estimate.get("pacchetti") or {}
    level = lead.get("livello") or "premium"
    return packages.get(level) or {}


def _estimate_range(lead: Dict[str, Any]) -> str:
    package = _selected_package(lead)
    low = package.get("range_basso", lead.get("range_basso"))
    high = package.get("range_alto", lead.get("range_alto"))
    if not low and not high:
        return "-"
    return f"{_format_eur(low)} - {_format_eur(high)}"


def _source_label(kind: str, lead: Dict[str, Any]) -> str:
    if kind == "callback" or lead.get("origine") == "callback":
        return "Richiesta di richiamo"
    if kind == "ai_quote" or lead.get("origine") == "ai_architect":
        return "Preventivo da AI Architect"
    return "Preventivo dalla landing"


def _html_table(rows: list[tuple[str, Any]]) -> str:
    rendered = []
    for label, value in rows:
        rendered.append(
            "<tr>"
            f"<td style='padding:8px 10px;border-bottom:1px solid #eee;color:#666'>{_safe(label)}</td>"
            f"<td style='padding:8px 10px;border-bottom:1px solid #eee;color:#111'><strong>{_safe(value) or '-'}</strong></td>"
            "</tr>"
        )
    return "<table cellpadding='0' cellspacing='0' style='border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:14px'>" + "".join(rendered) + "</table>"


def _admin_body(lead: Dict[str, Any], kind: str) -> tuple[str, str]:
    label = _source_label(kind, lead)
    lead_id = lead.get("id") or lead.get("_id")
    dashboard_url = _dashboard_lead_url(str(lead_id) if lead_id else "")
    rows = [
        ("Origine", label),
        ("Nome", lead.get("nome")),
        ("Email", lead.get("email")),
        ("Telefono", lead.get("telefono")),
        ("Citta", lead.get("citta")),
        ("Immobile", lead.get("tipo_immobile")),
        ("Mq", lead.get("mq")),
        ("Livello", lead.get("livello")),
        ("Stile", lead.get("stile")),
        ("Tempistiche", lead.get("tempistiche")),
        ("Range stimato", _estimate_range(lead)),
        ("Score", lead.get("score")),
        ("Note", lead.get("note_cliente")),
    ]
    text_lines = [f"{label} ricevuta", ""]
    text_lines.extend(f"{name}: {value or '-'}" for name, value in rows)
    if dashboard_url:
        text_lines.extend(["", f"Scheda lead: {dashboard_url}"])

    action = (
        f"<p style='margin:20px 0'><a href='{_safe(dashboard_url)}' "
        "style='display:inline-block;background:#c62828;color:#fff;text-decoration:none;"
        "padding:12px 18px;border-radius:999px;font-weight:bold'>Apri scheda lead</a></p>"
        if dashboard_url
        else ""
    )
    html_body = (
        "<div style='font-family:Arial,sans-serif;color:#111;line-height:1.5'>"
        f"<h2 style='margin:0 0 12px'>Nuova {html.escape(label.lower())}</h2>"
        f"{_html_table(rows)}"
        f"{action}"
        "</div>"
    )
    return "\n".join(text_lines), html_body


def _customer_body(lead: Dict[str, Any], kind: str) -> tuple[str, str]:
    name = lead.get("nome") or "cliente"
    if kind == "callback" or lead.get("origine") == "callback":
        intro = (
            "abbiamo ricevuto la tua richiesta di richiamo. "
            "Il team GB Construction ti contattera al numero indicato entro breve."
        )
        details = [
            ("Telefono", lead.get("telefono")),
            ("Messaggio", lead.get("note_cliente")),
        ]
    else:
        intro = (
            "abbiamo ricevuto la tua richiesta di preventivo. "
            "Un referente GB Construction verifichera i dati e ti ricontattera per il sopralluogo."
        )
        details = [
            ("Immobile", lead.get("tipo_immobile")),
            ("Mq", lead.get("mq")),
            ("Livello", lead.get("livello")),
            ("Stile", lead.get("stile")),
            ("Range stimato", _estimate_range(lead)),
        ]

    text_lines = [
        f"Ciao {name},",
        "",
        intro,
        "",
        "Riepilogo:",
    ]
    text_lines.extend(f"{label}: {value or '-'}" for label, value in details)
    text_lines.extend(["", "A presto,", "GB Construction"])

    html_body = (
        "<div style='font-family:Arial,sans-serif;color:#111;line-height:1.5'>"
        f"<p>Ciao <strong>{_safe(name)}</strong>,</p>"
        f"<p>{_safe(intro)}</p>"
        f"{_html_table(details)}"
        "<p style='margin-top:20px'>A presto,<br><strong>GB Construction</strong></p>"
        "</div>"
    )
    return "\n".join(text_lines), html_body


def _build_message(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    reply_to: Optional[str] = None,
) -> EmailMessage:
    message = EmailMessage()
    from_email = _sender_email()
    message["From"] = formataddr((_sender_name(), from_email))
    message["To"] = to_email
    message["Subject"] = subject
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    return message


def _send_message(message: EmailMessage) -> None:
    host = _env("SMTP_HOST")
    port = _smtp_port()
    username = _env("SMTP_USERNAME", _env("SMTP_USER"))
    password = _env("SMTP_PASSWORD")
    timeout = float(_env("SMTP_TIMEOUT_SECONDS", "15"))
    use_ssl = _env_bool("SMTP_USE_SSL", port == 465)
    use_starttls = _env_bool("SMTP_USE_STARTTLS", not use_ssl)

    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
        return

    with smtplib.SMTP(host, port, timeout=timeout) as smtp:
        if use_starttls:
            smtp.starttls(context=ssl.create_default_context())
        smtp.login(username, password)
        smtp.send_message(message)


def send_lead_emails(lead: Dict[str, Any], kind: str = "lead") -> None:
    if not is_configured():
        logger.warning("SMTP not configured: lead email notifications skipped")
        return

    lead = dict(lead)
    customer_email = (lead.get("email") or "").strip()
    notification_email = _notification_email()
    label = _source_label(kind, lead)

    try:
        text_body, html_body = _admin_body(lead, kind)
        admin_message = _build_message(
            to_email=notification_email,
            subject=f"[GB Construction] {label}: {lead.get('nome') or 'nuovo contatto'}",
            text_body=text_body,
            html_body=html_body,
            reply_to=customer_email or None,
        )
        _send_message(admin_message)
    except Exception:
        logger.exception("Failed to send internal lead notification")

    if not customer_email:
        return

    try:
        text_body, html_body = _customer_body(lead, kind)
        customer_message = _build_message(
            to_email=customer_email,
            subject="Abbiamo ricevuto la tua richiesta - GB Construction",
            text_body=text_body,
            html_body=html_body,
        )
        _send_message(customer_message)
    except Exception:
        logger.exception("Failed to send customer confirmation email")


def enqueue_lead_emails(background_tasks: Any, lead: Dict[str, Any], kind: str = "lead") -> None:
    payload = dict(lead)
    if background_tasks is not None:
        background_tasks.add_task(send_lead_emails, payload, kind)
        return
    send_lead_emails(payload, kind)
