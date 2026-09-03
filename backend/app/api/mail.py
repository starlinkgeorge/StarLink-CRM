from io import BytesIO

import hmac
import json

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User, UserRole
from app.config import get_settings
from datetime import datetime, time, timedelta, timezone

from app.schemas.mail import EmailMessagePage, EmailMessageRead, IndividualSendResult, MailFolderCounts, MailFolderCreate, MailFolderRead, MailFolderUpdate, MailSyncResult
from app.services import mail_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError, StorageConfigurationError

router = APIRouter(prefix="/mail", tags=["mail"])

# A valid 1x1 transparent GIF. This response is intentionally independent of
# whether the optional database write for the open event succeeds.
TRANSPARENT_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01"
    b"\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)


def _raise(error: Exception) -> None:
    if isinstance(error, NotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, (ForbiddenError,)):
        raise HTTPException(status_code=403, detail=str(error)) from error
    if isinstance(error, (ConflictError,)):
        raise HTTPException(status_code=409, detail=str(error)) from error
    if isinstance(error, (mail_service.MailConfigurationError, StorageConfigurationError)):
        raise HTTPException(status_code=503, detail=str(error)) from error
    raise error


@router.get("/track/{token}.gif", include_in_schema=False)
def track_email_open(token: str, session: Session = Depends(get_db_session)) -> Response:
    """Record an external tracking-pixel request without disclosing email data."""
    try:
        mail_service.record_email_open(session, token)
    except Exception:
        # Tracking is best-effort. An outage must never turn a recipient's
        # image request into a broken image or leak a server-side error.
        try:
            session.rollback()
        except Exception:
            pass
    return Response(
        content=TRANSPARENT_GIF,
        media_type="image/gif",
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )


@router.get("/messages", response_model=EmailMessagePage)
def list_email_messages(
    folder: str = Query("inbox", pattern="^(inbox|sent|unread|drafts|starred|all)$"),
    customer_id: int | None = Query(default=None, gt=0),
    mail_folder_id: int | None = Query(default=None, gt=0),
    query: str | None = Query(default=None, max_length=200),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    has_attachments: bool | None = Query(default=None),
    is_read: bool | None = Query(default=None),
    is_starred: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> EmailMessagePage:
    messages, total = mail_service.list_messages(session, current_user, folder=folder, customer_id=customer_id, mail_folder_id=mail_folder_id, query=query, date_from=date_from, date_to=date_to, has_attachments=has_attachments, is_read=is_read, is_starred=is_starred, limit=limit, offset=offset)
    return EmailMessagePage(items=messages, total=total)


@router.get("/counts", response_model=MailFolderCounts)
def get_mail_counts(session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> MailFolderCounts:
    return MailFolderCounts(**mail_service.folder_counts(session, current_user))


@router.get("/folders", response_model=list[MailFolderRead])
def get_mail_folders(session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> list[MailFolderRead]:
    return [MailFolderRead(**item) for item in mail_service.list_custom_folders(session, current_user)]


@router.post("/folders", response_model=MailFolderRead, status_code=status.HTTP_201_CREATED)
def create_mail_folder(payload: MailFolderCreate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> MailFolderRead:
    try:
        folder = mail_service.save_custom_folder(session, current_user, folder_id=None, **payload.model_dump())
        return MailFolderRead(id=folder.id, name=folder.name, customer_id=folder.customer_id, bound_addresses=json.loads(folder.bound_addresses))
    except (NotFoundError, ForbiddenError, ConflictError) as error:
        _raise(error)


@router.put("/folders/{folder_id}", response_model=MailFolderRead)
def update_mail_folder(folder_id: int, payload: MailFolderUpdate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> MailFolderRead:
    try:
        folder = mail_service.save_custom_folder(session, current_user, folder_id=folder_id, **payload.model_dump())
        return MailFolderRead(id=folder.id, name=folder.name, customer_id=folder.customer_id, bound_addresses=json.loads(folder.bound_addresses))
    except (NotFoundError, ForbiddenError, ConflictError) as error:
        _raise(error)


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_mail_folder(folder_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> Response:
    try:
        mail_service.delete_custom_folder(session, current_user, folder_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except (NotFoundError, ForbiddenError) as error:
        _raise(error)


@router.get("/messages/{message_id}", response_model=EmailMessageRead)
def get_email_message(message_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> EmailMessageRead:
    try:
        return mail_service.get_message(session, current_user, message_id)
    except (NotFoundError, ForbiddenError) as error:
        _raise(error)


@router.get("/messages/{message_id}/attachments/{attachment_id}")
async def download_email_attachment(message_id: int, attachment_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> StreamingResponse:
    try:
        message = mail_service.get_message(session, current_user, message_id)
        attachment = next((item for item in message.attachments if item.id == attachment_id), None)
        if attachment is None:
            raise NotFoundError("Email attachment not found.")
        return StreamingResponse(BytesIO(await mail_service.attachment_bytes(attachment)), media_type=attachment.content_type or "application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{attachment.file_name}"'})
    except (NotFoundError, ForbiddenError, StorageConfigurationError) as error:
        _raise(error)


@router.post("/sync", response_model=MailSyncResult)
async def sync_email(session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> MailSyncResult:
    if current_user.role is not UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only administrators may synchronize the shared mailbox.")
    try:
        imported, skipped, folders = await mail_service.sync_mailbox(session)
        return MailSyncResult(imported=imported, skipped=skipped, folders=folders)
    except (mail_service.MailConfigurationError, StorageConfigurationError, ConflictError, mail_service.MailSyncInProgressError) as error:
        _raise(error)


@router.get("/cron/sync", response_model=MailSyncResult)
async def cron_sync_email(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_db_session),
) -> MailSyncResult:
    """Vercel Cron entrypoint. It deliberately has no browser-user dependency."""
    secret = get_settings()["cron_secret"]
    expected = f"Bearer {secret}"
    if not secret or not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid cron authorization.")
    try:
        imported, skipped, folders = await mail_service.sync_mailbox(session)
        return MailSyncResult(imported=imported, skipped=skipped, folders=folders)
    except mail_service.MailSyncInProgressError:
        return MailSyncResult(imported=0, skipped=0, folders=[], already_running=True)
    except (mail_service.MailConfigurationError, StorageConfigurationError, ConflictError) as error:
        _raise(error)


@router.post("/send", response_model=EmailMessageRead, status_code=status.HTTP_201_CREATED)
async def send_email(
    to_emails: str = Form(..., min_length=3, max_length=3000),
    subject: str = Form(..., min_length=1, max_length=500),
    body: str = Form("", max_length=100000),
    html_body: str = Form("", max_length=200000),
    cc_emails: str = Form("", max_length=3000),
    bcc_emails: str = Form("", max_length=3000),
    tracking_enabled: bool = Form(default=True),
    customer_id: int | None = Form(default=None),
    reply_to_id: int | None = Form(default=None),
    forward_of_id: int | None = Form(default=None),
    draft_id: int | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> EmailMessageRead:
    try:
        attachments = []
        for upload in files:
            attachments.append((upload.filename or "attachment", upload.content_type, await upload.read(mail_service.MAX_ATTACHMENT_BYTES + 1)))
        return await mail_service.send_message(session, current_user, recipients=to_emails.replace(";", ",").split(","), cc_recipients=cc_emails.replace(";", ",").split(","), bcc_recipients=bcc_emails.replace(";", ",").split(","), subject=subject, body=body, html_body=html_body, customer_id=customer_id, reply_to_id=reply_to_id, forward_of_id=forward_of_id, draft_id=draft_id, attachments=attachments, tracking_enabled=tracking_enabled)
    except (NotFoundError, ForbiddenError, ConflictError, mail_service.MailConfigurationError, StorageConfigurationError) as error:
        _raise(error)
    finally:
        for upload in files:
            await upload.close()


@router.post("/send-individually", response_model=IndividualSendResult, status_code=status.HTTP_201_CREATED)
async def send_email_individually(
    to_emails: str = Form(..., min_length=3, max_length=3000),
    subject: str = Form(..., min_length=1, max_length=500),
    body: str = Form("", max_length=100000), html_body: str = Form("", max_length=200000),
    cc_emails: str = Form("", max_length=3000), bcc_emails: str = Form("", max_length=3000),
    tracking_enabled: bool = Form(default=True), customer_id: int | None = Form(default=None),
    reply_to_id: int | None = Form(default=None), forward_of_id: int | None = Form(default=None),
    files: list[UploadFile] = File(default=[]), session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user),
) -> IndividualSendResult:
    try:
        recipients = mail_service.parse_recipient_addresses(to_emails)
        if not recipients:
            raise ConflictError("Enter at least one valid recipient email address.")
        attachments = [(upload.filename or "attachment", upload.content_type, await upload.read(mail_service.MAX_ATTACHMENT_BYTES + 1)) for upload in files]
        sent, failed = await mail_service.send_individually(session, current_user, recipients=recipients, cc_recipients=mail_service.parse_recipient_addresses(cc_emails), bcc_recipients=mail_service.parse_recipient_addresses(bcc_emails), subject=subject, body=body, html_body=html_body, customer_id=customer_id, reply_to_id=reply_to_id, forward_of_id=forward_of_id, attachments=attachments, tracking_enabled=tracking_enabled)
        return IndividualSendResult(sent=sent, failed_addresses=failed)
    except (NotFoundError, ForbiddenError, ConflictError, mail_service.MailConfigurationError, StorageConfigurationError) as error:
        _raise(error)
    finally:
        for upload in files:
            await upload.close()


@router.post("/drafts", response_model=EmailMessageRead, status_code=status.HTTP_201_CREATED)
async def save_email_draft(
    to_emails: str = Form("", max_length=3000),
    cc_emails: str = Form("", max_length=3000),
    bcc_emails: str = Form("", max_length=3000),
    subject: str = Form("", max_length=500),
    body: str = Form("", max_length=100000),
    html_body: str = Form("", max_length=200000),
    customer_id: int | None = Form(default=None),
    draft_id: int | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user),
) -> EmailMessageRead:
    try:
        attachments = [(upload.filename or "attachment", upload.content_type, await upload.read(mail_service.MAX_ATTACHMENT_BYTES + 1)) for upload in files]
        return await mail_service.save_draft(session, current_user, draft_id=draft_id, recipients=to_emails.replace(";", ",").split(","), cc_recipients=cc_emails.replace(";", ",").split(","), bcc_recipients=bcc_emails.replace(";", ",").split(","), subject=subject, body=body, html_body=html_body, customer_id=customer_id, attachments=attachments)
    except (NotFoundError, ForbiddenError, ConflictError, StorageConfigurationError) as error:
        _raise(error)
    finally:
        for upload in files:
            await upload.close()


@router.post("/messages/{message_id}/read", response_model=EmailMessageRead)
def mark_email_read(message_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> EmailMessageRead:
    try:
        return mail_service.set_message_read_state(session, current_user, message_id, is_read=True)
    except (NotFoundError, ForbiddenError) as error:
        _raise(error)


@router.post("/messages/{message_id}/unread", response_model=EmailMessageRead)
def mark_email_unread(message_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> EmailMessageRead:
    try:
        return mail_service.set_message_read_state(session, current_user, message_id, is_read=False)
    except (NotFoundError, ForbiddenError) as error:
        _raise(error)


@router.post("/messages/bulk", response_model=list[EmailMessageRead])
def bulk_update_messages(
    message_ids: list[int],
    is_read: bool | None = Query(default=None),
    is_starred: bool | None = Query(default=None),
    mail_folder_id: int | None = Query(default=None),
    clear_mail_folder: bool = Query(default=False),
    deleted: bool | None = Query(default=None),
    session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user),
) -> list[EmailMessageRead]:
    try:
        return mail_service.update_messages(session, current_user, message_ids, is_read=is_read, is_starred=is_starred, mail_folder_id=mail_folder_id, clear_mail_folder=clear_mail_folder, deleted=deleted)
    except (NotFoundError, ForbiddenError, ConflictError) as error:
        _raise(error)
