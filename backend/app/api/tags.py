from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.customer import Tag
from app.models.user import User, UserRole
from app.schemas.customer import TagRead
from app.services import customer_service
from app.services.errors import ConflictError, NotFoundError

router = APIRouter(prefix="/tags", tags=["tags"])


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=255)
    color: str = Field(default="#2563eb", min_length=4, max_length=20)
    is_active: bool = True


class TagUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=255)
    color: Optional[str] = Field(default=None, min_length=4, max_length=20)
    is_active: Optional[bool] = None


@router.get("", response_model=list[TagRead])
def list_tags(session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> list[Tag]:
    return customer_service.list_tags(session)


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> Tag:
    if current_user.role is UserRole.VIEWER:
        raise HTTPException(status_code=403, detail="Viewer accounts have read-only access.")
    return customer_service.create_tag(session, **payload.model_dump())


@router.put("/{tag_id}", response_model=TagRead)
def update_tag(
    tag_id: int,
    payload: TagUpdate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Tag:
    if current_user.role is UserRole.VIEWER:
        raise HTTPException(status_code=403, detail="Viewer accounts have read-only access.")
    try:
        return customer_service.update_tag(
            session, tag_id, payload.model_dump(exclude_unset=True)
        )
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_tag(
    tag_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    if current_user.role is UserRole.VIEWER:
        raise HTTPException(status_code=403, detail="Viewer accounts have read-only access.")
    try:
        customer_service.deactivate_tag(session, tag_id)
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
