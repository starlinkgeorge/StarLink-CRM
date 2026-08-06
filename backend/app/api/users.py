from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserRead
from app.services import user_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(
    session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> list[UserRead]:
    try:
        user_service.ensure_user_management_access(current_user)
        return user_service.list_users(session)
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> UserRead:
    try:
        user_service.ensure_user_management_access(current_user)
        return user_service.create_user(session, payload)
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> UserRead:
    try:
        user_service.ensure_user_management_access(current_user)
        return user_service.get_user(session, user_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
