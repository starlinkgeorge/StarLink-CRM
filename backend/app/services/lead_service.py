from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.customer import Contact, Customer, CustomerStatus
from app.models.lead import (
    Lead,
    LeadStatus,
    Opportunity,
    OpportunitySalesStage,
    OpportunitySalesStageHistory,
    OpportunityStage,
    OpportunityStageHistory,
)
from app.models.user import User, UserRole
from app.schemas.lead import LeadCreate
from app.services.errors import ConflictError, ForbiddenError, NotFoundError


def list_leads(
    session: Session,
    limit: int,
    offset: int,
    query: str | None = None,
    status: LeadStatus | None = None,
    source: str | None = None,
) -> tuple[list[Lead], int]:
    filters = []
    search_term = query.strip() if query else ""
    if search_term:
        term = f"%{search_term}%"
        filters.append(
            or_(
                Lead.company_name.ilike(term),
                Lead.contact_name.ilike(term),
                Lead.country.ilike(term),
                Lead.email.ilike(term),
                Lead.inquiry_content.ilike(term),
                Lead.interested_product.ilike(term),
            )
        )
    if status is not None:
        filters.append(Lead.status == status)
    source_term = source.strip() if source else ""
    if source_term:
        filters.append(Lead.source.ilike(f"%{source_term}%"))

    statement = (
        select(Lead)
        .where(*filters)
        .order_by(Lead.updated_at.desc(), Lead.id.desc())
        .limit(limit)
        .offset(offset)
    )
    total = session.scalar(select(func.count()).select_from(Lead).where(*filters)) or 0
    return list(session.scalars(statement)), total


def get_lead(session: Session, lead_id: int, include_opportunity: bool = False) -> Lead:
    statement = select(Lead).where(Lead.id == lead_id)
    if include_opportunity:
        statement = statement.options(selectinload(Lead.opportunity))
    lead = session.scalar(statement)
    if lead is None:
        raise NotFoundError("Lead not found.")
    return lead


def create_lead(session: Session, payload: LeadCreate, creator: User) -> Lead:
    if creator.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")
    lead = Lead(**payload.model_dump())
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead


def convert_lead(
    session: Session, lead_id: int, converter: User
) -> tuple[Lead, Customer, Contact, Opportunity]:
    if converter.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")

    lead = get_lead(session, lead_id, include_opportunity=True)
    if lead.status is LeadStatus.CONVERTED or lead.opportunity is not None:
        raise ConflictError("Lead has already been converted.")
    if lead.status is LeadStatus.LOST:
        raise ConflictError("A lost Lead must be reopened before conversion.")

    customer = Customer(
        company_name=lead.company_name,
        contact_name=lead.contact_name,
        country=lead.country,
        email=lead.email,
        phone=lead.phone,
        whatsapp=lead.whatsapp,
        source=lead.source,
        interested_product=lead.interested_product,
        status=CustomerStatus.LEAD,
        sales_stage=CustomerStatus.LEAD,
        owner_id=converter.id,
    )
    session.add(customer)
    try:
        session.flush()
        contact = Contact(
            customer_id=customer.id,
            name=lead.contact_name,
            email=lead.email,
            phone=lead.phone,
            whatsapp=lead.whatsapp,
        )
        opportunity = Opportunity(
            customer_id=customer.id,
            source_lead_id=lead.id,
            owner_id=converter.id,
            name=f"{lead.company_name} - {lead.interested_product or 'New Opportunity'}",
            interested_product=lead.interested_product,
            inquiry_content=lead.inquiry_content,
            stage=OpportunityStage.LEAD,
            sales_stage=OpportunitySalesStage.NEW_LEAD.value,
            probability=10,
        )
        lead.status = LeadStatus.CONVERTED
        session.add_all((contact, opportunity))
        session.flush()
        session.add(
            OpportunityStageHistory(
                opportunity_id=opportunity.id,
                old_stage=None,
                new_stage=OpportunityStage.LEAD,
                changed_by_id=converter.id,
            )
        )
        session.add(
            OpportunitySalesStageHistory(
                opportunity_id=opportunity.id,
                old_sales_stage=None,
                new_sales_stage=OpportunitySalesStage.NEW_LEAD.value,
                changed_by_id=converter.id,
            )
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ConflictError("Lead has already been converted.") from error

    for record in (lead, customer, contact, opportunity):
        session.refresh(record)
    return lead, customer, contact, opportunity
