from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.contact import ContactCreate, ContactRead, ContactUpdate
from app.services import contact_service
from app.services.errors import NotFoundError

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
def create_contact(payload: ContactCreate, session: Session = Depends(get_db_session)) -> ContactRead:
    try:
        return contact_service.create_contact(session, payload)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/{contact_id}", response_model=ContactRead)
def get_contact(contact_id: int, session: Session = Depends(get_db_session)) -> ContactRead:
    try:
        return contact_service.get_contact(session, contact_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.put("/{contact_id}", response_model=ContactRead)
def update_contact(
    contact_id: int, payload: ContactUpdate, session: Session = Depends(get_db_session)
) -> ContactRead:
    try:
        return contact_service.update_contact(session, contact_id, payload)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
