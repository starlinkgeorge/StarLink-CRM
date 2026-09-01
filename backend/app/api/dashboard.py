from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.dashboard import DashboardStats, DashboardTaskCreate, DashboardTaskRead
from app.services import dashboard_service
from app.services.errors import ForbiddenError, NotFoundError
from app.schemas.sales_goal import AnnualSalesTargetRead, AnnualSalesTargetUpdate, OtherSalesAmountInput, OtherSalesAmountRead, SalesTargetProgress
from app.services import sales_target_service

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


@router.get("/sales-target-progress", response_model=SalesTargetProgress)
def sales_target_progress(session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> SalesTargetProgress:
    return sales_target_service.get_progress(session, current_user)


@router.put("/sales-targets/{year}", response_model=AnnualSalesTargetRead)
def update_sales_target(year: int, payload: AnnualSalesTargetUpdate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> AnnualSalesTargetRead:
    if year < 2020 or year > 2100:
        raise HTTPException(status_code=422, detail="year must be between 2020 and 2100")
    try:
        return sales_target_service.update_target(session, current_user, year, payload)
    except ForbiddenError as error:
        _raise_task_error(error)


@router.get("/other-sales", response_model=list[OtherSalesAmountRead])
def list_other_sales(year: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> list[OtherSalesAmountRead]:
    if year < 2020 or year > 2100:
        raise HTTPException(status_code=422, detail="year must be between 2020 and 2100")
    return sales_target_service.list_other_sales(session, current_user, year)


@router.post("/other-sales", response_model=OtherSalesAmountRead, status_code=status.HTTP_201_CREATED)
def create_other_sale(payload: OtherSalesAmountInput, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> OtherSalesAmountRead:
    try:
        return sales_target_service.create_other_sale(session, current_user, payload)
    except ForbiddenError as error:
        _raise_task_error(error)


@router.put("/other-sales/{entry_id}", response_model=OtherSalesAmountRead)
def update_other_sale(entry_id: int, payload: OtherSalesAmountInput, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> OtherSalesAmountRead:
    try:
        return sales_target_service.update_other_sale(session, current_user, entry_id, payload)
    except (ForbiddenError, NotFoundError) as error:
        _raise_task_error(error)


@router.delete("/other-sales/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_other_sale(entry_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> Response:
    try:
        sales_target_service.delete_other_sale(session, current_user, entry_id)
    except (ForbiddenError, NotFoundError) as error:
        _raise_task_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
