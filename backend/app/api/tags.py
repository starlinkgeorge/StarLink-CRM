from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.customer import Tag
from app.models.user import User, UserRole
from app.schemas.customer import TagRead
from app.services import customer_service

router = APIRouter(prefix="/tags", tags=["tags"])


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.get("", response_model=list[TagRead])
def list_tags(session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> list[Tag]:
    return customer_service.list_tags(session)


@router.post("", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> Tag:
    if current_user.role is UserRole.VIEWER:
        raise HTTPException(status_code=403, detail="Viewer accounts have read-only access.")
    return customer_service.create_tag(session, payload.name)
