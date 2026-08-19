from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.inquiry import InquiryStatus
from app.models.user import User
from app.schemas.inquiry import (
    InquiryConversionRead,
    InquiryCreate,
    InquiryPage,
    InquiryRead,
    InquiryUpdate,
)
from app.services import inquiry_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError

router = APIRouter(prefix="/inquiries", tags=["inquiries"])


def _parse_status(value: str | None) -> InquiryStatus | None:
    if value is None or not value.strip():
        return None
    try:
        return InquiryStatus(value.strip())
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid inquiry status filter.") from error


@router.get("", response_model=InquiryPage)
def list_inquiries(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=255),
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    source: str | None = Query(default=None, max_length=80),
    source_platform: str | None = Query(default=None, max_length=80),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> InquiryPage:
    items, total = inquiry_service.list_inquiries(
        session,
        current_user,
        limit,
        offset,
        q,
        _parse_status(status_filter),
        source,
        source_platform,
    )
    return InquiryPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=InquiryRead, status_code=status.HTTP_201_CREATED)
def create_inquiry(
    payload: InquiryCreate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> InquiryRead:
    try:
        return inquiry_service.create_inquiry(session, payload, current_user)
    except ForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@router.get("/{inquiry_id}", response_model=InquiryRead)
def get_inquiry(
    inquiry_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> InquiryRead:
    try:
        return inquiry_service.get_inquiry(session, inquiry_id, current_user)
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@router.put("/{inquiry_id}", response_model=InquiryRead)
def update_inquiry(
    inquiry_id: int,
    payload: InquiryUpdate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> InquiryRead:
    try:
        return inquiry_service.update_inquiry(session, inquiry_id, payload, current_user)
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/{inquiry_id}/convert",
    response_model=InquiryConversionRead,
    status_code=status.HTTP_201_CREATED,
)
def convert_inquiry(
    inquiry_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> InquiryConversionRead:
    try:
        inquiry, customer, contact, opportunity = inquiry_service.convert_inquiry(
            session, inquiry_id, current_user
        )
        return InquiryConversionRead(
            inquiry=inquiry,
            customer=customer,
            contact=contact,
            opportunity=opportunity,
        )
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (ConflictError, ForbiddenError) as error:
        raise HTTPException(
            status_code=409 if isinstance(error, ConflictError) else 403,
            detail=str(error),
        ) from error
