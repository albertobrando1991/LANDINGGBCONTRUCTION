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

BRAND_RED = "#C62828"
BRAND_ONYX = "#0F0F10"
BRAND_STEEL = "#4A4A4D"
BRAND_CONCRETE = "#6E6E6E"
BRAND_LIGHT = "#D9D9D9"
BRAND_BG = "#F4F4F4"


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


def _public_url() -> str:
    return _env("APP_PUBLIC_URL", "https://gbconstruction.it").rstrip("/")


def _logo_url() -> str:
    return _env("MAIL_LOGO_URL", _env("BRAND_LOGO_URL", f"{_public_url()}/brand/gb-logo.png"))


def _dashboard_lead_url(lead_id: Optional[str]) -> str:
    if not lead_id:
        return ""
    return f"{_public_url()}/dashboard/lead/{lead_id}"


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
            f"<td style='padding:12px 14px;border-bottom:1px solid #e7e7e7;color:{BRAND_CONCRETE};"
            "font-size:11px;text-transform:uppercase;letter-spacing:.08em;font-weight:700;width:34%'>"
            f"{_safe(label)}</td>"
            f"<td style='padding:12px 14px;border-bottom:1px solid #e7e7e7;color:{BRAND_ONYX};"
            "font-size:14px;font-weight:600'>"
            f"{_safe(value) or '-'}</td>"
            "</tr>"
        )
    return (
        "<table cellpadding='0' cellspacing='0' role='presentation' "
        "style='border-collapse:collapse;width:100%;font-family:Montserrat,Arial,sans-serif;"
        "border:1px solid #e7e7e7;background:#fff'>"
        + "".join(rendered)
        + "</table>"
    )


def _email_shell(title: str, html_body: str, preheader: str = "") -> str:
    safe_title = _safe(title or "GB Construction")
    safe_preheader = _safe(preheader or "GB Construction - Costruiamo valore. Trasformiamo spazi.")
    logo_url = _safe(_logo_url())
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{safe_title}</title>
  </head>
  <body style="margin:0;padding:0;background:{BRAND_BG};font-family:Montserrat,Arial,sans-serif;color:{BRAND_ONYX};">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{safe_preheader}</div>
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:{BRAND_BG};margin:0;padding:0;">
      <tr>
        <td align="center" style="padding:28px 14px;">
          <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:680px;border-collapse:collapse;">
            <tr>
              <td style="background:{BRAND_ONYX};padding:0;border-radius:6px 6px 0 0;overflow:hidden;">
                <div style="height:5px;background:{BRAND_RED};line-height:5px;font-size:5px;">&nbsp;</div>
                <table role="presentation" cellpadding="0" cellspacing="0" width="100%">
                  <tr>
                    <td style="padding:24px 28px 18px 28px;">
                      <img src="{logo_url}" width="132" alt="GB Construction" style="display:block;width:132px;max-width:132px;height:auto;border:0;outline:none;text-decoration:none;margin:0 0 18px 0;">
                      <div style="font-family:Oswald,Arial,sans-serif;color:#ffffff;font-size:12px;letter-spacing:.22em;text-transform:uppercase;font-weight:700;">
                        Costruiamo valore. Trasformiamo spazi.
                      </div>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="background:#ffffff;border-left:1px solid #dedede;border-right:1px solid #dedede;padding:30px 28px;">
                <h1 style="font-family:Oswald,Arial,sans-serif;margin:0 0 20px 0;color:{BRAND_ONYX};font-size:28px;line-height:1.12;text-transform:uppercase;letter-spacing:.02em;">
                  {safe_title}
                </h1>
                <div style="height:3px;width:72px;background:{BRAND_RED};margin:0 0 24px 0;line-height:3px;font-size:3px;">&nbsp;</div>
                {html_body}
              </td>
            </tr>
            <tr>
              <td style="background:{BRAND_ONYX};border-radius:0 0 6px 6px;padding:20px 28px;color:{BRAND_LIGHT};font-size:12px;line-height:1.6;">
                <strong style="font-family:Oswald,Arial,sans-serif;color:#ffffff;text-transform:uppercase;letter-spacing:.08em;">GB Construction S.R.L.</strong><br>
                Via San Giacomo 35, 80013 Casalnuovo di Napoli (NA)<br>
                <span style="color:{BRAND_LIGHT};">info@gbconstruction.it</span> &nbsp;|&nbsp; +39 389 658 4125
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


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
        f"style='display:inline-block;background:{BRAND_RED};color:#fff;text-decoration:none;"
        "padding:13px 18px;border-radius:4px;font-family:Oswald,Arial,sans-serif;"
        "font-weight:700;text-transform:uppercase;letter-spacing:.08em'>Apri scheda lead</a></p>"
        if dashboard_url
        else ""
    )
    html_body = (
        f"<div style='font-family:Montserrat,Arial,sans-serif;color:{BRAND_ONYX};line-height:1.55'>"
        f"<p style='margin:0 0 18px;color:{BRAND_STEEL};font-size:15px'>"
        f"Nuova <strong>{html.escape(label.lower())}</strong> ricevuta dalla piattaforma GB Construction.</p>"
        f"{_html_table(rows)}"
        f"{action}"
        "</div>"
    )
    return "\n".join(text_lines), html_body


def _customer_body(lead: Dict[str, Any], kind: str) -> tuple[str, str]:
    name = lead.get("nome") or "cliente"
    if kind == "sopralluogo":
        sopr = lead.get("sopralluogo") or {}
        quando = " ".join(
            str(p) for p in [sopr.get("date"), sopr.get("start")] if p
        ) or "-"
        if sopr.get("start") and sopr.get("end"):
            quando = f"{sopr.get('date')} dalle {sopr.get('start')} alle {sopr.get('end')}"
        intro = (
            "il tuo sopralluogo e confermato. Un tecnico GB Construction ti raggiungera "
            "all'indirizzo indicato nella data e orario qui sotto."
        )
        details = [
            ("Data e orario", quando),
            ("Tecnico", sopr.get("tecnico")),
            ("Indirizzo", lead.get("indirizzo")),
            ("Telefono", lead.get("telefono")),
        ]
    elif kind == "callback" or lead.get("origine") == "callback":
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
        f"<div style='font-family:Montserrat,Arial,sans-serif;color:{BRAND_ONYX};line-height:1.58'>"
        f"<p style='margin:0 0 14px;font-size:15px'>Ciao <strong>{_safe(name)}</strong>,</p>"
        f"<p style='margin:0 0 20px;color:{BRAND_STEEL};font-size:15px'>{_safe(intro)}</p>"
        f"{_html_table(details)}"
        f"<p style='margin-top:22px;color:{BRAND_STEEL};font-size:14px'>"
        f"A presto,<br><strong style='color:{BRAND_ONYX}'>GB Construction</strong></p>"
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
    message.add_alternative(
        _email_shell(subject, html_body, preheader=text_body[:180]),
        subtype="html",
    )
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


def send_custom_email(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    attachments: Optional[list] = None,
    reply_to: Optional[str] = None,
) -> None:
    """Invio email manuale dallo staff tramite l'email ufficiale (SMTP/Zimbra), con allegati.

    attachments: lista di dict {"filename": str, "content": bytes, "mime": str}.
    """
    if not is_configured():
        raise RuntimeError("SMTP/email ufficiale non configurato")
    if not (to_email or "").strip():
        raise RuntimeError("Destinatario mancante")
    message = EmailMessage()
    message["From"] = formataddr((_sender_name(), _sender_email()))
    message["To"] = to_email
    message["Subject"] = subject or "GB Construction"
    if reply_to:
        message["Reply-To"] = reply_to
    message.set_content(body_text or "")
    html_body = (
        f"<div style=\"font-family:Montserrat,Arial,sans-serif;font-size:15px;line-height:1.6;"
        f"color:{BRAND_ONYX};white-space:pre-wrap\">" + _safe(body_text) + "</div>"
    )
    message.add_alternative(
        _email_shell(subject or "GB Construction", html_body, preheader=(body_text or "")[:180]),
        subtype="html",
    )
    for att in attachments or []:
        content = att.get("content")
        if not content:
            continue
        mime = att.get("mime") or "application/octet-stream"
        maintype, _, subtype = mime.partition("/")
        message.add_attachment(
            content,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=att.get("filename") or "allegato",
        )
    _send_message(message)


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
        customer_subject = (
            "Sopralluogo confermato - GB Construction"
            if kind == "sopralluogo"
            else "Abbiamo ricevuto la tua richiesta - GB Construction"
        )
        customer_message = _build_message(
            to_email=customer_email,
            subject=customer_subject,
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
