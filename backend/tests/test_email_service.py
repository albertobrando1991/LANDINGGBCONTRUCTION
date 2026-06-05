import email_service


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
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)

    assert email_service.is_configured() is False
    email_service.send_lead_emails(_lead(), "landing_quote")


def test_email_service_sends_internal_and_customer_messages(monkeypatch):
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
    monkeypatch.setenv("SMTP_USERNAME", "dashboard@gbconstruction.it")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("MAIL_FROM_EMAIL", "dashboard@gbconstruction.it")
    monkeypatch.setenv("LEAD_NOTIFICATION_EMAIL", "dashboard@gbconstruction.it")
    monkeypatch.setattr(email_service.smtplib, "SMTP_SSL", FakeSMTP)

    email_service.send_lead_emails(_lead(), "landing_quote")

    assert len(sent_messages) == 2
    assert logins == [
        ("dashboard@gbconstruction.it", "secret"),
        ("dashboard@gbconstruction.it", "secret"),
    ]
    assert sent_messages[0]["To"] == "dashboard@gbconstruction.it"
    assert sent_messages[0]["Reply-To"] == "mario@example.com"
    assert sent_messages[1]["To"] == "mario@example.com"
