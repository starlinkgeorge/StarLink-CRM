from email.message import EmailMessage
from email.header import Header
from email import message_from_bytes, policy
import base64
import imaplib
import quopri
import re

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

    def list(self):
        return "OK", []

    def uid(self, command, *_args):
        if command == "search":
            return "OK", [b"1"]
        return "OK", [(b"1 (RFC822 {1})", self.raw)]

    def logout(self):
        return "BYE", []


class FolderFakeImap(FakeImap):
    def __init__(self, raw: bytes, entries: list[bytes], failing_mailboxes: set[str] | None = None) -> None:
        super().__init__(raw)
        self.entries = entries
        self.failing_mailboxes = failing_mailboxes or set()
        self.select_calls: list[str] = []

    def list(self):
        return "OK", self.entries

    def select(self, mailbox, readonly=True):
        self.select_calls.append(mailbox)
        if mailbox in self.failing_mailboxes:
            raise imaplib.IMAP4.error("EXAMINE parameters!")
        return "OK", []


class IncrementalFakeImap:
    def __init__(self, messages: dict[int, tuple[bytes, bool]], uid_validity: str = "1", failing_uids: set[int] | None = None) -> None:
        self.messages = messages
        self.uid_validity = uid_validity
        self.failing_uids = failing_uids or set()

    def login(self, *_args):
        return "OK", []

    def logout(self):
        return "BYE", []

    def list(self):
        return "OK", []

    def select(self, *_args, **_kwargs):
        return "OK", []

    def response(self, key):
        return ("OK", [self.uid_validity.encode()]) if key == "UIDVALIDITY" else ("NO", [])

    def uid(self, command, *_args):
        if command == "search":
            criterion = str(_args[-1]) if _args else "ALL"
            start = int(criterion.split()[1].split(":")[0]) if criterion.startswith("UID ") else 0
            return "OK", [b" ".join(str(uid).encode() for uid in sorted(self.messages) if uid >= start)]
        uid = int(_args[0])
        if uid in self.failing_uids:
            raise imaplib.IMAP4.error("broken message")
        raw, seen = self.messages[uid]
        flags = b"\\Seen" if seen else b""
        return "OK", [(b"%d (FLAGS (%s) RFC822 {%d})" % (uid, flags, len(raw)), raw)]


def _raw_mail(message_id: str, subject: str = "Hello", body: str = "Body", *, charset: str = "utf-8", sender: str = "buyer@example.com", attachment_name: str | None = None) -> bytes:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = "crm@example.com"
    message["Subject"] = subject
    message["Message-ID"] = f"<{message_id}@example.com>"
    message.set_content(body, charset=charset)
    if attachment_name:
        message.add_attachment("文件内容".encode(charset), maintype="application", subtype="octet-stream", filename=attachment_name)
    return message.as_bytes()


def test_manual_sync_matches_existing_customer_and_deduplicates(client: TestClient, monkeypatch) -> None:
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://crm.example.test")
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
    monkeypatch.setenv("APP_PUBLIC_URL", "https://crm.example.test")
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
    monkeypatch.setenv("APP_PUBLIC_URL", "https://crm.example.test")
    get_settings.cache_clear()
    admin = _login(client, "admin@example.com", "AdminPass123!")
    monkeypatch.setattr(mail_service, "_smtp_send", lambda _settings, _message: None)
    sent = client.post("/api/v1/mail/send", data={"to_emails": "unlinked@example.com", "subject": "Private"}, headers=admin)
    assert sent.status_code == 201
    created = client.post("/api/v1/users", json={"name": "Sales", "email": "mail-sales@example.com", "password": "SalesPass123!", "role": "Sales"}, headers=admin)
    assert created.status_code == 201
    sales = _login(client, "mail-sales@example.com", "SalesPass123!")
    assert client.get(f"/api/v1/mail/messages/{sent.json()['id']}", headers=sales).status_code == 403


def test_sent_flag_discovery_quotes_mailbox_name_with_spaces() -> None:
    from app.services import mail_service

    fake = FolderFakeImap(
        b"unused",
        [b'(\\HasNoChildren \\Sent) "/" "Sent Messages"'],
    )
    assert mail_service._mailboxes_to_sync(fake, "Configured Sent") == [
        ("INBOX", "inbox"),
        ("Sent Messages", "sent"),
    ]
    assert mail_service._imap_quote("Sent Messages") == '"Sent Messages"'
    assert mail_service._imap_quote('A "special" folder') == '"A \\"special\\" folder"'


def test_sync_keeps_inbox_when_sent_discovery_falls_back_and_selection_fails(client: TestClient, monkeypatch, caplog) -> None:
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    monkeypatch.setenv("MAIL_IMAP_SENT_FOLDER", "Sent Messages")
    get_settings.cache_clear()
    admin = _login(client, "admin@example.com", "AdminPass123!")
    raw = EmailMessage()
    raw["From"] = "Buyer <buyer@example.com>"
    raw["To"] = "crm@example.com"
    raw["Subject"] = "Inbox remains available"
    raw["Message-ID"] = "<mail-test-folder-failure@example.com>"
    raw.set_content("Inbox content")
    fake = FolderFakeImap(
        raw.as_bytes(),
        [b'(\\HasNoChildren) "/" "Archive"'],
        failing_mailboxes={'"Sent Messages"'},
    )
    monkeypatch.setattr(mail_service, "_open_imap", lambda _settings: fake)

    result = client.post("/api/v1/mail/sync", headers=admin)
    assert result.status_code == 200
    assert result.json()["imported"] == 1
    assert result.json()["folders"] == ["inbox"]
    assert fake.select_calls == ["INBOX", '"Sent Messages"']
    assert "Skipping IMAP sent mailbox" in caplog.text


def test_outgoing_tracking_pixel_is_unique_and_records_open_events(client: TestClient, monkeypatch) -> None:
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://crm.example.test")
    get_settings.cache_clear()
    sent_messages: list[EmailMessage] = []
    monkeypatch.setattr(mail_service, "_smtp_send", lambda _settings, message: sent_messages.append(message))
    admin = _login(client, "admin@example.com", "AdminPass123!")

    first = client.post("/api/v1/mail/send", data={"to_emails": "buyer@example.com", "subject": "Tracked", "body": "Hello"}, headers=admin)
    second = client.post("/api/v1/mail/send", data={"to_emails": "buyer2@example.com", "subject": "Tracked too", "body": "Hello"}, headers=admin)
    assert first.status_code == second.status_code == 201
    html_bodies = [message.get_body(preferencelist=("html",)).get_content() for message in sent_messages]
    tokens = [re.search(r"/track/([A-Za-z0-9_-]+)\.gif", body).group(1) for body in html_bodies]
    assert len(tokens[0]) >= 40
    assert tokens[0] != tokens[1]
    assert all("https://crm.example.test/api/v1/mail/track/" in body for body in html_bodies)
    assert all("display:none" not in body for body in html_bodies)
    assert all('opacity:0' not in body and 'visibility:hidden' not in body for body in html_bodies)

    opened = client.get(f"/api/v1/mail/track/{tokens[0]}.gif")
    assert opened.status_code == 200
    assert opened.headers["content-type"].startswith("image/gif")
    assert "no-store" in opened.headers["cache-control"]
    assert opened.headers["cdn-cache-control"] == "no-store"
    assert opened.headers["vercel-cdn-cache-control"] == "no-store"
    assert opened.content.startswith(b"GIF89a")
    after_first_open = client.get(f"/api/v1/mail/messages/{first.json()['id']}", headers=admin).json()
    assert after_first_open["open_count"] == 1
    assert after_first_open["first_opened_at"] is not None
    assert after_first_open["last_opened_at"] is not None

    assert client.get(f"/api/v1/mail/track/{tokens[0]}.gif").status_code == 200
    after_second_open = client.get(f"/api/v1/mail/messages/{first.json()['id']}", headers=admin).json()
    assert after_second_open["open_count"] == 2
    assert after_second_open["last_opened_at"] >= after_second_open["first_opened_at"]


def test_sent_imap_copy_with_rewritten_message_id_keeps_crm_tracking_record(client: TestClient, monkeypatch) -> None:
    """A provider's Sent copy must not shadow CRM's token-bearing outgoing row."""
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://crm.example.test")
    get_settings.cache_clear()
    captured: list[EmailMessage] = []
    monkeypatch.setattr(mail_service, "_smtp_send", lambda _settings, message: captured.append(message))
    admin = _login(client, "admin@example.com", "AdminPass123!")
    sent = client.post("/api/v1/mail/send", data={"to_emails": "buyer@example.com", "subject": "Tracked", "body": "Hello"}, headers=admin)
    assert sent.status_code == 201

    sent_copy = captured[0]
    del sent_copy["Message-ID"]
    sent_copy["Message-ID"] = "<provider-rewritten@example.com>"
    fake = IncrementalFakeImap({99: (sent_copy.as_bytes(), True)})
    monkeypatch.setattr(mail_service, "_open_imap", lambda _settings: fake)
    monkeypatch.setattr(mail_service, "_mailboxes_to_sync", lambda _client, _configured: [("Sent Messages", "sent")])

    result = client.post("/api/v1/mail/sync", headers=admin)
    assert result.status_code == 200
    assert result.json()["imported"] == 0
    sent_page = client.get("/api/v1/mail/messages", params={"folder": "sent"}, headers=admin).json()
    assert sent_page["total"] == 1
    assert sent_page["items"][0]["tracking_enabled"] is True


def test_tracking_can_be_disabled_and_internal_mail_view_does_not_open(client: TestClient, monkeypatch) -> None:
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://crm.example.test")
    get_settings.cache_clear()
    sent_messages: list[EmailMessage] = []
    monkeypatch.setattr(mail_service, "_smtp_send", lambda _settings, message: sent_messages.append(message))
    admin = _login(client, "admin@example.com", "AdminPass123!")

    disabled = client.post("/api/v1/mail/send", data={"to_emails": "buyer@example.com", "subject": "No tracking", "tracking_enabled": "false"}, headers=admin)
    assert disabled.status_code == 201
    assert disabled.json()["tracking_enabled"] is False
    assert sent_messages[0].get_body(preferencelist=("html",)) is None
    assert client.get(f"/api/v1/mail/messages/{disabled.json()['id']}", headers=admin).json()["open_count"] == 0

    tracked = client.post("/api/v1/mail/send", data={"to_emails": "buyer@example.com", "subject": "Tracked"}, headers=admin)
    assert tracked.status_code == 201
    # The CRM renders body_text, never the external HTML MIME alternative.
    viewed = client.get(f"/api/v1/mail/messages/{tracked.json()['id']}", headers=admin)
    assert viewed.status_code == 200
    assert viewed.json()["open_count"] == 0

    unknown = client.get("/api/v1/mail/track/not-a-real-token.gif")
    assert unknown.status_code == 200
    assert unknown.headers["content-type"].startswith("image/gif")

    monkeypatch.setattr(mail_service, "record_email_open", lambda _session, _token: (_ for _ in ()).throw(RuntimeError("database unavailable")))
    failed_recording = client.get("/api/v1/mail/track/any-token.gif")
    assert failed_recording.status_code == 200
    assert failed_recording.content.startswith(b"GIF89a")


def test_rich_html_individual_reply_and_forward_each_keep_open_tracking(client: TestClient, monkeypatch) -> None:
    """The editor HTML is sanitized before, not after, its per-message pixel is appended."""
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://crm.example.test")
    get_settings.cache_clear()
    captured: list[EmailMessage] = []
    monkeypatch.setattr(mail_service, "_smtp_send", lambda _settings, message: captured.append(message))
    admin = _login(client, "admin@example.com", "AdminPass123!")

    original = client.post(
        "/api/v1/mail/send",
        data={"to_emails": "buyer@example.com", "subject": "Rich HTML", "html_body": "<p><strong>中文 Bold</strong> <u>underlined</u></p>"},
        headers=admin,
    )
    assert original.status_code == 201
    individual = client.post(
        "/api/v1/mail/send-individually",
        data={"to_emails": "one@example.com; two@example.com", "subject": "Individual", "html_body": "<p><em>Separate</em></p>"},
        headers=admin,
    )
    assert individual.status_code == 201
    reply = client.post(
        "/api/v1/mail/send",
        data={"to_emails": "buyer@example.com", "subject": "Re: Rich HTML", "html_body": "<p>Reply</p>", "reply_to_id": original.json()["id"]},
        headers=admin,
    )
    forwarded = client.post(
        "/api/v1/mail/send",
        data={"to_emails": "forward@example.com", "subject": "Fwd: Rich HTML", "html_body": "<p>Forward</p>", "forward_of_id": original.json()["id"]},
        headers=admin,
    )
    assert reply.status_code == forwarded.status_code == 201

    html_bodies = [message.get_body(preferencelist=("html",)).get_content() for message in captured]
    assert "<strong>中文 Bold</strong>" in html_bodies[0]
    assert "<u>underlined</u>" in html_bodies[0]
    tokens = [re.search(r"/track/([A-Za-z0-9_-]+)\.gif", body).group(1) for body in html_bodies]
    assert len(tokens) == 5
    assert len(set(tokens)) == 5
    assert all("https://crm.example.test/api/v1/mail/track/" in body for body in html_bodies)
    assert all(item["tracking_enabled"] is True for item in individual.json()["sent"])

    opened = client.get(f"/api/v1/mail/track/{tokens[-1]}.gif")
    assert opened.status_code == 200 and opened.content.startswith(b"GIF89a")
    forwarded_detail = client.get(f"/api/v1/mail/messages/{forwarded.json()['id']}", headers=admin).json()
    assert forwarded_detail["open_count"] == 1
    assert forwarded_detail["first_opened_at"] is not None
    assert forwarded_detail["last_opened_at"] is not None


def test_incremental_sync_initial_window_then_all_new_uids_and_seen_state(client: TestClient, monkeypatch) -> None:
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    get_settings.cache_clear()
    admin = _login(client, "admin@example.com", "AdminPass123!")
    fake = IncrementalFakeImap({uid: (_raw_mail(f"initial-{uid}", f"Initial {uid}"), uid % 2 == 0) for uid in range(1, 151)})
    monkeypatch.setattr(mail_service, "_open_imap", lambda _settings: fake)

    first = client.post("/api/v1/mail/sync", headers=admin)
    assert first.status_code == 200
    assert first.json()["imported"] == 100
    fake.messages.update({uid: (_raw_mail(f"later-{uid}", f"Later {uid}"), False) for uid in range(151, 276)})
    second = client.post("/api/v1/mail/sync", headers=admin)
    assert second.status_code == 200
    assert second.json()["imported"] == 125
    page = client.get("/api/v1/mail/messages", params={"folder": "inbox", "limit": 100}, headers=admin)
    assert page.json()["total"] == 225
    newest = next(item for item in page.json()["items"] if item["subject"] == "Later 275")
    assert newest["is_read"] is False
    assert client.post(f"/api/v1/mail/messages/{newest['id']}/read", headers=admin).json()["is_read"] is True
    assert client.post(f"/api/v1/mail/messages/{newest['id']}/unread", headers=admin).json()["is_read"] is False
    assert client.get("/api/v1/mail/counts", headers=admin).json()["unread"] > 0


def test_uidvalidity_change_and_bad_message_do_not_block_later_sync(client: TestClient, monkeypatch, caplog) -> None:
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    get_settings.cache_clear()
    admin = _login(client, "admin@example.com", "AdminPass123!")
    fake = IncrementalFakeImap({1: (_raw_mail("old-generation", "Old"), False), 2: (_raw_mail("bad", "Bad"), False), 3: (_raw_mail("good", "Good"), False)}, failing_uids={2})
    monkeypatch.setattr(mail_service, "_open_imap", lambda _settings: fake)
    result = client.post("/api/v1/mail/sync", headers=admin)
    assert result.status_code == 200
    assert result.json()["imported"] == 2
    assert "UID 2" in caplog.text
    fake.uid_validity = "2"
    fake.failing_uids.clear()
    fake.messages = {1: (_raw_mail("new-generation", "New generation"), False)}
    changed = client.post("/api/v1/mail/sync", headers=admin)
    assert changed.status_code == 200
    assert changed.json()["imported"] == 1


def test_cron_requires_secret_and_shares_sync_lock_path(client: TestClient, monkeypatch) -> None:
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("CRON_SECRET", "cron-test-secret")
    get_settings.cache_clear()
    assert client.get("/api/v1/mail/cron/sync").status_code == 401
    monkeypatch.setattr(mail_service, "sync_mailbox", lambda _session: (_ for _ in ()).throw(mail_service.MailSyncInProgressError()))
    response = client.get("/api/v1/mail/cron/sync", headers={"Authorization": "Bearer cron-test-secret"})
    assert response.status_code == 200
    assert response.json()["already_running"] is True


def test_mime_chinese_decoding_and_forward_tracking(client: TestClient, monkeypatch) -> None:
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://crm.example.test")
    get_settings.cache_clear()
    admin = _login(client, "admin@example.com", "AdminPass123!")
    raw = _raw_mail("cn-mail", str(Header("中文主题", "gb18030")), "中文正文", charset="gb18030", sender=str(Header("中文发件人", "gbk")) + " <buyer@example.com>", attachment_name="中文附件.txt")
    fake = IncrementalFakeImap({1: (raw, False)})
    monkeypatch.setattr(mail_service, "_open_imap", lambda _settings: fake)
    assert client.post("/api/v1/mail/sync", headers=admin).status_code == 200
    original = client.get("/api/v1/mail/messages", params={"folder": "inbox"}, headers=admin).json()["items"][0]
    assert "中文主题" in original["subject"]
    assert "中文正文" in original["body_text"]
    assert "中文发件人" in original["from_name"]
    assert "中文附件" in original["attachments"][0]["file_name"]
    captured: list[EmailMessage] = []
    monkeypatch.setattr(mail_service, "_smtp_send", lambda _settings, message: captured.append(message))
    forwarded = client.post("/api/v1/mail/send", data={"to_emails": "forward@example.com", "subject": "Fwd: 中文主题", "body": "转发正文", "forward_of_id": original["id"]}, headers=admin)
    assert forwarded.status_code == 201
    assert forwarded.json()["forwarded_from_id"] == original["id"]
    assert captured[0].get_body(preferencelist=("html",)) is not None


def test_mime_text_decoding_fallbacks_cover_common_chinese_encodings() -> None:
    from app.services import mail_service

    for charset in ("utf-8", "gbk", "gb2312", "gb18030", "iso-8859-1"):
        text = "中文正文" if charset != "iso-8859-1" else "plain text"
        raw = text.encode(charset)
        assert mail_service._decode_bytes(raw, charset) == text
    encoded_subject = Header("中文主题", "gb2312").encode()
    assert mail_service._header(encoded_subject) == "中文主题"
    base64_message = message_from_bytes(
        b"Content-Type: text/plain; charset=gb18030\nContent-Transfer-Encoding: base64\n\n" + base64.b64encode("Base64 中文".encode("gb18030")), policy=policy.default
    )
    quoted_printable_message = message_from_bytes(
        b"Content-Type: text/plain; charset=gbk\nContent-Transfer-Encoding: quoted-printable\n\n" + quopri.encodestring("QP 中文".encode("gbk")), policy=policy.default
    )
    unknown_charset_message = message_from_bytes(
        b"Content-Type: text/plain; charset=x-unknown\nContent-Transfer-Encoding: base64\n\n" + base64.b64encode("Fallback 中文".encode()), policy=policy.default
    )
    assert mail_service._body_text(base64_message) == "Base64 中文"
    assert mail_service._body_text(quoted_printable_message) == "QP 中文"
    assert mail_service._body_text(unknown_charset_message) == "Fallback 中文"


def test_mime_text_decoding_recovers_chinese_from_a_wrong_latin1_declaration() -> None:
    """ISO-8859-1 is permissive, so a GBK fallback needs an explicit heuristic."""
    from app.services import mail_service

    wrong_declared = message_from_bytes(
        b"Content-Type: text/plain; charset=iso-8859-1\nContent-Transfer-Encoding: base64\n\n"
        + base64.b64encode("错误声明也应显示中文".encode("gbk")),
        policy=policy.default,
    )
    assert mail_service._body_text(wrong_declared) == "错误声明也应显示中文"


def test_uidvalidity_accepts_standard_imap_response_atom() -> None:
    from app.services import mail_service

    class ResponseAtomImap:
        def response(self, _key):
            return "UIDVALIDITY", [b"987654"]

    assert mail_service._uid_validity(ResponseAtomImap()) == "987654"


def test_custom_folder_draft_and_bulk_flags_keep_existing_mail_data(client: TestClient, monkeypatch) -> None:
    """New productivity state is additive: it files and flags an existing message."""
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://crm.example.test")
    get_settings.cache_clear()
    admin = _login(client, "admin@example.com", "AdminPass123!")
    customer = client.post("/api/v1/customers", json={"company_name": "Folder customer", "email": "folder@example.com"}, headers=admin).json()
    folder = client.post("/api/v1/mail/folders", json={"name": "Folder customer", "customer_id": customer["id"], "bound_addresses": ["folder@example.com"]}, headers=admin)
    assert folder.status_code == 201
    fake = IncrementalFakeImap({1: (_raw_mail("folder-test", sender="folder@example.com"), False)})
    monkeypatch.setattr(mail_service, "_open_imap", lambda _settings: fake)
    assert client.post("/api/v1/mail/sync", headers=admin).status_code == 200
    item = client.get("/api/v1/mail/messages", params={"folder": "inbox"}, headers=admin).json()["items"][0]
    assert item["customer_id"] == customer["id"]
    assert item["mail_folder_id"] == folder.json()["id"]
    updated = client.post("/api/v1/mail/messages/bulk", params={"is_starred": True, "is_read": True}, json=[item["id"]], headers=admin)
    assert updated.status_code == 200
    assert updated.json()[0]["is_starred"] is True
    starred = client.get("/api/v1/mail/messages", params={"folder": "starred"}, headers=admin).json()
    assert starred["total"] == 1 and starred["items"][0]["is_read"] is True
    draft = client.post("/api/v1/mail/drafts", data={"to_emails": "folder@example.com", "subject": "Draft", "body": "draft body"}, headers=admin)
    assert draft.status_code == 201
    drafts = client.get("/api/v1/mail/messages", params={"folder": "drafts"}, headers=admin).json()
    assert drafts["total"] == 1 and drafts["items"][0]["is_draft"] is True


def test_individual_send_is_sequential_deduplicated_and_records_each_success(client: TestClient, monkeypatch) -> None:
    from app.config import get_settings
    from app.services import mail_service

    monkeypatch.setenv("MAIL_USERNAME", "crm@example.com")
    monkeypatch.setenv("MAIL_AUTH_CODE", "test-code")
    monkeypatch.setenv("APP_PUBLIC_URL", "https://crm.example.test")
    get_settings.cache_clear()
    admin = _login(client, "admin@example.com", "AdminPass123!")
    sent_to: list[str] = []
    monkeypatch.setattr(mail_service, "_smtp_send", lambda _settings, message: sent_to.append(str(message["To"])))
    response = client.post("/api/v1/mail/send-individually", data={"to_emails": "a@example.com; b@example.com\na@example.com; invalid", "subject": "Individual", "body": "Body"}, headers=admin)
    assert response.status_code == 201
    assert sent_to == ["a@example.com", "b@example.com"]
    assert len(response.json()["sent"]) == 2
    page = client.get("/api/v1/mail/messages", params={"folder": "sent"}, headers=admin).json()
    assert page["total"] == 2
