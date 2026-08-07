from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.quotation import QuotationStatus
from app.models.user import User
from app.schemas.quotation import (
    QuotationCreate,
    QuotationDetail,
    QuotationPage,
    QuotationUpdate,
)
from app.services import quotation_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError

router = APIRouter(prefix="/quotations", tags=["quotations"])


def _parse_status(value: str | None) -> QuotationStatus | None:
    if value is None or not value.strip():
        return None
    try:
        return QuotationStatus(value.strip())
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid quotation status.") from error


def _raise_service_error(error: Exception) -> None:
    if isinstance(error, NotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, ConflictError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    if isinstance(error, ForbiddenError):
        raise HTTPException(status_code=403, detail=str(error)) from error
    raise error


@router.get("", response_model=QuotationPage)
def list_quotations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=255),
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> QuotationPage:
    items, total = quotation_service.list_quotations(
        session, current_user, limit, offset, q, _parse_status(status_filter)
    )
    return QuotationPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=QuotationDetail, status_code=status.HTTP_201_CREATED)
def create_quotation(
    payload: QuotationCreate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> QuotationDetail:
    try:
        return quotation_service.create_quotation(session, payload, current_user)
    except (NotFoundError, ConflictError, ForbiddenError) as error:
        _raise_service_error(error)


@router.get("/{quotation_id}/pdf")
def download_quotation_pdf(
    quotation_id: int,
    version_no: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    try:
        path, download_name = quotation_service.get_pdf_path(
            session, quotation_id, current_user, version_no
        )
        return FileResponse(path, media_type="application/pdf", filename=download_name)
    except (NotFoundError, ForbiddenError) as error:
        _raise_service_error(error)


@router.get("/{quotation_id}", response_model=QuotationDetail)
def get_quotation(
    quotation_id: int,
    version_no: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> QuotationDetail:
    try:
        return quotation_service.get_quotation_detail(
            session, quotation_id, current_user, version_no
        )
    except (NotFoundError, ForbiddenError) as error:
        _raise_service_error(error)


@router.put("/{quotation_id}", response_model=QuotationDetail)
def update_quotation(
    quotation_id: int,
    payload: QuotationUpdate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> QuotationDetail:
    try:
        return quotation_service.update_quotation(
            session, quotation_id, payload, current_user
        )
    except (NotFoundError, ConflictError, ForbiddenError) as error:
        _raise_service_error(error)


@router.post("/{quotation_id}/versions", response_model=QuotationDetail)
def create_version(
    quotation_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> QuotationDetail:
    try:
        return quotation_service.create_version(session, quotation_id, current_user)
    except (NotFoundError, ConflictError, ForbiddenError) as error:
        _raise_service_error(error)


@router.post("/{quotation_id}/pdf", response_model=QuotationDetail)
def generate_pdf(
    quotation_id: int,
    version_no: int | None = Query(default=None, ge=1),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> QuotationDetail:
    try:
        return quotation_service.generate_pdf(
            session, quotation_id, current_user, version_no
        )
    except (NotFoundError, ForbiddenError) as error:
        _raise_service_error(error)


@router.post("/{quotation_id}/send", response_model=QuotationDetail)
def mark_sent(
    quotation_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> QuotationDetail:
    try:
        return quotation_service.mark_sent(session, quotation_id, current_user)
    except (NotFoundError, ConflictError, ForbiddenError) as error:
        _raise_service_error(error)
