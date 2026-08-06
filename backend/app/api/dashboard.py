from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.dashboard import DashboardStats
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> DashboardStats:
    customer_count, followup_count = dashboard_service.get_dashboard_stats(session, current_user)
    return DashboardStats(customer_count=customer_count, followup_count=followup_count)
