from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.customer import CustomerCreate, CustomerDetail, CustomerPage, CustomerRead, CustomerUpdate
from app.services import customer_service
from app.services.errors import NotFoundError

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerPage)
def list_customers(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, min_length=1, max_length=255),
    session: Session = Depends(get_db_session),
) -> CustomerPage:
    items, total = customer_service.list_customers(session, limit, offset, q)
    return CustomerPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, session: Session = Depends(get_db_session)) -> CustomerRead:
    try:
        return customer_service.create_customer(session, payload)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: int, session: Session = Depends(get_db_session)) -> CustomerDetail:
    try:
        return customer_service.get_customer(session, customer_id, include_relations=True)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.put("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: int, payload: CustomerUpdate, session: Session = Depends(get_db_session)
) -> CustomerRead:
    try:
        return customer_service.update_customer(session, customer_id, payload)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(customer_id: int, session: Session = Depends(get_db_session)) -> Response:
    try:
        customer_service.delete_customer(session, customer_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
