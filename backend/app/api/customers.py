from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.api.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.customer import CustomerLevel, CustomerStatus, Tag
from app.schemas.customer import CustomerCreate, CustomerDetail, CustomerPage, CustomerRead, CustomerUpdate
from app.services import access_service, customer_service
from app.services.errors import ForbiddenError, NotFoundError

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerPage)
def list_customers(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, min_length=1, max_length=255),
    status: CustomerStatus | None = None,
    level: CustomerLevel | None = None,
    country: str | None = Query(default=None, max_length=100),
    source: str | None = Query(default=None, max_length=80),
    tag_id: int | None = Query(default=None, gt=0),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CustomerPage:
    owner_id = current_user.id if current_user.role is UserRole.SALES else None
    items, total = customer_service.list_customers(session, limit, offset, q, owner_id, status, level, country, source, tag_id)
    return CustomerPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> CustomerRead:
    try:
        return customer_service.create_customer(session, payload, current_user)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(
    customer_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> CustomerDetail:
    try:
        customer = customer_service.get_customer(session, customer_id, include_relations=True)
        access_service.ensure_customer_read_access(current_user, customer)
        return customer
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.put("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: int, payload: CustomerUpdate, session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CustomerRead:
    try:
        customer = customer_service.get_customer(session, customer_id)
        access_service.ensure_customer_manage_access(current_user, customer)
        return customer_service.update_customer(session, customer_id, payload, current_user)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> Response:
    try:
        customer = customer_service.get_customer(session, customer_id)
        access_service.ensure_customer_manage_access(current_user, customer)
        customer_service.delete_customer(session, customer_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{customer_id}/tags/{tag_id}", response_model=CustomerDetail)
def assign_tag(customer_id: int, tag_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> CustomerDetail:
    try:
        customer = customer_service.get_customer(session, customer_id, include_relations=True)
        access_service.ensure_customer_manage_access(current_user, customer)
        tag = session.get(Tag, tag_id)
        if tag is None: raise NotFoundError("Tag not found.")
        customer_service.assign_tag(session, customer, tag)
        return customer_service.get_customer(session, customer_id, include_relations=True)
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error


@router.delete("/{customer_id}/tags/{tag_id}", response_model=CustomerDetail)
def remove_tag(customer_id: int, tag_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)) -> CustomerDetail:
    try:
        customer = customer_service.get_customer(session, customer_id, include_relations=True)
        access_service.ensure_customer_manage_access(current_user, customer)
        tag = session.get(Tag, tag_id)
        if tag is None: raise NotFoundError("Tag not found.")
        customer_service.remove_tag(session, customer, tag)
        return customer_service.get_customer(session, customer_id, include_relations=True)
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
