from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer import Contact, Customer, CustomerStatus
from app.models.user import User, UserRole
from app.schemas.alibaba import AlibabaInquiryCreate
from app.services.errors import ForbiddenError


def _find_existing_customer(session: Session, payload: AlibabaInquiryCreate) -> Customer | None:
    if payload.email:
        email = payload.email.casefold()
        existing = session.scalar(
            select(Customer)
            .where(func.lower(func.trim(Customer.email)) == email)
            .order_by(Customer.id.asc())
        )
        if existing is not None:
            return existing

    return session.scalar(
        select(Customer)
        .where(
            func.lower(func.trim(Customer.company_name)) == payload.company_name.casefold(),
            func.lower(func.trim(Customer.contact_name)) == payload.contact_name.casefold(),
        )
        .order_by(Customer.id.asc())
    )


def receive_inquiry(
    session: Session, payload: AlibabaInquiryCreate, receiver: User
) -> tuple[Customer, bool]:
    if receiver.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")

    existing = _find_existing_customer(session, payload)
    if existing is not None:
        return existing, False

    data = payload.model_dump(exclude={"source", "inquiry_content"})
    customer = Customer(
        **data,
        source="Alibaba",
        source_platform="Alibaba",
        original_inquiry=payload.inquiry_content,
        status=CustomerStatus.LEAD,
        sales_stage=CustomerStatus.LEAD,
        owner_id=receiver.id,
    )
    session.add(customer)
    session.flush()
    session.add(
        Contact(
            customer_id=customer.id,
            name=payload.contact_name,
            email=payload.email,
            phone=payload.phone,
            whatsapp=payload.whatsapp,
        )
    )
    session.commit()
    session.refresh(customer)
    return customer, True
