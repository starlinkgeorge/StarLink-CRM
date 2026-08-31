from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.workbench import DailyWorkNoteRead, DailyWorkNoteUpdate, TaskCreate, TaskRead, WorkbenchToday
from app.services import workbench_service
from app.services.errors import ForbiddenError, NotFoundError

router = APIRouter(prefix="/workbench", tags=["workbench"])


def _raise(error: Exception) -> None:
    if isinstance(error, ForbiddenError): raise HTTPException(status_code=403, detail=str(error)) from error
    if isinstance(error, NotFoundError): raise HTTPException(status_code=404, detail=str(error)) from error
    raise error


@router.get("/today", response_model=WorkbenchToday)
def get_today(session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> WorkbenchToday:
    try: return workbench_service.get_today(session, current_user)
    except (ForbiddenError, NotFoundError) as error: _raise(error)


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> TaskRead:
    try: return workbench_service.create_task(session, payload, current_user)
    except (ForbiddenError, NotFoundError) as error: _raise(error)


@router.post("/tasks/{task_id}/complete", response_model=TaskRead)
def complete_task(task_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> TaskRead:
    try: return workbench_service.complete_task(session, task_id, current_user)
    except (ForbiddenError, NotFoundError) as error: _raise(error)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> Response:
    try: workbench_service.delete_task(session, task_id, current_user)
    except (ForbiddenError, NotFoundError) as error: _raise(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/daily-note", response_model=DailyWorkNoteRead)
def save_daily_note(payload: DailyWorkNoteUpdate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> DailyWorkNoteRead:
    try: return workbench_service.save_daily_note(session, payload, current_user)
    except (ForbiddenError, NotFoundError) as error: _raise(error)
