from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.product import (
    ProductCategoryCreate,
    ProductCategoryRead,
    ProductCategoryUpdate,
    ProductCreate,
    ProductPage,
    ProductRead,
    ProductUpdate,
)
from app.services import product_service
from app.services.errors import ConflictError, ForbiddenError, NotFoundError

router = APIRouter(prefix="/products", tags=["products"])
category_router = APIRouter(prefix="/product-categories", tags=["product-categories"])


def _raise_service_error(error: Exception) -> None:
    if isinstance(error, NotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, ConflictError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    if isinstance(error, ForbiddenError):
        raise HTTPException(status_code=403, detail=str(error)) from error
    raise error


@category_router.get("", response_model=list[ProductCategoryRead])
def list_categories(
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[ProductCategoryRead]:
    return product_service.list_categories(session)


@category_router.post("", response_model=ProductCategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(
    payload: ProductCategoryCreate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ProductCategoryRead:
    try:
        return product_service.create_category(session, payload, current_user)
    except (NotFoundError, ForbiddenError) as error:
        _raise_service_error(error)


@category_router.put("/{category_id}", response_model=ProductCategoryRead)
def update_category(
    category_id: int,
    payload: ProductCategoryUpdate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ProductCategoryRead:
    try:
        return product_service.update_category(session, category_id, payload, current_user)
    except (NotFoundError, ConflictError, ForbiddenError) as error:
        _raise_service_error(error)


@router.get("", response_model=ProductPage)
def list_products(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=255),
    category_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = Query(default=None),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ProductPage:
    items, total = product_service.list_products(
        session, limit, offset, q, category_id, is_active
    )
    return ProductPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ProductRead:
    try:
        return product_service.create_product(session, payload, current_user)
    except (NotFoundError, ConflictError, ForbiddenError) as error:
        _raise_service_error(error)


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ProductRead:
    try:
        return product_service.get_product_read(session, product_id)
    except NotFoundError as error:
        _raise_service_error(error)


@router.put("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ProductRead:
    try:
        return product_service.update_product(session, product_id, payload, current_user)
    except (NotFoundError, ConflictError, ForbiddenError) as error:
        _raise_service_error(error)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        product_service.delete_product(session, product_id, current_user)
    except (NotFoundError, ConflictError, ForbiddenError) as error:
        _raise_service_error(error)
