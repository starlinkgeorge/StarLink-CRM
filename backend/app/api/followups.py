from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User, UserRole
from app.schemas.followup import (
    FollowUpAttachmentRead,
    FollowUpCreate,
    FollowUpRead,
    FollowUpUpdate,
)
from app.services import access_service, customer_service, followup_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError

router = APIRouter(prefix="/followups", tags=["followups"])


def _raise_http_error(error: Exception) -> None:
    if isinstance(error, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    if isinstance(error, ForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    if isinstance(error, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    raise error


def _ensure_followup_write_access(
    session: Session, followup_id: int, current_user: User
):
    followup = followup_service.get_followup(session, followup_id)
    customer = customer_service.get_customer(session, followup.customer_id)
    access_service.ensure_customer_manage_access(current_user, customer)
    if current_user.role is UserRole.SALES and followup.user_id != current_user.id:
        raise ForbiddenError("Sales users may only edit or delete their own follow-up records.")
    return followup


@router.post("", response_model=FollowUpRead, status_code=status.HTTP_201_CREATED)
def create_followup(
    payload: FollowUpCreate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> FollowUpRead:
    try:
        customer = customer_service.get_customer(session, payload.customer_id)
        access_service.ensure_customer_manage_access(current_user, customer)
        user_id = payload.user_id or current_user.id
        if current_user.role is UserRole.SALES and user_id != current_user.id:
            raise ForbiddenError("Sales users may only create their own follow-up records.")
        payload_with_user = payload.model_copy(update={"user_id": user_id})
        return followup_service.create_followup(session, payload_with_user)
    except (NotFoundError, ForbiddenError, ConflictError) as error:
        _raise_http_error(error)


@router.get("", response_model=list[FollowUpRead])
def list_customer_followups(
    customer_id: int = Query(gt=0),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[FollowUpRead]:
    try:
        customer = customer_service.get_customer(session, customer_id)
        access_service.ensure_customer_read_access(current_user, customer)
        return followup_service.list_customer_followups(session, customer_id)
    except (NotFoundError, ForbiddenError) as error:
        _raise_http_error(error)


@router.put("/{followup_id}", response_model=FollowUpRead)
def update_followup(
    followup_id: int,
    payload: FollowUpUpdate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> FollowUpRead:
    try:
        _ensure_followup_write_access(session, followup_id, current_user)
        return followup_service.update_followup(session, followup_id, payload)
    except (NotFoundError, ForbiddenError, ConflictError) as error:
        _raise_http_error(error)


@router.delete("/{followup_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_followup(
    followup_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    try:
        followup = _ensure_followup_write_access(session, followup_id, current_user)
        followup_service.delete_followup(session, followup)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except (NotFoundError, ForbiddenError) as error:
        _raise_http_error(error)


@router.post(
    "/{followup_id}/attachments",
    response_model=FollowUpAttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_followup_attachment(
    followup_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> FollowUpAttachmentRead:
    try:
        followup = _ensure_followup_write_access(session, followup_id, current_user)
        content = await file.read(followup_service.MAX_ATTACHMENT_BYTES + 1)
        return followup_service.create_attachment(
            session,
            followup,
            file.filename or "attachment",
            file.content_type,
            content,
        )
    except (NotFoundError, ForbiddenError, ConflictError) as error:
        _raise_http_error(error)
    finally:
        await file.close()


@router.get("/{followup_id}/attachments/{attachment_id}")
def download_followup_attachment(
    followup_id: int,
    attachment_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    try:
        followup = followup_service.get_followup(session, followup_id)
        customer = customer_service.get_customer(session, followup.customer_id)
        access_service.ensure_customer_read_access(current_user, customer)
        attachment = followup_service.get_attachment(session, followup_id, attachment_id)
        return FileResponse(
            followup_service.attachment_path(attachment),
            media_type=attachment.content_type or "application/octet-stream",
            filename=attachment.file_name,
        )
    except (NotFoundError, ForbiddenError) as error:
        _raise_http_error(error)


@router.delete("/{followup_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_followup_attachment(
    followup_id: int,
    attachment_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    try:
        _ensure_followup_write_access(session, followup_id, current_user)
        attachment = followup_service.get_attachment(session, followup_id, attachment_id)
        followup_service.delete_attachment(session, attachment)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except (NotFoundError, ForbiddenError) as error:
        _raise_http_error(error)
