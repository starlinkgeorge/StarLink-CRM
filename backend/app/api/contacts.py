from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.contact import ContactCreate, ContactRead, ContactUpdate
from app.services import access_service, contact_service, customer_service
from app.services.errors import ForbiddenError, NotFoundError

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> ContactRead:
    try:
        customer = customer_service.get_customer(session, payload.customer_id)
        access_service.ensure_customer_manage_access(current_user, customer)
        return contact_service.create_contact(session, payload)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.get("/{contact_id}", response_model=ContactRead)
def get_contact(
    contact_id: int, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> ContactRead:
    try:
        contact = contact_service.get_contact(session, contact_id)
        access_service.ensure_customer_read_access(current_user, customer_service.get_customer(session, contact.customer_id))
        return contact
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.put("/{contact_id}", response_model=ContactRead)
def update_contact(
    contact_id: int, payload: ContactUpdate, session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> ContactRead:
    try:
        contact = contact_service.get_contact(session, contact_id)
        access_service.ensure_customer_manage_access(current_user, customer_service.get_customer(session, contact.customer_id))
        return contact_service.update_contact(session, contact_id, payload)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
