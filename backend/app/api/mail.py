from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User, UserRole
from app.schemas.mail import EmailMessagePage, EmailMessageRead, MailSyncResult
from app.services import mail_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError, StorageConfigurationError

router = APIRouter(prefix="/mail", tags=["mail"])


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


@router.get("/messages", response_model=EmailMessagePage)
def list_email_messages(
    folder: str = Query("inbox", pattern="^(inbox|sent|all)$"),
    customer_id: int | None = Query(default=None, gt=0),
    query: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> EmailMessagePage:
    messages, total = mail_service.list_messages(session, current_user, folder=folder, customer_id=customer_id, query=query, limit=limit, offset=offset)
    return EmailMessagePage(items=messages, total=total)


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
    except (mail_service.MailConfigurationError, StorageConfigurationError, ConflictError) as error:
        _raise(error)


@router.post("/send", response_model=EmailMessageRead, status_code=status.HTTP_201_CREATED)
async def send_email(
    to_emails: str = Form(..., min_length=3, max_length=3000),
    subject: str = Form(..., min_length=1, max_length=500),
    body: str = Form("", max_length=100000),
    customer_id: int | None = Form(default=None),
    reply_to_id: int | None = Form(default=None),
    files: list[UploadFile] = File(default=[]),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> EmailMessageRead:
    try:
        attachments = []
        for upload in files:
            attachments.append((upload.filename or "attachment", upload.content_type, await upload.read(mail_service.MAX_ATTACHMENT_BYTES + 1)))
        return await mail_service.send_message(session, current_user, recipients=to_emails.replace(";", ",").split(","), subject=subject, body=body, customer_id=customer_id, reply_to_id=reply_to_id, attachments=attachments)
    except (NotFoundError, ForbiddenError, ConflictError, mail_service.MailConfigurationError, StorageConfigurationError) as error:
        _raise(error)
    finally:
        for upload in files:
            await upload.close()
