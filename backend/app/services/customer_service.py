from datetime import date, datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.customer import Customer, CustomerLevel, CustomerStatus, Tag
from app.models.customer_classification import CustomerCategory, CustomerScoreHistory
from app.models.customer_activity import CustomerStatusHistory
from app.models.followup import FollowUp
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.models.user import UserRole
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


def _validate_owner(session: Session, owner_id: int | None) -> None:
    if owner_id is not None and session.get(User, owner_id) is None:
        raise NotFoundError("Customer owner not found.")


def list_customers(
    session: Session, limit: int, offset: int, query: str | None, owner_id: int | None = None,
    status: CustomerStatus | None = None, level: CustomerLevel | None = None,
    country: str | None = None, source: str | None = None, tag_id: int | None = None,
    customer_type: str | None = None, interested_product: str | None = None,
    sales_stage: CustomerStatus | None = None, category_id: int | None = None,
    score_min: int | None = None, score_max: int | None = None,
    followup_stage: str | None = None, response_status: str | None = None,
    followup_requirement: str | None = None, customer_level_value: int | None = None,
    customer_name: str | None = None, company_name: str | None = None,
    position: str | None = None, whatsapp: str | None = None, email: str | None = None,
    phone: str | None = None, notes: str | None = None,
    customer_acquired_from: date | None = None, customer_acquired_to: date | None = None,
    customer_size: int | None = None, customer_total_score_min: int | None = None,
    customer_total_score_max: int | None = None, automatic_stage_judgement: str | None = None,
    latest_followup_from: date | None = None, latest_followup_to: date | None = None,
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
                Customer.phone.ilike(term),
                Customer.whatsapp.ilike(term),
                Customer.position.ilike(term),
                Customer.notes.ilike(term),
                Customer.interested_product.ilike(term),
                Customer.followup_stage.ilike(term),
            )
        )
    if status:
        filters.append(Customer.status == status)
    if level:
        filters.append(Customer.level == level)
    if sales_stage:
        filters.append(Customer.sales_stage == sales_stage)
    country_term = country.strip() if country else ""
    if country_term:
        filters.append(Customer.country.ilike(f"%{country_term}%"))
    source_term = source.strip() if source else ""
    if source_term:
        filters.append(Customer.source.ilike(f"%{source_term}%"))
    customer_type_term = customer_type.strip() if customer_type else ""
    if customer_type_term:
        filters.append(Customer.customer_type.ilike(f"%{customer_type_term}%"))
    interested_product_term = interested_product.strip() if interested_product else ""
    if interested_product_term:
        filters.append(Customer.interested_product.ilike(f"%{interested_product_term}%"))
    followup_stage_term = followup_stage.strip() if followup_stage else ""
    if followup_stage_term:
        filters.append(Customer.followup_stage.ilike(f"%{followup_stage_term}%"))
    response_status_term = response_status.strip() if response_status else ""
    if response_status_term:
        filters.append(Customer.response_status.ilike(f"%{response_status_term}%"))
    followup_requirement_term = followup_requirement.strip() if followup_requirement else ""
    if followup_requirement_term:
        filters.append(Customer.followup_requirement.ilike(f"%{followup_requirement_term}%"))
    if customer_level_value is not None:
        filters.append(Customer.customer_level_value == customer_level_value)
    if customer_size is not None:
        filters.append(Customer.customer_size == customer_size)
    if customer_total_score_min is not None:
        filters.append(Customer.customer_total_score >= customer_total_score_min)
    if customer_total_score_max is not None:
        filters.append(Customer.customer_total_score <= customer_total_score_max)
    if customer_acquired_from is not None:
        filters.append(Customer.customer_acquired_at >= customer_acquired_from)
    if customer_acquired_to is not None:
        filters.append(Customer.customer_acquired_at <= customer_acquired_to)
    if latest_followup_from is not None:
        filters.append(Customer.latest_followup_date >= latest_followup_from)
    if latest_followup_to is not None:
        filters.append(Customer.latest_followup_date <= latest_followup_to)

    for column, value in (
        (Customer.contact_name, customer_name),
        (Customer.company_name, company_name),
        (Customer.position, position),
        (Customer.whatsapp, whatsapp),
        (Customer.email, email),
        (Customer.phone, phone),
        (Customer.notes, notes),
        (Customer.automatic_stage_judgement, automatic_stage_judgement),
    ):
        term_value = value.strip() if value else ""
        if term_value:
            filters.append(column.ilike(f"%{term_value}%"))
    if tag_id:
        filters.append(Customer.tags.any(Tag.id == tag_id))
    if category_id:
        filters.append(Customer.category_id == category_id)
    if score_min is not None:
        filters.append(Customer.customer_score >= score_min)
    if score_max is not None:
        filters.append(Customer.customer_score <= score_max)
    statement = (
        select(Customer)
        .options(selectinload(Customer.category))
        .where(*filters)
        .order_by(Customer.updated_at.desc(), Customer.id.desc())
    )
    total = session.scalar(select(func.count()).select_from(Customer).where(*filters)) or 0
    customers = list(session.scalars(statement.limit(limit).offset(offset)))
    return customers, total


def list_customers_for_export(session: Session, owner_id: int | None = None) -> list[Customer]:
    statement = select(Customer).options(selectinload(Customer.owner))
    if owner_id is not None:
        statement = statement.where(Customer.owner_id == owner_id)
    statement = statement.order_by(Customer.customer_acquired_at.desc(), Customer.id.desc())
    return list(session.scalars(statement))


def get_customer(session: Session, customer_id: int, include_relations: bool = False) -> Customer:
    statement = select(Customer).where(Customer.id == customer_id)
    if include_relations:
        statement = statement.options(
            selectinload(Customer.contacts),
            selectinload(Customer.tags),
            selectinload(Customer.followups).selectinload(FollowUp.attachments),
            selectinload(Customer.category),
            selectinload(Customer.score_history),
        )
    customer = session.scalar(statement)
    if customer is None:
        raise NotFoundError("Customer not found.")
    return customer


def create_customer(session: Session, payload: CustomerCreate, creator: User) -> Customer:
    if creator.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")
    data = payload.model_dump(exclude_none=True)
    if "sales_stage" in payload.model_fields_set:
        data["status"] = data["sales_stage"]
    else:
        data["sales_stage"] = data["status"]
    if creator.role is UserRole.SALES:
        if data.get("owner_id") not in (None, creator.id):
            raise ForbiddenError("Sales users may only create customers for themselves.")
        data["owner_id"] = creator.id
    _validate_owner(session, data.get("owner_id"))
    category_id = data.get("category_id")
    if category_id is not None and session.get(CustomerCategory, category_id) is None:
        raise NotFoundError("Customer category not found.")
    if "customer_score" in data:
        data["level"] = level_for_score(data["customer_score"])
        data["score_updated_at"] = datetime.now(timezone.utc)
    customer = Customer(**data)
    session.add(customer)
    session.commit()
    session.refresh(customer)
    if "customer_score" in data:
        session.add(
            CustomerScoreHistory(
                customer_id=customer.id,
                old_score=None,
                new_score=data["customer_score"],
                reason="Initial customer score",
                changed_by_id=creator.id,
            )
        )
        session.commit()
    return customer


def update_customer(session: Session, customer_id: int, payload: CustomerUpdate, editor: User) -> Customer:
    customer = get_customer(session, customer_id)
    previous_stage = customer.sales_stage
    changes = payload.model_dump(exclude_unset=True)
    if "sales_stage" in changes:
        changes["status"] = changes["sales_stage"]
    elif "status" in changes:
        changes["sales_stage"] = changes["status"]
    if editor.role is UserRole.SALES and "owner_id" in changes and changes["owner_id"] != editor.id:
        raise ForbiddenError("Sales users may not reassign customers.")
    if "owner_id" in changes:
        _validate_owner(session, changes["owner_id"])
    if "category_id" in changes and changes["category_id"] is not None:
        if session.get(CustomerCategory, changes["category_id"]) is None:
            raise NotFoundError("Customer category not found.")
    if changes.get("customer_score") is None:
        changes.pop("customer_score", None)
    score_changed = "customer_score" in changes and changes["customer_score"] is not None
    old_score = customer.customer_score
    if score_changed:
        changes["level"] = level_for_score(changes["customer_score"])
        changes["score_updated_at"] = datetime.now(timezone.utc)
    next_stage = changes.get("sales_stage", previous_stage)
    if next_stage != previous_stage:
        session.add(
            CustomerStatusHistory(
                customer_id=customer.id,
                old_status=previous_stage,
                new_status=next_stage,
                changed_by_id=editor.id,
            )
        )
    for field, value in changes.items():
        setattr(customer, field, value)
    session.commit()
    session.refresh(customer)
    if score_changed and changes["customer_score"] != old_score:
        session.add(
            CustomerScoreHistory(
                customer_id=customer.id,
                old_score=old_score,
                new_score=changes["customer_score"],
                reason="Customer profile score update",
                changed_by_id=editor.id,
            )
        )
        session.commit()
    return customer


def delete_customer(session: Session, customer_id: int) -> None:
    customer = get_customer(session, customer_id)
    session.delete(customer)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError(
            "Customers with commercial records such as quotations cannot be deleted."
        ) from error


def level_for_score(score: int) -> CustomerLevel:
    if score >= 80:
        return CustomerLevel.A
    if score >= 50:
        return CustomerLevel.B
    return CustomerLevel.C


def list_tags(session: Session, active_only: bool = False) -> list[Tag]:
    statement = select(Tag)
    if active_only:
        statement = statement.where(Tag.is_active.is_(True))
    return list(session.scalars(statement.order_by(Tag.name.asc())))


def create_tag(
    session: Session,
    name: str,
    description: str | None = None,
    color: str = "#2563eb",
    is_active: bool = True,
) -> Tag:
    existing = session.scalar(select(Tag).where(func.lower(Tag.name) == name.strip().lower()))
    if existing:
        return existing
    tag = Tag(name=name.strip(), description=description, color=color, is_active=is_active)
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


def update_tag(session: Session, tag_id: int, changes: dict) -> Tag:
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise NotFoundError("Tag not found.")
    if "name" in changes and changes["name"] is not None:
        duplicate = session.scalar(
            select(Tag).where(func.lower(Tag.name) == changes["name"].strip().lower(), Tag.id != tag_id)
        )
        if duplicate:
            raise ConflictError("A tag with this name already exists.")
        changes["name"] = changes["name"].strip()
    for field, value in changes.items():
        setattr(tag, field, value)
    session.commit()
    session.refresh(tag)
    return tag


def deactivate_tag(session: Session, tag_id: int) -> None:
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise NotFoundError("Tag not found.")
    tag.is_active = False
    session.commit()


def list_categories(session: Session, active_only: bool = False) -> list[CustomerCategory]:
    statement = select(CustomerCategory)
    if active_only:
        statement = statement.where(CustomerCategory.is_active.is_(True))
    return list(
        session.scalars(
            statement.order_by(CustomerCategory.sort_order.asc(), CustomerCategory.name.asc())
        )
    )


def create_category(session: Session, data: dict) -> CustomerCategory:
    existing = session.scalar(
        select(CustomerCategory).where(func.lower(CustomerCategory.name) == data["name"].strip().lower())
    )
    if existing:
        raise ConflictError("A customer category with this name already exists.")
    category = CustomerCategory(**{**data, "name": data["name"].strip()})
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def update_category(session: Session, category_id: int, changes: dict) -> CustomerCategory:
    category = session.get(CustomerCategory, category_id)
    if category is None:
        raise NotFoundError("Customer category not found.")
    if "name" in changes and changes["name"] is not None:
        duplicate = session.scalar(
            select(CustomerCategory).where(
                func.lower(CustomerCategory.name) == changes["name"].strip().lower(),
                CustomerCategory.id != category_id,
            )
        )
        if duplicate:
            raise ConflictError("A customer category with this name already exists.")
        changes["name"] = changes["name"].strip()
    for field, value in changes.items():
        setattr(category, field, value)
    session.commit()
    session.refresh(category)
    return category


def list_score_history(session: Session, customer_id: int) -> list[CustomerScoreHistory]:
    return list(
        session.scalars(
            select(CustomerScoreHistory)
            .where(CustomerScoreHistory.customer_id == customer_id)
            .order_by(CustomerScoreHistory.created_at.desc(), CustomerScoreHistory.id.desc())
        )
    )


def update_customer_score(
    session: Session, customer_id: int, score: int, reason: str | None, editor: User
) -> Customer:
    customer = get_customer(session, customer_id)
    old_score = customer.customer_score
    customer.customer_score = score
    customer.level = level_for_score(score)
    customer.score_updated_at = datetime.now(timezone.utc)
    session.add(
        CustomerScoreHistory(
            customer_id=customer.id,
            old_score=old_score,
            new_score=score,
            reason=reason,
            changed_by_id=editor.id,
        )
    )
    session.commit()
    session.refresh(customer)
    return customer


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
