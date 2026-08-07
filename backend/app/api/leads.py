from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.lead import LeadStatus
from app.models.user import User
from app.schemas.lead import LeadConversionRead, LeadCreate, LeadDetail, LeadPage, LeadRead
from app.services import lead_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError

router = APIRouter(prefix="/leads", tags=["leads"])


def _parse_status(value: str | None) -> LeadStatus | None:
    if value is None or not value.strip():
        return None
    try:
        return LeadStatus(value.strip())
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid Lead status filter.") from error


@router.get("", response_model=LeadPage)
def list_leads(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=255),
    status_filter: str | None = Query(default=None, alias="status", max_length=50),
    source: str | None = Query(default=None, max_length=80),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> LeadPage:
    del current_user
    items, total = lead_service.list_leads(
        session=session,
        limit=limit,
        offset=offset,
        query=q,
        status=_parse_status(status_filter),
        source=source,
    )
    return LeadPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> LeadRead:
    try:
        return lead_service.create_lead(session, payload, current_user)
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.get("/{lead_id}", response_model=LeadDetail)
def get_lead(
    lead_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> LeadDetail:
    del current_user
    try:
        lead = lead_service.get_lead(session, lead_id, include_opportunity=True)
        detail = LeadDetail.model_validate(lead)
        if lead.opportunity is not None:
            detail.converted_customer_id = lead.opportunity.customer_id
            detail.converted_opportunity_id = lead.opportunity.id
        return detail
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post(
    "/{lead_id}/convert",
    response_model=LeadConversionRead,
    status_code=status.HTTP_201_CREATED,
)
def convert_lead(
    lead_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> LeadConversionRead:
    try:
        lead, customer, contact, opportunity = lead_service.convert_lead(
            session, lead_id, current_user
        )
        return LeadConversionRead(
            lead=lead,
            customer=customer,
            contact=contact,
            opportunity=opportunity,
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
