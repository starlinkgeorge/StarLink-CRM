from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer, CustomerStatus
from app.models.followup import FollowUp
from app.models.inquiry import Inquiry, InquiryStatus
from app.models.lead import Opportunity, OpportunitySalesStage
from app.models.user import User, UserRole
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
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    new_customers_today = session.scalar(
        select(func.count())
        .select_from(Customer)
        .where(*filters, func.date(Customer.created_at) == today)
    ) or 0
    today_inquiry_count = session.scalar(
        select(func.count())
        .select_from(Inquiry)
        .where(func.date(Inquiry.created_at) == today)
    ) or 0
    pending_inquiry_count = session.scalar(
        select(func.count())
        .select_from(Inquiry)
        .where(Inquiry.status.in_((InquiryStatus.NEW.value, InquiryStatus.PROCESSING.value)))
    ) or 0
    inquiry_source_rows = session.execute(
        select(Inquiry.source, func.count(Inquiry.id))
        .group_by(Inquiry.source)
        .order_by(Inquiry.source.asc())
    ).all()
    due_followups = session.scalar(
        select(func.count()).select_from(FollowUp).join(Customer).where(
            *filters, FollowUp.next_followup_date.is_not(None), FollowUp.next_followup_date <= today
        )
    ) or 0
    week_followup_count = session.scalar(
        select(func.count())
        .select_from(FollowUp)
        .join(Customer)
        .where(
            *filters,
            func.date(FollowUp.created_at) >= week_start,
            func.date(FollowUp.created_at) < week_end,
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
    opportunity_filters = []
    if user.role is UserRole.SALES:
        opportunity_filters.append(Opportunity.owner_id == user.id)
    opportunity_rows = session.execute(
        select(Opportunity.sales_stage, func.count(Opportunity.id))
        .where(*opportunity_filters)
        .group_by(Opportunity.sales_stage)
    ).all()
    opportunity_counts = {
        OpportunitySalesStage(stage): count for stage, count in opportunity_rows
    }
    won_opportunities = opportunity_counts.get(OpportunitySalesStage.WON, 0)
    lost_opportunities = opportunity_counts.get(OpportunitySalesStage.LOST, 0)
    opportunity_count = sum(opportunity_counts.values())
    amount_rows = session.execute(
        select(Opportunity.currency, func.coalesce(func.sum(Opportunity.amount), 0))
        .where(*opportunity_filters)
        .group_by(Opportunity.currency)
        .order_by(Opportunity.currency.asc())
    ).all()
    return {
        "customer_count": customer_count,
        "followup_count": followup_count,
        "new_customers_today": new_customers_today,
        "today_inquiry_count": today_inquiry_count,
        "pending_inquiry_count": pending_inquiry_count,
        "inquiry_source_stats": [
            {"source": source, "count": count} for source, count in inquiry_source_rows
        ],
        "due_followups": due_followups,
        "today_followup_count": len(today_reminders),
        "overdue_followup_count": len(overdue_reminders),
        "pending_followup_customer_count": len(current_reminders),
        "week_followup_count": week_followup_count,
        "pipeline": [
            {"status": status.value, "count": counts[status.value]}
            for status in CustomerStatus
        ],
        "upcoming_followups": [_serialize_followup(followup, name) for followup, name in upcoming],
        "today_followups": [
            {**_serialize_followup(followup, name), "reminder_status": "today"}
            for followup, name in today_reminders[:10]
        ],
        "overdue_followups": [
            {**_serialize_followup(followup, name), "reminder_status": "overdue"}
            for followup, name in overdue_reminders[:10]
        ],
        "opportunity_count": opportunity_count,
        "active_opportunity_count": opportunity_count - won_opportunities - lost_opportunities,
        "won_opportunity_count": won_opportunities,
        "lost_opportunity_count": lost_opportunities,
        "opportunity_amounts": [
            {"currency": currency, "amount": amount} for currency, amount in amount_rows
        ],
        # Kept separately so V7 consumers can label it as the sales total while
        # existing dashboards continue to use opportunity_amounts unchanged.
        "opportunity_total_amounts": [
            {"currency": currency, "amount": amount} for currency, amount in amount_rows
        ],
        "opportunity_pipeline": [
            {
                "sales_stage": sales_stage.value,
                "count": opportunity_counts.get(sales_stage, 0),
            }
            for sales_stage in OpportunitySalesStage
        ],
    }
