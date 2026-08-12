from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.customer_center import CustomerCenter
from app.services import (
    access_service,
    customer_activity_service,
    customer_service,
    opportunity_service,
    quotation_service,
)


def get_customer_center(
    session: Session, customer_id: int, current_user: User
) -> CustomerCenter:
    """Load the customer center without widening any existing access scope."""
    customer = customer_service.get_customer(session, customer_id, include_relations=True)
    access_service.ensure_customer_read_access(current_user, customer)
    opportunities, _ = opportunity_service.list_opportunities(
        session,
        current_user,
        limit=100,
        offset=0,
        customer_id=customer.id,
    )
    quotations, _ = quotation_service.list_quotations(
        session,
        current_user,
        limit=100,
        offset=0,
        customer_id=customer.id,
    )
    return CustomerCenter.model_validate(
        {
            **customer.__dict__,
            "automatic_stage_judgement": customer.automatic_stage_judgement,
            "suggested_followup_date": customer.suggested_followup_date,
            "calculated_followup_reminder_status": customer.calculated_followup_reminder_status,
            "calculated_followup_reminder_label": customer.calculated_followup_reminder_label,
            "opportunities": opportunities,
            "quotations": quotations,
            "activities": customer_activity_service.list_customer_timeline(session, customer),
            "score_history": customer.score_history,
        }
    )
