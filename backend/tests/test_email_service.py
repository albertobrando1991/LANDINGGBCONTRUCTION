import email_service


def _clear_resend(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("API_RESEND", raising=False)


def _assert_branded_logo(message, html_body):
    if "cid:gblogo" in html_body:
        images = [
            part
            for part in message.walk()
            if part.get_content_maintype() == "image"
            and part.get("Content-ID") == "<gblogo>"
        ]
        assert images, "Il logo CID dichiarato nell'HTML deve essere allegato"
    else:
        assert "https://gbconstruction.it/brand/gb-logo.png" in html_body


def _lead():
    return {
        "id": "lead-123",
        "nome": "Mario Rossi",
        "email": "mario@example.com",
        "telefono": "+39 333 1234567",
        "citta": "Napoli",
        "tipo_immobile": "appartamento",
        "mq": 90,
        "livello": "premium",
        "stile": "Moderno minimal",
        "tempistiche": "Subito",
        "score": 82,
        "range_basso": 50000,
        "range_alto": 65000,
        "estimate": {
            "pacchetti": {
                "premium": {
                    "range_basso": 50000,
                    "range_alto": 65000,
                }
            }
        },
    }


def test_email_service_skips_when_smtp_is_not_configured(monkeypatch):
    _clear_resend(monkeypatch)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    assert email_service.is_configured() is False
    email_service.send_lead_emails(_lead(), "landing_quote")


def test_email_service_sends_internal_and_customer_messages(monkeypatch):
    _clear_resend(monkeypatch)
    sent_messages = []
    logins = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None, context=None):
            self.host = host
            self.port = port
            self.timeout = timeout
            self.context = context

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            logins.append((username, password))

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setenv("SMTP_HOST", "mail.gbconstruction.it")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USERNAME", "info@gbconstruction.it")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("MAIL_FROM_EMAIL", "info@gbconstruction.it")
    monkeypatch.setenv("LEAD_NOTIFICATION_EMAIL", "info@gbconstruction.it")
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", FakeSMTP)

    email_service.send_lead_emails(_lead(), "landing_quote")

    assert len(sent_messages) == 2
    assert logins == [
        ("info@gbconstruction.it", "secret"),
        ("info@gbconstruction.it", "secret"),
    ]
    assert sent_messages[0]["To"] == "info@gbconstruction.it"
    assert sent_messages[0]["Reply-To"] == "mario@example.com"
    assert sent_messages[1]["To"] == "mario@example.com"
    html_body = sent_messages[1].get_body(preferencelist=("html",)).get_content()
    _assert_branded_logo(sent_messages[1], html_body)
    assert "#C62828" in html_body
    assert "Costruiamo valore. Trasformiamo spazi." in html_body


def test_custom_email_uses_branded_layout(monkeypatch):
    _clear_resend(monkeypatch)
    sent_messages = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=None, context=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            pass

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setenv("SMTP_HOST", "mail.gbconstruction.it")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USERNAME", "info@gbconstruction.it")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("MAIL_FROM_EMAIL", "info@gbconstruction.it")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://gbconstruction.it")
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", FakeSMTP)

    email_service.send_custom_email(
        to_email="cliente@example.com",
        subject="Aggiornamento cantiere",
        body_text="Stato avanzamento: 45%",
    )

    assert len(sent_messages) == 1
    html_body = sent_messages[0].get_body(preferencelist=("html",)).get_content()
    _assert_branded_logo(sent_messages[0], html_body)
    assert "Aggiornamento cantiere" in html_body
    assert "Stato avanzamento: 45%" in html_body


def test_resend_has_priority_and_preserves_brand_reply_to_and_inline_logo(monkeypatch):
    requests_sent = []

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"id": "resend-email-123"}

    def fake_post(url, *, headers, json, timeout):
        requests_sent.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return FakeResponse()

    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.setenv("API_RESEND", "re_test_secret")
    monkeypatch.setenv("SMTP_HOST", "mail.gbconstruction.it")
    monkeypatch.setenv("SMTP_USERNAME", "info@gbconstruction.it")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-secret")
    monkeypatch.setenv("MAIL_FROM_EMAIL", "info@gbconstruction.it")
    monkeypatch.setenv("MAIL_FROM_NAME", "GB Construction")
    monkeypatch.setenv("LEAD_NOTIFICATION_EMAIL", "info@gbconstruction.it")
    monkeypatch.setattr(email_service.requests, "post", fake_post)

    assert email_service.transport_name() == "resend"
    assert email_service.is_configured() is True
    email_service.send_lead_emails(_lead(), "landing_quote")

    assert len(requests_sent) == 2
    assert requests_sent[0]["url"] == "https://api.resend.com/emails"
    assert requests_sent[0]["headers"]["Authorization"] == "Bearer re_test_secret"
    assert requests_sent[0]["json"]["from"] == "GB Construction <info@gbconstruction.it>"
    assert requests_sent[0]["json"]["to"] == ["info@gbconstruction.it"]
    assert requests_sent[0]["json"]["reply_to"] == "mario@example.com"
    assert requests_sent[1]["json"]["to"] == ["mario@example.com"]
    assert "#C62828" in requests_sent[1]["json"]["html"]
    assert "Costruiamo valore. Trasformiamo spazi." in requests_sent[1]["json"]["html"]
    if "cid:gblogo" in requests_sent[1]["json"]["html"]:
        assert any(
            attachment.get("content_id") == "gblogo"
            for attachment in requests_sent[1]["json"].get("attachments", [])
        )


def test_resend_error_is_reported_without_falling_back_to_smtp(monkeypatch):
    smtp_calls = []

    class FakeResponse:
        status_code = 403

        @staticmethod
        def json():
            return {"message": "domain is not verified"}

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            smtp_calls.append((args, kwargs))

    monkeypatch.setenv("RESEND_API_KEY", "re_test_secret")
    monkeypatch.delenv("API_RESEND", raising=False)
    monkeypatch.setenv("SMTP_HOST", "mail.gbconstruction.it")
    monkeypatch.setenv("SMTP_USERNAME", "info@gbconstruction.it")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-secret")
    monkeypatch.setenv("MAIL_FROM_EMAIL", "info@gbconstruction.it")
    monkeypatch.setattr(email_service.requests, "post", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", FakeSMTP)

    message = email_service._build_message(
        to_email="cliente@example.com",
        subject="Test Resend",
        text_body="Test",
        html_body="<p>Test</p>",
    )

    try:
        email_service._send_message(message)
    except RuntimeError as exc:
        assert "Resend API HTTP 403" in str(exc)
        assert "domain is not verified" in str(exc)
    else:
        raise AssertionError("Un errore Resend deve essere propagato")
    assert smtp_calls == []
