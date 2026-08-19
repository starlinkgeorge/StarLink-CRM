from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.opportunity import OpportunityDealStage, OpportunitySalesStage, OpportunityStage
from app.models.user import User
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityDetail,
    OpportunityDealPipeline,
    OpportunityListItem,
    OpportunityPage,
    OpportunityPipeline,
    OpportunityUpdate,
)
from app.schemas.product import OpportunityProductReplace
from app.services import opportunity_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _parse_stage(value: str | None) -> OpportunityStage | None:
    if value is None or not value.strip():
        return None
    try:
        return OpportunityStage(value.strip())
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid opportunity stage.") from error


def _parse_sales_stage(value: str | None) -> OpportunitySalesStage | None:
    if value is None or not value.strip():
        return None
    try:
        return OpportunitySalesStage(value.strip())
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid opportunity sales stage.") from error


def _parse_deal_stage(value: str | None) -> OpportunityDealStage | None:
    if value is None or not value.strip():
        return None
    try:
        return OpportunityDealStage(value.strip())
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid opportunity deal stage.") from error


@router.get("", response_model=OpportunityPage)
def list_opportunities(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=255),
    stage_filter: str | None = Query(default=None, alias="stage", max_length=50),
    sales_stage_filter: str | None = Query(
        default=None, alias="sales_stage", max_length=50
    ),
    deal_stage_filter: str | None = Query(default=None, alias="deal_stage", max_length=50),
    customer_id: int | None = Query(default=None, gt=0),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> OpportunityPage:
    items, total = opportunity_service.list_opportunities(
        session=session,
        user=current_user,
        limit=limit,
        offset=offset,
        query=q,
        stage=_parse_stage(stage_filter),
        sales_stage=_parse_sales_stage(sales_stage_filter),
        deal_stage=_parse_deal_stage(deal_stage_filter),
        customer_id=customer_id,
    )
    return OpportunityPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=OpportunityListItem, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    payload: OpportunityCreate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> OpportunityListItem:
    try:
        return opportunity_service.create_opportunity(session, payload, current_user)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("/pipeline", response_model=OpportunityPipeline)
def get_sales_pipeline(
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> OpportunityPipeline:
    """Return the seven V7 sales stages as Kanban columns."""
    return opportunity_service.get_sales_pipeline(session, current_user)


@router.get("/deal-pipeline", response_model=OpportunityDealPipeline)
def get_deal_pipeline(
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> OpportunityDealPipeline:
    """Return V9's six user-facing stages for the sales-process board."""
    return opportunity_service.get_deal_pipeline(session, current_user)


@router.get("/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity(
    opportunity_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> OpportunityDetail:
    try:
        return opportunity_service.get_opportunity_detail(
            session, opportunity_id, current_user
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.delete("/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_opportunity(
    opportunity_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        opportunity_service.delete_opportunity(session, opportunity_id, current_user)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.put("/{opportunity_id}", response_model=OpportunityDetail)
def update_opportunity(
    opportunity_id: int,
    payload: OpportunityUpdate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> OpportunityDetail:
    try:
        return opportunity_service.update_opportunity(
            session, opportunity_id, payload, current_user
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.put("/{opportunity_id}/products", response_model=OpportunityDetail)
def replace_opportunity_products(
    opportunity_id: int,
    payload: OpportunityProductReplace,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> OpportunityDetail:
    try:
        return opportunity_service.replace_opportunity_products(
            session, opportunity_id, payload, current_user
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
