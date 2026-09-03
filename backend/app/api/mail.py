from io import BytesIO

import hmac

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User, UserRole
from app.config import get_settings
from app.schemas.mail import EmailMessagePage, EmailMessageRead, MailFolderCounts, MailSyncResult
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
    folder: str = Query("inbox", pattern="^(inbox|sent|unread|all)$"),
    customer_id: int | None = Query(default=None, gt=0),
    query: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> EmailMessagePage:
    messages, total = mail_service.list_messages(session, current_user, folder=folder, customer_id=customer_id, query=query, limit=limit, offset=offset)
    return EmailMessagePage(items=messages, total=total)


@router.get("/counts", response_model=MailFolderCounts)
def get_mail_counts(session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> MailFolderCounts:
    return MailFolderCounts(**mail_service.folder_counts(session, current_user))


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
    tracking_enabled: bool = Form(default=True),
    customer_id: int | None = Form(default=None),
    reply_to_id: int | None = Form(default=None),
    forward_of_id: int | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> EmailMessageRead:
    try:
        attachments = []
        for upload in files:
            attachments.append((upload.filename or "attachment", upload.content_type, await upload.read(mail_service.MAX_ATTACHMENT_BYTES + 1)))
        return await mail_service.send_message(session, current_user, recipients=to_emails.replace(";", ",").split(","), subject=subject, body=body, customer_id=customer_id, reply_to_id=reply_to_id, forward_of_id=forward_of_id, attachments=attachments, tracking_enabled=tracking_enabled)
    except (NotFoundError, ForbiddenError, ConflictError, mail_service.MailConfigurationError, StorageConfigurationError) as error:
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
