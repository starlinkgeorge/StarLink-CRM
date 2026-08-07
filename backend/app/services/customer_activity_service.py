from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.customer_activity import CustomerStatusHistory
from app.models.followup import FollowUp
from app.schemas.customer_activity import CustomerActivityRead


def list_customer_timeline(
    session: Session, customer: Customer
) -> list[CustomerActivityRead]:
    sortable_events: list[tuple[datetime, int, int, CustomerActivityRead]] = [
        (
            customer.created_at,
            0,
            customer.id,
            CustomerActivityRead(
                event_id=f"customer-{customer.id}",
                event_type="customer_created",
                occurred_at=customer.created_at,
            ),
        )
    ]

    followups = session.scalars(
        select(FollowUp).where(FollowUp.customer_id == customer.id)
    )
    for followup in followups:
        sortable_events.append(
            (
                followup.created_at,
                1,
                followup.id,
                CustomerActivityRead(
                    event_id=f"followup-{followup.id}",
                    event_type="followup",
                    occurred_at=followup.created_at,
                    user_id=followup.user_id,
                    content=followup.content,
                    followup_type=followup.type,
                    next_followup_date=followup.next_followup_date,
                ),
            )
        )

    status_changes = session.scalars(
        select(CustomerStatusHistory).where(CustomerStatusHistory.customer_id == customer.id)
    )
    for change in status_changes:
        sortable_events.append(
            (
                change.created_at,
                2,
                change.id,
                CustomerActivityRead(
                    event_id=f"status-{change.id}",
                    event_type="status_changed",
                    occurred_at=change.created_at,
                    user_id=change.changed_by_id,
                    old_status=change.old_status,
                    new_status=change.new_status,
                ),
            )
        )

    sortable_events.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return [event for _, _, _, event in sortable_events]
