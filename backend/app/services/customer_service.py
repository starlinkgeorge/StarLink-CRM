from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.customer import Customer
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.services.errors import NotFoundError


def _validate_owner(session: Session, owner_id: int | None) -> None:
    if owner_id is not None and session.get(User, owner_id) is None:
        raise NotFoundError("Customer owner not found.")


def list_customers(session: Session, limit: int, offset: int, query: str | None) -> tuple[list[Customer], int]:
    filters = []
    if query:
        term = f"%{query.strip()}%"
        filters.append(
            or_(
                Customer.company_name.ilike(term),
                Customer.contact_name.ilike(term),
                Customer.country.ilike(term),
                Customer.email.ilike(term),
            )
        )
    statement = select(Customer).where(*filters).order_by(Customer.updated_at.desc(), Customer.id.desc())
    total = session.scalar(select(func.count()).select_from(Customer).where(*filters)) or 0
    customers = list(session.scalars(statement.limit(limit).offset(offset)))
    return customers, total


def get_customer(session: Session, customer_id: int, include_relations: bool = False) -> Customer:
    statement = select(Customer).where(Customer.id == customer_id)
    if include_relations:
        statement = statement.options(
            selectinload(Customer.contacts),
            selectinload(Customer.tags),
            selectinload(Customer.followups),
        )
    customer = session.scalar(statement)
    if customer is None:
        raise NotFoundError("Customer not found.")
    return customer


def create_customer(session: Session, payload: CustomerCreate) -> Customer:
    data = payload.model_dump()
    _validate_owner(session, data["owner_id"])
    customer = Customer(**data)
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


def update_customer(session: Session, customer_id: int, payload: CustomerUpdate) -> Customer:
    customer = get_customer(session, customer_id)
    changes = payload.model_dump(exclude_unset=True)
    if "owner_id" in changes:
        _validate_owner(session, changes["owner_id"])
    for field, value in changes.items():
        setattr(customer, field, value)
    session.commit()
    session.refresh(customer)
    return customer


def delete_customer(session: Session, customer_id: int) -> None:
    customer = get_customer(session, customer_id)
    session.delete(customer)
    session.commit()
