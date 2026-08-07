from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.customer import Customer, CustomerLevel, CustomerStatus, Tag
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.models.user import UserRole
from app.services.errors import ForbiddenError, NotFoundError


def _validate_owner(session: Session, owner_id: int | None) -> None:
    if owner_id is not None and session.get(User, owner_id) is None:
        raise NotFoundError("Customer owner not found.")


def list_customers(
    session: Session, limit: int, offset: int, query: str | None, owner_id: int | None = None,
    status: CustomerStatus | None = None, level: CustomerLevel | None = None,
    country: str | None = None, source: str | None = None, tag_id: int | None = None,
) -> tuple[list[Customer], int]:
    filters = []
    if owner_id is not None:
        filters.append(Customer.owner_id == owner_id)
    search_term = query.strip() if query else ""
    if search_term:
        term = f"%{search_term}%"
        filters.append(
            or_(
                Customer.company_name.ilike(term),
                Customer.contact_name.ilike(term),
                Customer.country.ilike(term),
                Customer.email.ilike(term),
            )
        )
    if status:
        filters.append(Customer.status == status)
    if level:
        filters.append(Customer.level == level)
    country_term = country.strip() if country else ""
    if country_term:
        filters.append(Customer.country.ilike(f"%{country_term}%"))
    source_term = source.strip() if source else ""
    if source_term:
        filters.append(Customer.source.ilike(f"%{source_term}%"))
    if tag_id:
        filters.append(Customer.tags.any(Tag.id == tag_id))
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


def create_customer(session: Session, payload: CustomerCreate, creator: User) -> Customer:
    if creator.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")
    data = payload.model_dump()
    if "sales_stage" in payload.model_fields_set:
        data["status"] = data["sales_stage"]
    else:
        data["sales_stage"] = data["status"]
    if creator.role is UserRole.SALES:
        if data["owner_id"] not in (None, creator.id):
            raise ForbiddenError("Sales users may only create customers for themselves.")
        data["owner_id"] = creator.id
    _validate_owner(session, data["owner_id"])
    customer = Customer(**data)
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


def update_customer(session: Session, customer_id: int, payload: CustomerUpdate, editor: User) -> Customer:
    customer = get_customer(session, customer_id)
    changes = payload.model_dump(exclude_unset=True)
    if "sales_stage" in changes:
        changes["status"] = changes["sales_stage"]
    elif "status" in changes:
        changes["sales_stage"] = changes["status"]
    if editor.role is UserRole.SALES and "owner_id" in changes and changes["owner_id"] != editor.id:
        raise ForbiddenError("Sales users may not reassign customers.")
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


def list_tags(session: Session) -> list[Tag]:
    return list(session.scalars(select(Tag).order_by(Tag.name.asc())))


def create_tag(session: Session, name: str) -> Tag:
    existing = session.scalar(select(Tag).where(func.lower(Tag.name) == name.strip().lower()))
    if existing:
        return existing
    tag = Tag(name=name.strip())
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def assign_tag(session: Session, customer: Customer, tag: Tag) -> Customer:
    if tag not in customer.tags:
        customer.tags.append(tag)
        session.commit()
    return customer


def remove_tag(session: Session, customer: Customer, tag: Tag) -> Customer:
    if tag in customer.tags:
        customer.tags.remove(tag)
        session.commit()
    return customer
