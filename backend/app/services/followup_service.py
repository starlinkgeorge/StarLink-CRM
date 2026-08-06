from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.followup import FollowUp
from app.models.user import User
from app.schemas.followup import FollowUpCreate
from app.services.errors import NotFoundError


def create_followup(session: Session, payload: FollowUpCreate) -> FollowUp:
    if session.get(Customer, payload.customer_id) is None:
        raise NotFoundError("Customer not found.")
    if session.get(User, payload.user_id) is None:
        raise NotFoundError("User not found.")
    followup = FollowUp(**payload.model_dump())
    session.add(followup)
    session.commit()
    session.refresh(followup)
    return followup


def list_customer_followups(session: Session, customer_id: int) -> list[FollowUp]:
    if session.get(Customer, customer_id) is None:
        raise NotFoundError("Customer not found.")
    statement = (
        select(FollowUp)
        .where(FollowUp.customer_id == customer_id)
        .order_by(FollowUp.created_at.desc(), FollowUp.id.desc())
    )
    return list(session.scalars(statement))
