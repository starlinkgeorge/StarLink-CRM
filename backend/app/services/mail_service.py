"""Manual QQ/Foxmail IMAP/SMTP mail integration.

Credentials are deliberately read only from runtime environment settings.  The
database stores message metadata and attachment object keys, never passwords or
authorization codes.
"""

import html
import imaplib
import json
import logging
import re
import smtplib
from datetime import datetime, timezone
from email import message_from_bytes, policy
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import getaddresses, parsedate_to_datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models.customer import Contact, Customer
from app.models.mail import EmailAttachment, EmailMessage as StoredEmailMessage
from app.models.user import User, UserRole
from app.services.errors import ConflictError, ForbiddenError, NotFoundError, StorageConfigurationError
from app.services.storage_service import get_attachment_storage

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_SYNC_MESSAGES = 100
logger = logging.getLogger(__name__)
_LIST_RESPONSE_RE = re.compile(
    r"^\((?P<flags>[^)]*)\)\s+(?P<delimiter>NIL|\"(?:[^\"\\]|\\.)*\"|\S+)\s+(?P<mailbox>.+)$"
)


class MailConfigurationError(Exception):
    pass


def _settings() -> dict[str, str]:
    settings = get_settings()
    if not settings["mail_username"] or not settings["mail_auth_code"]:
        raise MailConfigurationError("MAIL_USERNAME and MAIL_AUTH_CODE must be configured before using mail.")
    return settings


def _addresses(value: str | None) -> list[str]:
    return [address.strip().lower() for _, address in getaddresses([value or ""]) if address.strip()]


def _header(value: object | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(str(value))))
    except (UnicodeError, ValueError):
        return str(value)


def _body_text(message) -> str:
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    content = part.get_content()
    if part.get_content_type() == "text/html":
        content = re.sub(r"<[^>]+>", " ", content)
        content = html.unescape(content)
    return content.strip()[:100000]


def _sent_at(message) -> datetime:
    try:
        value = parsedate_to_datetime(message.get("Date"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value
    except (TypeError, ValueError, IndexError):
        return datetime.now(timezone.utc)


def _safe_name(file_name: str) -> str:
    safe_name = Path(file_name.replace("\\", "/")).name.strip()
    if not safe_name:
        raise ConflictError("Attachment file name is required.")
    return safe_name[:255]


def _find_customer(session: Session, addresses: list[str]) -> Customer | None:
    addresses = [address.lower() for address in addresses if address]
    if not addresses:
        return None
    return session.scalar(
        select(Customer)
        .outerjoin(Contact, Contact.customer_id == Customer.id)
        .where(or_(func.lower(Customer.email).in_(addresses), func.lower(Contact.email).in_(addresses)))
        .order_by(Customer.id)
        .limit(1)
    )


def _load_message(session: Session, message_id: int) -> StoredEmailMessage:
    message = session.scalar(
        select(StoredEmailMessage)
        .where(StoredEmailMessage.id == message_id)
        .options(selectinload(StoredEmailMessage.attachments))
    )
    if message is None:
        raise NotFoundError("Email message not found.")
    return message


def ensure_read_access(user: User, message: StoredEmailMessage) -> None:
    if user.role is not UserRole.SALES:
        return
    if message.created_by_id == user.id:
        return
    if message.customer is not None and message.customer.owner_id == user.id:
        return
    raise ForbiddenError("You may only access email related to your customers or sent by you.")


def _query_for_user(session: Session, user: User):
    statement = select(StoredEmailMessage).options(
        selectinload(StoredEmailMessage.attachments), selectinload(StoredEmailMessage.customer)
    )
    if user.role is UserRole.SALES:
        statement = statement.outerjoin(Customer, StoredEmailMessage.customer_id == Customer.id).where(
            or_(Customer.owner_id == user.id, StoredEmailMessage.created_by_id == user.id)
        )
    return statement


def list_messages(session: Session, user: User, *, folder: str, customer_id: int | None, query: str | None, limit: int, offset: int) -> tuple[list[StoredEmailMessage], int]:
    statement = _query_for_user(session, user)
    count_statement = _query_for_user(session, user).with_only_columns(func.count(StoredEmailMessage.id)).order_by(None)
    if folder != "all":
        statement = statement.where(StoredEmailMessage.folder == folder)
        count_statement = count_statement.where(StoredEmailMessage.folder == folder)
    if customer_id is not None:
        statement = statement.where(StoredEmailMessage.customer_id == customer_id)
        count_statement = count_statement.where(StoredEmailMessage.customer_id == customer_id)
    if query:
        pattern = f"%{query.strip()}%"
        filter_clause = or_(StoredEmailMessage.subject.ilike(pattern), StoredEmailMessage.from_email.ilike(pattern), StoredEmailMessage.body_text.ilike(pattern))
        statement = statement.where(filter_clause)
        count_statement = count_statement.where(filter_clause)
    total = int(session.scalar(count_statement) or 0)
    messages = list(session.scalars(statement.order_by(StoredEmailMessage.sent_at.desc(), StoredEmailMessage.id.desc()).offset(offset).limit(limit)))
    return messages, total


async def _store_attachment(session: Session, message: StoredEmailMessage, file_name: str, content_type: str | None, content: bytes) -> EmailAttachment:
    safe_name = _safe_name(file_name)
    if not content or len(content) > MAX_ATTACHMENT_BYTES:
        raise ConflictError("Attachment must be between 1 byte and 10 MB.")
    storage_key = f"mail-{uuid4().hex}{Path(safe_name).suffix.lower()}"
    storage = get_attachment_storage()
    stored_name = await storage.put(storage_key, content, content_type)
    attachment = EmailAttachment(email_message_id=message.id, file_name=safe_name, stored_name=stored_name, content_type=(content_type or None), size_bytes=len(content))
    session.add(attachment)
    return attachment


async def _persist_imap_message(session: Session, raw: bytes, *, folder: str, sync_key: str) -> bool:
    parsed = message_from_bytes(raw, policy=policy.default)
    message_id = _header(parsed.get("Message-ID")) or None
    existing = session.scalar(select(StoredEmailMessage.id).where(StoredEmailMessage.sync_key == sync_key))
    if existing is None and message_id:
        existing = session.scalar(select(StoredEmailMessage.id).where(StoredEmailMessage.message_id == message_id))
    if existing is not None:
        return False
    from_email = (_addresses(_header(parsed.get("From"))) or [""])[0]
    to_emails = _addresses(_header(parsed.get("To")))
    cc_emails = _addresses(_header(parsed.get("Cc")))
    candidates = [from_email, *to_emails, *cc_emails]
    customer = _find_customer(session, candidates)
    message = StoredEmailMessage(
        customer_id=(customer.id if customer else None),
        folder=folder,
        direction="incoming" if folder == "inbox" else "outgoing",
        sync_key=sync_key,
        message_id=message_id,
        subject=_header(parsed.get("Subject"))[:500],
        from_email=from_email[:320],
        to_emails=json.dumps(to_emails),
        cc_emails=json.dumps(cc_emails),
        body_text=_body_text(parsed),
        sent_at=_sent_at(parsed),
        has_attachments=any(part.get_content_disposition() == "attachment" for part in parsed.walk()),
    )
    session.add(message)
    session.flush()
    try:
        for part in parsed.iter_attachments():
            payload = part.get_payload(decode=True) or b""
            if payload and len(payload) <= MAX_ATTACHMENT_BYTES:
                await _store_attachment(session, message, part.get_filename() or "attachment", part.get_content_type(), payload)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return True


def _open_imap(settings: dict[str, str]):
    client = imaplib.IMAP4_SSL(settings["mail_imap_host"], int(settings["mail_imap_port"]))
    client.login(settings["mail_username"], settings["mail_auth_code"])
    return client


def _decode_list_value(value: bytes | str) -> str:
    """Keep the server's mailbox representation intact (including modified UTF-7)."""
    if isinstance(value, bytes):
        return value.decode("ascii", errors="surrogateescape")
    return value


def _unquote_mailbox(value: str) -> str | None:
    value = value.strip()
    if not value or value.upper() == "NIL" or value.startswith("{"):
        # Literal LIST responses need a continuation value which imaplib does
        # not expose as one portable mailbox string.  Do not guess a name.
        return None
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
        return re.sub(r"\\(.)", r"\1", value)
    return value


def _parse_list_response(value: bytes | str) -> tuple[set[str], str] | None:
    match = _LIST_RESPONSE_RE.match(_decode_list_value(value))
    if match is None:
        return None
    mailbox = _unquote_mailbox(match.group("mailbox"))
    if mailbox is None:
        return None
    flags = {flag.lower() for flag in re.findall(r"\\[^\s()]+", match.group("flags"))}
    return flags, mailbox


def _imap_quote(mailbox: str) -> str:
    """Return one IMAP astring, never an unquoted list of command arguments."""
    if mailbox.upper() == "INBOX":
        return "INBOX"
    return '"' + mailbox.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _mailboxes_to_sync(client, configured_sent_folder: str) -> list[tuple[str, str]]:
    """Choose INBOX plus the server-advertised Sent mailbox, without guessing names."""
    mailboxes: list[tuple[str, str]] = [("INBOX", "inbox")]
    sent_mailbox: str | None = None
    try:
        status, entries = client.list()
        if status == "OK":
            for entry in entries or []:
                parsed = _parse_list_response(entry)
                if parsed is not None and "\\sent" in parsed[0]:
                    sent_mailbox = parsed[1]
                    break
        else:
            logger.warning("IMAP LIST failed while discovering the Sent mailbox: %s", status)
    except (imaplib.IMAP4.error, OSError) as error:
        logger.warning("IMAP LIST failed while discovering the Sent mailbox: %s", error)

    if sent_mailbox:
        mailboxes.append((sent_mailbox, "sent"))
    elif configured_sent_folder:
        # The configured name is intentionally still quoted before EXAMINE.
        mailboxes.append((configured_sent_folder, "sent"))
    else:
        logger.warning("No IMAP mailbox with the \\Sent flag was found; skipping Sent synchronization.")
    return mailboxes


async def sync_mailbox(session: Session) -> tuple[int, int, list[str]]:
    settings = _settings()
    client = _open_imap(settings)
    imported = skipped = 0
    folders = _mailboxes_to_sync(client, settings["mail_imap_sent_folder"])
    completed_folders: list[str] = []
    try:
        for mailbox, folder in folders:
            try:
                status, _ = client.select(_imap_quote(mailbox), readonly=True)
                if status != "OK":
                    logger.warning("Skipping IMAP %s mailbox because EXAMINE returned %s.", folder, status)
                    continue
                status, data = client.uid("search", None, "ALL")
                if status != "OK":
                    logger.warning("Skipping IMAP %s mailbox because UID SEARCH returned %s.", folder, status)
                    continue
                for uid in (data[0].split()[-MAX_SYNC_MESSAGES:] if data else []):
                    try:
                        status, data = client.uid("fetch", uid, "(RFC822)")
                    except (imaplib.IMAP4.error, OSError) as error:
                        logger.warning("Skipping one IMAP message in %s because UID FETCH failed: %s", folder, error)
                        continue
                    if status != "OK" or not data:
                        continue
                    raw = next((item[1] for item in data if isinstance(item, tuple) and isinstance(item[1], bytes)), None)
                    if raw is None:
                        continue
                    if await _persist_imap_message(session, raw, folder=folder, sync_key=f"imap:{mailbox}:{uid.decode(errors='replace')}"):
                        imported += 1
                    else:
                        skipped += 1
                completed_folders.append(folder)
            except (imaplib.IMAP4.error, OSError) as error:
                logger.warning("Skipping IMAP %s mailbox because it cannot be selected: %s", folder, error)
    finally:
        try:
            client.logout()
        except Exception:
            pass
    return imported, skipped, completed_folders


def _smtp_send(settings: dict[str, str], message: EmailMessage) -> None:
    with smtplib.SMTP_SSL(settings["mail_smtp_host"], int(settings["mail_smtp_port"])) as client:
        client.login(settings["mail_username"], settings["mail_auth_code"])
        client.send_message(message)


async def send_message(session: Session, user: User, *, recipients: list[str], subject: str, body: str, customer_id: int | None, reply_to_id: int | None, attachments: list[tuple[str, str | None, bytes]]) -> StoredEmailMessage:
    if user.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts cannot send email.")
    settings = _settings()
    recipients = [email.strip().lower() for email in recipients if email.strip()]
    if not recipients:
        raise ConflictError("At least one recipient is required.")
    if len(subject.strip()) > 500 or not subject.strip():
        raise ConflictError("Email subject is required and must be at most 500 characters.")
    customer = session.get(Customer, customer_id) if customer_id else _find_customer(session, recipients)
    if customer_id and customer is None:
        raise NotFoundError("Customer not found.")
    if user.role is UserRole.SALES and customer is not None and customer.owner_id != user.id:
        raise ForbiddenError("You may only send email for customers assigned to you.")
    parent = _load_message(session, reply_to_id) if reply_to_id else None
    if parent is not None:
        ensure_read_access(user, parent)
    outbound = EmailMessage()
    outbound["From"] = settings["mail_username"]
    outbound["To"] = ", ".join(recipients)
    outbound["Subject"] = subject.strip()
    outbound["Message-ID"] = f"<{uuid4().hex}@starlink-crm.local>"
    if parent and parent.message_id:
        outbound["In-Reply-To"] = parent.message_id
        outbound["References"] = parent.message_id
    outbound.set_content(body or "")
    for file_name, content_type, content in attachments:
        safe_name = _safe_name(file_name)
        if not content or len(content) > MAX_ATTACHMENT_BYTES:
            raise ConflictError("Each attachment must be between 1 byte and 10 MB.")
        main_type, sub_type = (content_type or "application/octet-stream").split("/", 1) if "/" in (content_type or "") else ("application", "octet-stream")
        outbound.add_attachment(content, maintype=main_type, subtype=sub_type, filename=safe_name)
    _smtp_send(settings, outbound)
    stored = StoredEmailMessage(customer_id=customer.id if customer else None, created_by_id=user.id, in_reply_to_id=parent.id if parent else None, folder="sent", direction="outgoing", sync_key=f"smtp:{uuid4().hex}", message_id=str(outbound["Message-ID"]), subject=subject.strip(), from_email=settings["mail_username"].lower(), to_emails=json.dumps(recipients), cc_emails="[]", body_text=body or "", sent_at=datetime.now(timezone.utc), has_attachments=bool(attachments))
    session.add(stored)
    session.flush()
    try:
        for file_name, content_type, content in attachments:
            await _store_attachment(session, stored, file_name, content_type, content)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return _load_message(session, stored.id)


def get_message(session: Session, user: User, message_id: int) -> StoredEmailMessage:
    message = _load_message(session, message_id)
    ensure_read_access(user, message)
    return message


async def attachment_bytes(attachment: EmailAttachment) -> bytes:
    return await get_attachment_storage().get(attachment.stored_name)
