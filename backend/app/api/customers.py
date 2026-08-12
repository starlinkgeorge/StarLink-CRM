from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import Response as FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.api.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.customer import CustomerLevel, CustomerStatus, Tag
from app.schemas.customer import (
    CustomerCreate,
    CustomerDetail,
    CustomerPage,
    CustomerRead,
    CustomerScoreHistoryRead,
    CustomerScoreUpdate,
    CustomerUpdate,
)
from app.schemas.customer_activity import CustomerActivityRead
from app.schemas.customer_center import CustomerCenter
from app.services import (
    access_service,
    customer_activity_service,
    customer_center_service,
    customer_service,
)
from app.services.errors import ConflictError, ForbiddenError, NotFoundError

router = APIRouter(prefix="/customers", tags=["customers"])


def _parse_status_filter(value: str | None) -> CustomerStatus | None:
    if value is None or not value.strip():
        return None
    try:
        return CustomerStatus(value.strip())
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid customer status filter.") from error


def _parse_level_filter(value: str | None) -> CustomerLevel | None:
    if value is None or not value.strip():
        return None
    try:
        return CustomerLevel(value.strip())
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid customer level filter.") from error


def _parse_sales_stage_filter(value: str | None) -> CustomerStatus | None:
    if value is None or not value.strip():
        return None
    try:
        return CustomerStatus(value.strip())
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid sales stage filter.") from error


@router.get("", response_model=CustomerPage)
def list_customers(
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=255),
    status_filter: str | None = Query(default=None, alias="status", max_length=50),
    level_filter: str | None = Query(default=None, alias="level", max_length=10),
    country: str | None = Query(default=None, max_length=100),
    customer_type: str | None = Query(default=None, max_length=80),
    source: str | None = Query(default=None, max_length=80),
    interested_product: str | None = Query(default=None, max_length=500),
    sales_stage_filter: str | None = Query(default=None, alias="sales_stage", max_length=50),
    tag_id: int | None = Query(default=None, gt=0),
    category_id: int | None = Query(default=None, gt=0),
    score_min: int | None = Query(default=None, ge=0, le=100),
    score_max: int | None = Query(default=None, ge=0, le=100),
    followup_stage: str | None = Query(default=None, max_length=120),
    response_status: str | None = Query(default=None, max_length=80),
    followup_requirement: str | None = Query(default=None, max_length=80),
    customer_level_value: int | None = Query(default=None, ge=0, le=9999),
    customer_name: str | None = Query(default=None, max_length=120),
    company_name: str | None = Query(default=None, max_length=255),
    position: str | None = Query(default=None, max_length=120),
    whatsapp: str | None = Query(default=None, max_length=50),
    email: str | None = Query(default=None, max_length=320),
    phone: str | None = Query(default=None, max_length=50),
    notes: str | None = Query(default=None, max_length=10000),
    customer_acquired_from: date | None = None,
    customer_acquired_to: date | None = None,
    customer_size: int | None = Query(default=None, ge=0, le=9999),
    customer_total_score_min: int | None = Query(default=None, ge=0, le=9999),
    customer_total_score_max: int | None = Query(default=None, ge=0, le=9999),
    automatic_stage_judgement: str | None = Query(default=None, max_length=120),
    latest_followup_from: date | None = None,
    latest_followup_to: date | None = None,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CustomerPage:
    owner_id = current_user.id if current_user.role is UserRole.SALES else None
    items, total = customer_service.list_customers(
        session=session,
        limit=limit,
        offset=offset,
        query=q,
        owner_id=owner_id,
        status=_parse_status_filter(status_filter),
        level=_parse_level_filter(level_filter),
        country=country,
        source=source,
        tag_id=tag_id,
        customer_type=customer_type,
        interested_product=interested_product,
        sales_stage=_parse_sales_stage_filter(sales_stage_filter),
        category_id=category_id,
        score_min=score_min,
        score_max=score_max,
        followup_stage=followup_stage,
        response_status=response_status,
        followup_requirement=followup_requirement,
        customer_level_value=customer_level_value,
        customer_name=customer_name,
        company_name=company_name,
        position=position,
        whatsapp=whatsapp,
        email=email,
        phone=phone,
        notes=notes,
        customer_acquired_from=customer_acquired_from,
        customer_acquired_to=customer_acquired_to,
        customer_size=customer_size,
        customer_total_score_min=customer_total_score_min,
        customer_total_score_max=customer_total_score_max,
        automatic_stage_judgement=automatic_stage_judgement,
        latest_followup_from=latest_followup_from,
        latest_followup_to=latest_followup_to,
    )
    return CustomerPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/export")
def export_customer_archive(
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Download every customer accessible to the current user as a real .xlsx archive."""
    from app.services.customer_export_service import build_customer_archive_export

    owner_id = current_user.id if current_user.role is UserRole.SALES else None
    content = build_customer_archive_export(customer_service.list_customers_for_export(session, owner_id))
    filename = "StarLink-CRM-客户档案表.xlsx"
    return FileResponse(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=StarLink-CRM-customers.xlsx; filename*=UTF-8''{quote(filename)}",
        },
    )


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> CustomerRead:
    try:
        return customer_service.create_customer(session, payload, current_user)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.get("/{customer_id}/center", response_model=CustomerCenter)
def get_customer_center(
    customer_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CustomerCenter:
    try:
        return customer_center_service.get_customer_center(session, customer_id, current_user)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(
    customer_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> CustomerDetail:
    try:
        customer = customer_service.get_customer(session, customer_id, include_relations=True)
        access_service.ensure_customer_read_access(current_user, customer)
        return customer
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.get("/{customer_id}/timeline", response_model=list[CustomerActivityRead])
def get_customer_timeline(
    customer_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[CustomerActivityRead]:
    try:
        customer = customer_service.get_customer(session, customer_id)
        access_service.ensure_customer_read_access(current_user, customer)
        return customer_activity_service.list_customer_timeline(session, customer)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.put("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: int, payload: CustomerUpdate, session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CustomerRead:
    try:
        customer = customer_service.get_customer(session, customer_id)
        access_service.ensure_customer_manage_access(current_user, customer)
        return customer_service.update_customer(session, customer_id, payload, current_user)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> Response:
    try:
        customer = customer_service.get_customer(session, customer_id)
        access_service.ensure_customer_manage_access(current_user, customer)
        customer_service.delete_customer(session, customer_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{customer_id}/tags/{tag_id}", response_model=CustomerDetail)
def assign_tag(customer_id: int, tag_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> CustomerDetail:
    try:
        customer = customer_service.get_customer(session, customer_id, include_relations=True)
        access_service.ensure_customer_manage_access(current_user, customer)
        tag = session.get(Tag, tag_id)
        if tag is None: raise NotFoundError("Tag not found.")
        customer_service.assign_tag(session, customer, tag)
        return customer_service.get_customer(session, customer_id, include_relations=True)
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@router.delete("/{customer_id}/tags/{tag_id}", response_model=CustomerDetail)
def remove_tag(customer_id: int, tag_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> CustomerDetail:
    try:
        customer = customer_service.get_customer(session, customer_id, include_relations=True)
        access_service.ensure_customer_manage_access(current_user, customer)
        tag = session.get(Tag, tag_id)
        if tag is None: raise NotFoundError("Tag not found.")
        customer_service.remove_tag(session, customer, tag)
        return customer_service.get_customer(session, customer_id, include_relations=True)
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@router.put("/{customer_id}/score", response_model=CustomerRead)
def update_customer_score(
    customer_id: int,
    payload: CustomerScoreUpdate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CustomerRead:
    try:
        customer = customer_service.get_customer(session, customer_id)
        access_service.ensure_customer_manage_access(current_user, customer)
        return customer_service.update_customer_score(
            session, customer_id, payload.score, payload.reason, current_user
        )
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@router.get("/{customer_id}/score-history", response_model=list[CustomerScoreHistoryRead])
def get_customer_score_history(
    customer_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[CustomerScoreHistoryRead]:
    try:
        customer = customer_service.get_customer(session, customer_id)
        access_service.ensure_customer_read_access(current_user, customer)
        return customer_service.list_score_history(session, customer_id)
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
