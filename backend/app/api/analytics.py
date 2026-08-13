"""Read-only business analytics endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.analytics import AnalyticsPeriod, BusinessAnalyticsOverview
from app.services import analytics_service


router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=BusinessAnalyticsOverview)
def get_business_analytics(
    period: AnalyticsPeriod = Query(default=AnalyticsPeriod.MONTH),
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> BusinessAnalyticsOverview:
    try:
        return BusinessAnalyticsOverview(
            **analytics_service.get_business_analytics(
                session,
                current_user,
                period=period,
                start_date=start_date,
                end_date=end_date,
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error
