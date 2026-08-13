from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.customer import Contact, Customer, CustomerStatus
from app.models.inquiry import Inquiry, InquiryStatus
from app.models.opportunity import (
    Opportunity,
    OpportunityDealStage,
    OpportunityDealStageHistory,
    OpportunitySalesStage,
    OpportunitySalesStageHistory,
    OpportunityStage,
    OpportunityStageHistory,
)
from app.models.user import User, UserRole
from app.schemas.inquiry import InquiryCreate, InquiryUpdate
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


def _as_status(value: InquiryStatus | str) -> InquiryStatus:
    return value if isinstance(value, InquiryStatus) else InquiryStatus(value)


def list_inquiries(
    session: Session,
    limit: int,
    offset: int,
    query: str | None = None,
    status: InquiryStatus | None = None,
    source: str | None = None,
    source_platform: str | None = None,
) -> tuple[list[Inquiry], int]:
    filters = []
    if status is not None:
        filters.append(Inquiry.status == status.value)
    source_term = source.strip() if source else ""
    if source_term:
        filters.append(Inquiry.source.ilike(f"%{source_term}%"))
    platform_term = source_platform.strip() if source_platform else ""
    if platform_term:
        filters.append(Inquiry.source_platform.ilike(f"%{platform_term}%"))
    search_term = query.strip() if query else ""
    if search_term:
        term = f"%{search_term}%"
        filters.append(
            or_(
                Inquiry.company_name.ilike(term),
                Inquiry.contact_name.ilike(term),
                Inquiry.country.ilike(term),
                Inquiry.email.ilike(term),
                Inquiry.interested_product.ilike(term),
                Inquiry.inquiry_content.ilike(term),
            )
        )
    statement = (
        select(Inquiry)
        .where(*filters)
        .order_by(Inquiry.updated_at.desc(), Inquiry.id.desc())
        .limit(limit)
        .offset(offset)
    )
    total = session.scalar(select(func.count()).select_from(Inquiry).where(*filters)) or 0
    return list(session.scalars(statement)), total


def get_inquiry(session: Session, inquiry_id: int) -> Inquiry:
    inquiry = session.get(Inquiry, inquiry_id)
    if inquiry is None:
        raise NotFoundError("Inquiry not found.")
    return inquiry


def create_inquiry(session: Session, payload: InquiryCreate, creator: User) -> Inquiry:
    if creator.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")
    data = payload.model_dump()
    data["status"] = data["status"].value
    inquiry = Inquiry(**data)
    session.add(inquiry)
    session.commit()
    session.refresh(inquiry)
    return inquiry


def update_inquiry(
    session: Session, inquiry_id: int, payload: InquiryUpdate, editor: User
) -> Inquiry:
    if editor.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")
    inquiry = get_inquiry(session, inquiry_id)
    if _as_status(inquiry.status) is InquiryStatus.CONVERTED:
        raise ConflictError("Converted inquiries are immutable. Update the customer or opportunity instead.")
    changes = payload.model_dump(exclude_unset=True)
    for required_field in (
        "company_name",
        "contact_name",
        "source",
        "source_platform",
        "inquiry_content",
        "status",
    ):
        if changes.get(required_field) is None:
            changes.pop(required_field, None)
    if changes.get("status") is InquiryStatus.CONVERTED:
        raise ConflictError("Use the conversion endpoint to mark an inquiry as converted.")
    if "status" in changes:
        changes["status"] = changes["status"].value
    for field, value in changes.items():
        setattr(inquiry, field, value)
    session.commit()
    session.refresh(inquiry)
    return inquiry


def convert_inquiry(
    session: Session, inquiry_id: int, converter: User
) -> tuple[Inquiry, Customer, Contact, Opportunity]:
    if converter.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")
    inquiry = get_inquiry(session, inquiry_id)
    inquiry_status = _as_status(inquiry.status)
    if inquiry_status is InquiryStatus.CONVERTED or inquiry.converted_opportunity_id is not None:
        raise ConflictError("Inquiry has already been converted.")
    if inquiry_status is InquiryStatus.CLOSED:
        raise ConflictError("A closed inquiry must be reopened before conversion.")

    customer = Customer(
        company_name=inquiry.company_name,
        contact_name=inquiry.contact_name,
        country=inquiry.country,
        email=inquiry.email,
        phone=inquiry.phone,
        whatsapp=inquiry.whatsapp,
        source=inquiry.source,
        source_platform=inquiry.source_platform,
        original_inquiry=inquiry.inquiry_content,
        interested_product=inquiry.interested_product,
        status=CustomerStatus.LEAD,
        sales_stage=CustomerStatus.LEAD,
        owner_id=converter.id,
    )
    session.add(customer)
    try:
        session.flush()
        contact = Contact(
            customer_id=customer.id,
            name=inquiry.contact_name,
            email=inquiry.email,
            phone=inquiry.phone,
            whatsapp=inquiry.whatsapp,
        )
        opportunity = Opportunity(
            customer_id=customer.id,
            owner_id=converter.id,
            name=f"{inquiry.company_name} - {inquiry.interested_product or 'New Opportunity'}",
            interested_product=inquiry.interested_product,
            inquiry_content=inquiry.inquiry_content,
            stage=OpportunityStage.LEAD,
            sales_stage=OpportunitySalesStage.NEW_LEAD.value,
            deal_stage=OpportunityDealStage.NEW_INQUIRY.value,
            probability=10,
        )
        inquiry.customer_id = customer.id
        inquiry.status = InquiryStatus.CONVERTED.value
        session.add_all((contact, opportunity))
        session.flush()
        inquiry.converted_opportunity_id = opportunity.id
        session.add_all(
            (
                OpportunityStageHistory(
                    opportunity_id=opportunity.id,
                    old_stage=None,
                    new_stage=OpportunityStage.LEAD,
                    changed_by_id=converter.id,
                ),
                OpportunitySalesStageHistory(
                    opportunity_id=opportunity.id,
                    old_sales_stage=None,
                    new_sales_stage=OpportunitySalesStage.NEW_LEAD.value,
                    changed_by_id=converter.id,
                ),
                OpportunityDealStageHistory(
                    opportunity_id=opportunity.id,
                    old_deal_stage=None,
                    new_deal_stage=OpportunityDealStage.NEW_INQUIRY.value,
                    changed_by_id=converter.id,
                ),
            )
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError("Inquiry has already been converted.") from error

    for record in (inquiry, customer, contact, opportunity):
        session.refresh(record)
    return inquiry, customer, contact, opportunity
