from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User, UserRole
from app.schemas.customer import CustomerCategoryCreate, CustomerCategoryRead, CustomerCategoryUpdate
from app.services import customer_service
from app.services.errors import ConflictError, NotFoundError

router = APIRouter(prefix="/customer-categories", tags=["customer-categories"])


@router.get("", response_model=list[CustomerCategoryRead])
def list_customer_categories(
    active_only: bool = Query(default=False),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[CustomerCategoryRead]:
    return customer_service.list_categories(session, active_only=active_only)


@router.post("", response_model=CustomerCategoryRead, status_code=status.HTTP_201_CREATED)
def create_customer_category(
    payload: CustomerCategoryCreate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CustomerCategoryRead:
    if current_user.role is UserRole.VIEWER:
        raise HTTPException(status_code=403, detail="Viewer accounts have read-only access.")
    try:
        return customer_service.create_category(session, payload.model_dump())
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.put("/{category_id}", response_model=CustomerCategoryRead)
def update_customer_category(
    category_id: int,
    payload: CustomerCategoryUpdate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CustomerCategoryRead:
    if current_user.role is UserRole.VIEWER:
        raise HTTPException(status_code=403, detail="Viewer accounts have read-only access.")
    try:
        return customer_service.update_category(
            session, category_id, payload.model_dump(exclude_unset=True)
        )
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
