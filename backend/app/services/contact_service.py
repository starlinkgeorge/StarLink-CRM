from sqlalchemy.orm import Session

from app.models.customer import Contact, Customer
from app.schemas.contact import ContactCreate, ContactUpdate
from app.services.errors import NotFoundError


def get_contact(session: Session, contact_id: int) -> Contact:
    contact = session.get(Contact, contact_id)
    if contact is None:
        raise NotFoundError("Contact not found.")
    return contact


def create_contact(session: Session, payload: ContactCreate) -> Contact:
    if session.get(Customer, payload.customer_id) is None:
        raise NotFoundError("Customer not found.")
    contact = Contact(**payload.model_dump())
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def update_contact(session: Session, contact_id: int, payload: ContactUpdate) -> Contact:
    contact = get_contact(session, contact_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    session.commit()
    session.refresh(contact)
    return contact
