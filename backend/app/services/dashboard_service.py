from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer, CustomerStatus
from app.models.followup import FollowUp
from app.models.user import User
from app.services.access_service import customer_scope


def _serialize_followup(followup: FollowUp, customer_name: str) -> dict:
    return {
        "id": followup.id,
        "customer_id": followup.customer_id,
        "customer_name": customer_name,
        "type": followup.type.value,
        "content": followup.content,
        "next_followup_date": followup.next_followup_date,
    }


def get_dashboard_stats(session: Session, user: User) -> dict:
    filters = []
    scope = customer_scope(user)
    if scope is not None:
        filters.append(scope)
    customer_count = session.scalar(select(func.count()).select_from(Customer).where(*filters)) or 0
    followup_count = (
        session.scalar(
            select(func.count()).select_from(FollowUp).join(Customer).where(*filters)
        )
        or 0
    )
    today = date.today()
    new_customers_today = session.scalar(
        select(func.count()).select_from(Customer).where(*filters, func.date(Customer.created_at) == today)
    ) or 0
    due_followups = session.scalar(
        select(func.count()).select_from(FollowUp).join(Customer).where(
            *filters, FollowUp.next_followup_date.is_not(None), FollowUp.next_followup_date <= today
        )
    ) or 0
    pipeline_rows = session.execute(
        select(Customer.status, func.count(Customer.id)).where(*filters).group_by(Customer.status)
    ).all()
    counts = {status.value: 0 for status in CustomerStatus}
    counts.update({status.value: count for status, count in pipeline_rows})
    upcoming = session.execute(
        select(FollowUp, Customer.company_name)
        .join(Customer)
        .where(*filters, FollowUp.next_followup_date.is_not(None))
        .order_by(FollowUp.next_followup_date.asc(), FollowUp.id.desc())
        .limit(6)
    ).all()

    latest_followup_ids = (
        select(func.max(FollowUp.id).label("id"))
        .join(Customer)
        .where(*filters)
        .group_by(FollowUp.customer_id)
        .subquery()
    )
    current_reminders = session.execute(
        select(FollowUp, Customer.company_name)
        .join(Customer)
        .where(
            FollowUp.id.in_(select(latest_followup_ids.c.id)),
            FollowUp.next_followup_date.is_not(None),
            FollowUp.next_followup_date <= today,
        )
        .order_by(FollowUp.next_followup_date.asc(), FollowUp.id.desc())
    ).all()
    today_reminders = [
        (followup, name)
        for followup, name in current_reminders
        if followup.next_followup_date == today
    ]
    overdue_reminders = [
        (followup, name)
        for followup, name in current_reminders
        if followup.next_followup_date < today
    ]
    return {
        "customer_count": customer_count,
        "followup_count": followup_count,
        "new_customers_today": new_customers_today,
        "due_followups": due_followups,
        "today_followup_count": len(today_reminders),
        "overdue_followup_count": len(overdue_reminders),
        "pipeline": [{"status": status.value, "count": counts[status.value]} for status in CustomerStatus],
        "upcoming_followups": [_serialize_followup(followup, name) for followup, name in upcoming],
        "today_followups": [
            {**_serialize_followup(followup, name), "reminder_status": "today"}
            for followup, name in today_reminders[:10]
        ],
        "overdue_followups": [
            {**_serialize_followup(followup, name), "reminder_status": "overdue"}
            for followup, name in overdue_reminders[:10]
        ],
    }
