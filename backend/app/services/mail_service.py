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
from secrets import token_urlsafe
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db.session import get_session_factory
from app.models.customer import Contact, Customer
from app.models.mail import EmailAttachment, EmailMessage as StoredEmailMessage, EmailOpenEvent, MailboxSyncState
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


class MailSyncInProgressError(ConflictError):
    pass


def _settings() -> dict[str, str]:
    settings = get_settings()
    if not settings["mail_username"] or not settings["mail_auth_code"]:
        raise MailConfigurationError("MAIL_USERNAME and MAIL_AUTH_CODE must be configured before using mail.")
    return settings


def _decode_bytes(value: bytes, declared_charset: str | None = None) -> str:
    """Decode real-world MIME bytes without propagating malformed charset errors."""
    candidates = [declared_charset, "utf-8", "gb18030", "gbk", "gb2312", "iso-8859-1"]
    tried: set[str] = set()
    for charset in candidates:
        if not charset:
            continue
        normalized = charset.strip().lower().replace("_", "-")
        if normalized in tried:
            continue
        tried.add(normalized)
        try:
            return value.decode(normalized)
        except (LookupError, UnicodeDecodeError):
            continue
    return value.decode("utf-8", errors="replace")


def _header(value: object | None) -> str:
    if not value:
        return ""
    try:
        parts = decode_header(str(value))
    except (UnicodeError, ValueError):
        return str(value)
    decoded: list[str] = []
    for part, charset in parts:
        decoded.append(_decode_bytes(part, charset) if isinstance(part, bytes) else str(part))
    return "".join(decoded)


def _addresses(value: str | None) -> list[str]:
    return [address.strip().lower() for _, address in getaddresses([_header(value)]) if address.strip()]


def _display_addresses(value: str | None) -> list[str]:
    result: list[str] = []
    for display_name, address in getaddresses([_header(value)]):
        if not address:
            continue
        name = _header(display_name).strip()
        result.append(f"{name} <{address}>" if name else address)
    return result


def _html_to_text(content: str) -> str:
    content = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", content)
    content = re.sub(r"(?i)<br\s*/?>", "\n", content)
    content = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", "\n", content)
    content = re.sub(r"<[^>]+>", " ", content)
    return re.sub(r"[ \t]+", " ", html.unescape(content)).strip()


def _part_text(part) -> str:
    try:
        payload = part.get_payload(decode=True)
    except (ValueError, UnicodeError):
        payload = None
    if isinstance(payload, bytes):
        return _decode_bytes(payload, part.get_content_charset())
    raw = part.get_payload()
    return raw if isinstance(raw, str) else ""


def _body_text(message) -> str:
    text_parts = [part for part in message.walk() if part.get_content_maintype() == "text" and part.get_content_disposition() != "attachment"]
    plain = next((part for part in text_parts if part.get_content_type() == "text/plain"), None)
    html_part = next((part for part in text_parts if part.get_content_type() == "text/html"), None)
    part = plain or html_part
    if part is None:
        return ""
    content = _part_text(part)
    if part.get_content_type() == "text/html":
        content = _html_to_text(content)
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
    if folder == "unread":
        statement = statement.where(StoredEmailMessage.direction == "incoming", StoredEmailMessage.is_read.is_(False))
        count_statement = count_statement.where(StoredEmailMessage.direction == "incoming", StoredEmailMessage.is_read.is_(False))
    elif folder != "all":
        statement = statement.where(StoredEmailMessage.folder == folder)
        count_statement = count_statement.where(StoredEmailMessage.folder == folder)
    if customer_id is not None:
        statement = statement.where(StoredEmailMessage.customer_id == customer_id)
        count_statement = count_statement.where(StoredEmailMessage.customer_id == customer_id)
    if query:
        pattern = f"%{query.strip()}%"
        filter_clause = or_(
            StoredEmailMessage.subject.ilike(pattern),
            StoredEmailMessage.from_email.ilike(pattern),
            StoredEmailMessage.to_emails.ilike(pattern),
            StoredEmailMessage.cc_emails.ilike(pattern),
            StoredEmailMessage.body_text.ilike(pattern),
        )
        statement = statement.where(filter_clause)
        count_statement = count_statement.where(filter_clause)
    total = int(session.scalar(count_statement) or 0)
    messages = list(session.scalars(statement.order_by(StoredEmailMessage.sent_at.desc(), StoredEmailMessage.id.desc()).offset(offset).limit(limit)))
    return messages, total


def folder_counts(session: Session, user: User) -> dict[str, int]:
    statement = _query_for_user(session, user).with_only_columns(
        func.coalesce(func.sum(case((StoredEmailMessage.folder == "inbox", 1), else_=0)), 0).label("inbox"),
        func.coalesce(func.sum(case((StoredEmailMessage.folder == "sent", 1), else_=0)), 0).label("sent"),
        func.coalesce(func.sum(case((
            (StoredEmailMessage.direction == "incoming") & (StoredEmailMessage.is_read.is_(False)), 1
        ), else_=0)), 0).label("unread"),
    )
    row = session.execute(statement).one()
    return {"inbox": int(row.inbox), "sent": int(row.sent), "unread": int(row.unread)}


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


async def _persist_imap_message(session: Session, raw: bytes, *, folder: str, sync_key: str, is_read: bool) -> bool:
    parsed = message_from_bytes(raw, policy=policy.default)
    message_id = _header(parsed.get("Message-ID")) or None
    existing = session.scalar(select(StoredEmailMessage.id).where(StoredEmailMessage.sync_key == sync_key))
    if existing is None and message_id:
        existing = session.scalar(select(StoredEmailMessage.id).where(StoredEmailMessage.message_id == message_id))
    if existing is not None:
        return False
    from_header = _header(parsed.get("From"))
    from_email = (_addresses(from_header) or [""])[0]
    from_names = getaddresses([from_header])
    from_name = _header(from_names[0][0]).strip() if from_names else None
    to_emails = _addresses(parsed.get("To"))
    cc_emails = _addresses(parsed.get("Cc"))
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
        from_name=from_name[:500] if from_name else None,
        to_emails=json.dumps(to_emails),
        cc_emails=json.dumps(cc_emails),
        to_display=json.dumps(_display_addresses(parsed.get("To"))),
        cc_display=json.dumps(_display_addresses(parsed.get("Cc"))),
        body_text=_body_text(parsed),
        sent_at=_sent_at(parsed),
        has_attachments=any(part.get_content_disposition() == "attachment" for part in parsed.walk()),
        is_read=is_read,
        tracking_enabled=False,
    )
    session.add(message)
    session.flush()
    try:
        for part in parsed.iter_attachments():
            payload = part.get_payload(decode=True) or b""
            if payload and len(payload) <= MAX_ATTACHMENT_BYTES:
                file_name = _header(part.get_filename()) or "attachment"
                await _store_attachment(session, message, file_name, part.get_content_type(), payload)
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


_SYNC_LOCK_KEY = 834_173_299


def _acquire_sync_lock(session: Session) -> Session | None:
    """Use a PostgreSQL session-level advisory lock across Cron and manual runs."""
    if session.get_bind().dialect.name != "postgresql":
        # SQLite is only used by isolated tests; production uses PostgreSQL.
        return None
    lock_session = get_session_factory()()
    acquired = bool(lock_session.scalar(select(func.pg_try_advisory_lock(_SYNC_LOCK_KEY))))
    if not acquired:
        lock_session.close()
        raise MailSyncInProgressError("A mailbox synchronization is already running.")
    return lock_session


def _release_sync_lock(lock_session: Session | None) -> None:
    if lock_session is None:
        return
    try:
        lock_session.scalar(select(func.pg_advisory_unlock(_SYNC_LOCK_KEY)))
    finally:
        lock_session.close()


def _uid_validity(client) -> str | None:
    try:
        status, values = client.response("UIDVALIDITY")
    except (AttributeError, imaplib.IMAP4.error, OSError):
        return None
    # imaplib returns either ``OK`` or the response atom itself depending on
    # server/version.  Both forms carry the UIDVALIDITY payload; only a real
    # failure response must be ignored.
    if str(status).upper() in {"NO", "BAD"} or not values:
        return None
    value = values[0]
    return value.decode(errors="replace") if isinstance(value, bytes) else str(value)


def _uids_from_search(data) -> list[int]:
    raw_uids = data[0].split() if data and data[0] else []
    result: list[int] = []
    for raw_uid in raw_uids:
        try:
            result.append(int(raw_uid))
        except (TypeError, ValueError):
            logger.warning("Skipping malformed IMAP UID: %r", raw_uid)
    return sorted(set(result))


def _flags_from_fetch(data) -> set[str]:
    for item in data or []:
        if isinstance(item, tuple):
            metadata = item[0]
            text = metadata.decode(errors="replace") if isinstance(metadata, bytes) else str(metadata)
            return {flag.lower() for flag in re.findall(r"\\[^\s()]+", text)}
    return set()


def _advance_sync_state(session: Session, state_id: int, uid: int) -> None:
    state = session.get(MailboxSyncState, state_id)
    if state is None:
        return
    state.last_synced_uid = uid
    state.last_synced_at = datetime.now(timezone.utc)
    session.commit()


async def sync_mailbox(session: Session) -> tuple[int, int, list[str]]:
    """Synchronize only unseen IMAP UIDs after an initial bounded import."""
    settings = _settings()
    lock_session = _acquire_sync_lock(session)
    client = None
    imported = skipped = 0
    completed_folders: list[str] = []
    try:
        # Opening the IMAP connection can fail too. Keep it inside the guarded
        # block so the advisory lock is always released in that case.
        client = _open_imap(settings)
        folders = _mailboxes_to_sync(client, settings["mail_imap_sent_folder"])
        for mailbox, folder in folders:
            try:
                status, _ = client.select(_imap_quote(mailbox), readonly=True)
                if status != "OK":
                    logger.warning("Skipping IMAP %s mailbox because EXAMINE returned %s.", folder, status)
                    continue
                uid_validity = _uid_validity(client) or "unknown"
                state = session.scalar(select(MailboxSyncState).where(MailboxSyncState.mailbox == mailbox))
                is_initial = state is None or state.uid_validity != uid_validity
                if state is None:
                    state = MailboxSyncState(mailbox=mailbox, uid_validity=uid_validity)
                    session.add(state)
                    session.commit()
                elif state.uid_validity != uid_validity:
                    # UID values belong to a different mailbox generation. Never
                    # compare them to old UIDs; start a new bounded window safely.
                    state.uid_validity = uid_validity
                    state.last_synced_uid = None
                    state.last_synced_at = None
                    session.commit()

                criterion = "ALL" if is_initial else f"UID {int(state.last_synced_uid or 0) + 1}:*"
                status, data = client.uid("search", None, criterion)
                if status != "OK":
                    logger.warning("Skipping IMAP %s mailbox because UID SEARCH returned %s.", folder, status)
                    continue
                uids = _uids_from_search(data)
                if is_initial:
                    uids = uids[-MAX_SYNC_MESSAGES:]
                for uid in uids:
                    try:
                        status, data = client.uid("fetch", str(uid), "(RFC822 FLAGS)")
                        if status != "OK" or not data:
                            logger.warning("Skipping one IMAP message in %s because UID FETCH returned %s.", folder, status)
                            skipped += 1
                            _advance_sync_state(session, state.id, uid)
                            continue
                        raw = next((item[1] for item in data if isinstance(item, tuple) and isinstance(item[1], bytes)), None)
                        if raw is None:
                            logger.warning("Skipping one IMAP message in %s because it had no RFC822 payload.", folder)
                            skipped += 1
                        elif await _persist_imap_message(
                            session,
                            raw,
                            folder=folder,
                            sync_key=f"imap:{mailbox}:{uid_validity}:{uid}",
                            is_read=("\\seen" in _flags_from_fetch(data)),
                        ):
                            imported += 1
                        else:
                            skipped += 1
                    except Exception as error:
                        session.rollback()
                        logger.warning("Skipping one IMAP message in %s at UID %s: %s", folder, uid, error)
                        skipped += 1
                    finally:
                        # A malformed individual message must not block later UIDs.
                        _advance_sync_state(session, state.id, uid)
                completed_folders.append(folder)
            except (imaplib.IMAP4.error, OSError) as error:
                session.rollback()
                logger.warning("Skipping IMAP %s mailbox because it cannot be selected: %s", folder, error)
            except Exception as error:
                session.rollback()
                logger.warning("Skipping IMAP %s mailbox because synchronization failed: %s", folder, error)
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass
        _release_sync_lock(lock_session)
    return imported, skipped, completed_folders


def _smtp_send(settings: dict[str, str], message: EmailMessage) -> None:
    with smtplib.SMTP_SSL(settings["mail_smtp_host"], int(settings["mail_smtp_port"])) as client:
        client.login(settings["mail_username"], settings["mail_auth_code"])
        client.send_message(message)


def _tracking_pixel_url(settings: dict[str, str], token: str) -> str:
    public_url = settings["app_public_url"]
    parsed = urlsplit(public_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise MailConfigurationError(
            "APP_PUBLIC_URL must be configured as a public HTTPS URL before email open tracking can be enabled."
        )
    return f"{public_url}/api/v1/mail/track/{token}.gif"


def _new_tracking_token(session: Session) -> str:
    """Generate a high-entropy, unguessable token which is not a message ID."""
    for _ in range(5):
        token = token_urlsafe(32)
        if session.scalar(select(StoredEmailMessage.id).where(StoredEmailMessage.tracking_token == token)) is None:
            return token
    raise MailConfigurationError("Could not allocate a unique email tracking token. Please try again.")


def _html_with_tracking_pixel(body: str, pixel_url: str) -> str:
    escaped_body = html.escape(body or "").replace("\n", "<br>\n")
    escaped_url = html.escape(pixel_url, quote=True)
    return (
        "<!doctype html><html><body>"
        f"{escaped_body}<img src=\"{escaped_url}\" width=\"1\" height=\"1\" alt=\"\" "
        "style=\"display:none!important;width:1px;height:1px;border:0\" />"
        "</body></html>"
    )


async def send_message(session: Session, user: User, *, recipients: list[str], subject: str, body: str, customer_id: int | None, reply_to_id: int | None, forward_of_id: int | None, attachments: list[tuple[str, str | None, bytes]], tracking_enabled: bool = True) -> StoredEmailMessage:
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
    forwarded = _load_message(session, forward_of_id) if forward_of_id else None
    if forwarded is not None:
        ensure_read_access(user, forwarded)
    tracking_token = _new_tracking_token(session) if tracking_enabled else None
    outbound = EmailMessage()
    outbound["From"] = settings["mail_username"]
    outbound["To"] = ", ".join(recipients)
    outbound["Subject"] = subject.strip()
    outbound["Message-ID"] = f"<{uuid4().hex}@starlink-crm.local>"
    if parent and parent.message_id:
        outbound["In-Reply-To"] = parent.message_id
        outbound["References"] = parent.message_id
    outbound.set_content(body or "")
    if tracking_token is not None:
        outbound.add_alternative(
            _html_with_tracking_pixel(body, _tracking_pixel_url(settings, tracking_token)), subtype="html"
        )
    for file_name, content_type, content in attachments:
        safe_name = _safe_name(file_name)
        if not content or len(content) > MAX_ATTACHMENT_BYTES:
            raise ConflictError("Each attachment must be between 1 byte and 10 MB.")
        main_type, sub_type = (content_type or "application/octet-stream").split("/", 1) if "/" in (content_type or "") else ("application", "octet-stream")
        outbound.add_attachment(content, maintype=main_type, subtype=sub_type, filename=safe_name)
    _smtp_send(settings, outbound)
    stored = StoredEmailMessage(customer_id=customer.id if customer else (forwarded.customer_id if forwarded else None), created_by_id=user.id, in_reply_to_id=parent.id if parent else None, forwarded_from_id=forwarded.id if forwarded else None, folder="sent", direction="outgoing", sync_key=f"smtp:{uuid4().hex}", message_id=str(outbound["Message-ID"]), subject=subject.strip(), from_email=settings["mail_username"].lower(), from_name=None, to_emails=json.dumps(recipients), cc_emails="[]", to_display=json.dumps(recipients), cc_display="[]", body_text=body or "", sent_at=datetime.now(timezone.utc), has_attachments=bool(attachments), is_read=True, tracking_enabled=tracking_enabled, tracking_token=tracking_token)
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


def record_email_open(session: Session, token: str) -> None:
    """Best-effort state update for an external pixel request.

    Only CRM-originated outgoing messages that explicitly opted into tracking
    can be updated. No caller-visible information is returned.
    """
    if not token or len(token) > 128:
        return
    message = session.scalar(
        select(StoredEmailMessage).where(
            StoredEmailMessage.tracking_token == token,
            StoredEmailMessage.tracking_enabled.is_(True),
            StoredEmailMessage.direction == "outgoing",
        )
    )
    if message is None:
        return
    opened_at = datetime.now(timezone.utc)
    if message.first_opened_at is None:
        message.first_opened_at = opened_at
    message.last_opened_at = opened_at
    message.open_count += 1
    session.add(EmailOpenEvent(email_message_id=message.id, opened_at=opened_at))
    session.commit()


def get_message(session: Session, user: User, message_id: int) -> StoredEmailMessage:
    message = _load_message(session, message_id)
    ensure_read_access(user, message)
    return message


def set_message_read_state(session: Session, user: User, message_id: int, *, is_read: bool) -> StoredEmailMessage:
    message = _load_message(session, message_id)
    ensure_read_access(user, message)
    # This is deliberately CRM-local. Changing it must not set or clear the
    # mailbox's IMAP \Seen flag and interfere with Foxmail/QQ clients.
    message.is_read = is_read
    session.commit()
    return _load_message(session, message.id)


async def attachment_bytes(attachment: EmailAttachment) -> bytes:
    return await get_attachment_storage().get(attachment.stored_name)
