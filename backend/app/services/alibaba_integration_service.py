from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadStatus
from app.models.user import User, UserRole
from app.schemas.alibaba import AlibabaInquiryCreate
from app.services.errors import ForbiddenError


def _find_existing_lead(session: Session, payload: AlibabaInquiryCreate) -> Lead | None:
    if payload.email:
        email = payload.email.casefold()
        existing = session.scalar(
            select(Lead)
            .where(func.lower(func.trim(Lead.email)) == email)
            .order_by(Lead.id.asc())
        )
        if existing is not None:
            return existing

    return session.scalar(
        select(Lead)
        .where(
            func.lower(func.trim(Lead.company_name)) == payload.company_name.casefold(),
            func.lower(func.trim(Lead.contact_name)) == payload.contact_name.casefold(),
        )
        .order_by(Lead.id.asc())
    )


def receive_inquiry(
    session: Session, payload: AlibabaInquiryCreate, receiver: User
) -> tuple[Lead, bool]:
    if receiver.role is UserRole.VIEWER:
        raise ForbiddenError("Viewer accounts have read-only access.")

    existing = _find_existing_lead(session, payload)
    if existing is not None:
        return existing, False

    data = payload.model_dump(exclude={"source"})
    lead = Lead(
        **data,
        source="Alibaba",
        status=LeadStatus.NEW,
    )
    session.add(lead)
    session.commit()
    session.refresh(lead)
    return lead, True
