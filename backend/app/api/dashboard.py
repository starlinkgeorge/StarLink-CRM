from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.dashboard import DashboardStats, DashboardTaskCreate, DashboardTaskRead
from app.services import dashboard_service
from app.services.errors import ForbiddenError, NotFoundError

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> DashboardStats:
    return DashboardStats(**dashboard_service.get_dashboard_stats(session, current_user))


def _raise_task_error(error: Exception) -> None:
    if isinstance(error, ForbiddenError):
        raise HTTPException(status_code=403, detail=str(error)) from error
    if isinstance(error, NotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    raise error


@router.get("/tasks/today", response_model=list[DashboardTaskRead])
def get_today_tasks(session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> list[DashboardTaskRead]:
    try:
        return dashboard_service.get_today_tasks(session, current_user)
    except (ForbiddenError, NotFoundError) as error:
        _raise_task_error(error)


@router.post("/tasks", response_model=DashboardTaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: DashboardTaskCreate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> DashboardTaskRead:
    try:
        return dashboard_service.create_dashboard_task(session, payload, current_user)
    except (ForbiddenError, NotFoundError) as error:
        _raise_task_error(error)


@router.post("/tasks/{task_id}/complete", response_model=DashboardTaskRead)
def complete_task(task_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> DashboardTaskRead:
    try:
        return dashboard_service.complete_dashboard_task(session, task_id, current_user)
    except (ForbiddenError, NotFoundError) as error:
        _raise_task_error(error)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> Response:
    try:
        dashboard_service.delete_dashboard_task(session, task_id, current_user)
    except (ForbiddenError, NotFoundError) as error:
        _raise_task_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
