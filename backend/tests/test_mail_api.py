from email.message import EmailMessage

from fastapi.testclient import TestClient


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class FakeImap:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def login(self, *_args):
        return "OK", []

    def select(self, mailbox, readonly=True):
        return ("OK", []) if mailbox == "INBOX" else ("NO", [])

    def uid(self, command, *_args):
        if command == "search":
            return "OK", [b"1"]
        return "OK", [(b"1 (RFC822 {1})", self.raw)]

    def logout(self):
        return "BYE", []


def test_manual_sync_matches_existing_customer_and_deduplicates(client: TestClient, monkeypatch) -> None:
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    get_settings.cache_clear()
    admin = _login(client, "admin@example.com", "AdminPass123!")
    customer = client.post("/api/v1/customers", json={"company_name": "Mail Customer", "email": "buyer@example.com"}, headers=admin)
    assert customer.status_code == 201
    raw = EmailMessage()
    raw["From"] = "Buyer <buyer@example.com>"
    raw["To"] = "crm@example.com"
    raw["Subject"] = "Need quotation"
    raw["Message-ID"] = "<mail-test-1@example.com>"
    raw.set_content("Please send quotation")
    monkeypatch.setattr(mail_service, "_open_imap", lambda _settings: FakeImap(raw.as_bytes()))

    first = client.post("/api/v1/mail/sync", headers=admin)
    assert first.status_code == 200
    assert first.json()["imported"] == 1
    second = client.post("/api/v1/mail/sync", headers=admin)
    assert second.status_code == 200
    assert second.json()["imported"] == 0
    page = client.get("/api/v1/mail/messages", params={"folder": "inbox", "customer_id": customer.json()["id"]}, headers=admin)
    assert page.status_code == 200
    assert page.json()["total"] == 1
    assert page.json()["items"][0]["customer_id"] == customer.json()["id"]


def test_mail_send_permissions_and_unmatched_message_stays_unlinked(client: TestClient, monkeypatch) -> None:
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    get_settings.cache_clear()
    admin = _login(client, "admin@example.com", "AdminPass123!")
    monkeypatch.setattr(mail_service, "_smtp_send", lambda _settings, _message: None)
    sent = client.post("/api/v1/mail/send", data={"to_emails": "unknown@example.com", "subject": "Hello", "body": "Body"}, headers=admin)
    assert sent.status_code == 201
    assert sent.json()["customer_id"] is None

    created = client.post("/api/v1/users", json={"name": "Viewer", "email": "mail-viewer@example.com", "password": "ViewerPass123!", "role": "Viewer"}, headers=admin)
    assert created.status_code == 201
    viewer = _login(client, "mail-viewer@example.com", "ViewerPass123!")
    assert client.post("/api/v1/mail/send", data={"to_emails": "x@example.com", "subject": "Blocked"}, headers=viewer).status_code == 403
    assert client.post("/api/v1/mail/sync", headers=viewer).status_code == 403


def test_sales_cannot_read_an_unlinked_email_created_by_another_user(client: TestClient, monkeypatch) -> None:
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    get_settings.cache_clear()
    admin = _login(client, "admin@example.com", "AdminPass123!")
    monkeypatch.setattr(mail_service, "_smtp_send", lambda _settings, _message: None)
    sent = client.post("/api/v1/mail/send", data={"to_emails": "unlinked@example.com", "subject": "Private"}, headers=admin)
    assert sent.status_code == 201
    created = client.post("/api/v1/users", json={"name": "Sales", "email": "mail-sales@example.com", "password": "SalesPass123!", "role": "Sales"}, headers=admin)
    assert created.status_code == 201
    sales = _login(client, "mail-sales@example.com", "SalesPass123!")
    assert client.get(f"/api/v1/mail/messages/{sent.json()['id']}", headers=sales).status_code == 403
