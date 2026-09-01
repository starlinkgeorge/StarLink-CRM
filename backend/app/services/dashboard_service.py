from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer, CustomerStatus
from app.models.followup import FollowUp
from app.models.opportunity import Opportunity, OpportunityReminderStatus, OpportunitySalesStage
from app.models.user import User, UserRole
from app.models.task import Task
from app.schemas.dashboard import DashboardTaskCreate, DashboardTaskRead
from app.services.errors import ForbiddenError, NotFoundError
from app.services.access_service import customer_scope
from app.services.followup_reminder_service import (
    list_customer_followup_reminders,
    shanghai_today,
)


def _serialize_followup(followup: FollowUp, customer_name: str) -> dict:
    return {
        "id": followup.id,
        "customer_id": followup.customer_id,
        "customer_name": customer_name,
        "type": followup.type.value,
        "content": followup.content,
        "next_followup_date": followup.next_followup_date,
    }


def _ensure_dashboard_task_admin(user: User) -> None:
    if user.role is not UserRole.ADMIN:
        raise ForbiddenError("Only Admin accounts can manage dashboard tasks.")


def _task_read(task: Task, customer_name: str | None) -> DashboardTaskRead:
    return DashboardTaskRead(
        id=task.id, title=task.title, due_date=task.due_date, priority=task.priority,
        status=task.status, customer_id=task.customer_id, customer_name=customer_name,
        created_by_id=task.created_by_id, created_at=task.created_at, completed_at=task.completed_at,
    )


def get_today_tasks(session: Session, user: User) -> list[DashboardTaskRead]:
    _ensure_dashboard_task_admin(user)
    today = shanghai_today()
    priority_order = {"high": 0, "medium": 1, "low": 2}
    rows = session.execute(
        select(Task, Customer.company_name)
        .outerjoin(Customer, Customer.id == Task.customer_id)
        .where(Task.created_by_id == user.id, Task.status == "pending", Task.due_date <= today)
        .order_by(Task.due_date.asc(), Task.id.asc())
    ).all()
    result = [_task_read(task, company_name) for task, company_name in rows]
    return sorted(result, key=lambda task: (task.due_date >= today, priority_order[task.priority], task.due_date, task.id))


def create_dashboard_task(session: Session, payload: DashboardTaskCreate, user: User) -> DashboardTaskRead:
    _ensure_dashboard_task_admin(user)
    if payload.customer_id is not None and session.get(Customer, payload.customer_id) is None:
        raise NotFoundError("Customer not found.")
    task = Task(**payload.model_dump(), created_by_id=user.id, status="pending")
    session.add(task); session.commit(); session.refresh(task)
    customer = session.get(Customer, task.customer_id) if task.customer_id else None
    return _task_read(task, customer.company_name if customer else None)


def complete_dashboard_task(session: Session, task_id: int, user: User) -> DashboardTaskRead:
    _ensure_dashboard_task_admin(user)
    task = session.scalar(select(Task).where(Task.id == task_id, Task.created_by_id == user.id))
    if task is None:
        raise NotFoundError("Task not found.")
    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    session.commit(); session.refresh(task)
    customer = session.get(Customer, task.customer_id) if task.customer_id else None
    return _task_read(task, customer.company_name if customer else None)


def delete_dashboard_task(session: Session, task_id: int, user: User) -> None:
    _ensure_dashboard_task_admin(user)
    task = session.scalar(select(Task).where(Task.id == task_id, Task.created_by_id == user.id))
    if task is None:
        raise NotFoundError("Task not found.")
    session.delete(task)
    session.commit()


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
    # Keep the legacy dashboard counters on their existing server-date
    # behaviour.  The new follow-up reminders alone use the China business
    # day, including when the API runs in Vercel's UTC environment.
    today = date.today()
    followup_today = shanghai_today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=7)
    followup_week_start = followup_today - timedelta(days=followup_today.weekday())
    followup_week_end = followup_week_start + timedelta(days=7)
    new_customers_today = session.scalar(
        select(func.count())
        .select_from(Customer)
        .where(*filters, func.date(Customer.created_at) == today)
    ) or 0
    due_followups = session.scalar(
        select(func.count()).select_from(FollowUp).join(Customer).where(
            *filters,
            FollowUp.next_followup_date.is_not(None),
            FollowUp.next_followup_date <= followup_today,
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
    # V10 planned-task counts use the denormalized current customer reminder.
    # The V5 week_followup_count above remains a count of records created this
    # week for backwards-compatible dashboard consumers.
    today_due_customer_count = session.scalar(
        select(func.count()).select_from(Customer).where(
            *filters, Customer.next_followup_date == followup_today
        )
    ) or 0
    overdue_customer_count = session.scalar(
        select(func.count()).select_from(Customer).where(
            *filters, Customer.next_followup_date < followup_today
        )
    ) or 0
    week_followup_task_count = session.scalar(
        select(func.count()).select_from(Customer).where(
            *filters,
            Customer.next_followup_date >= followup_week_start,
            Customer.next_followup_date < followup_week_end,
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
            FollowUp.next_followup_date <= followup_today,
        )
        .order_by(FollowUp.next_followup_date.asc(), FollowUp.id.desc())
    ).all()
    today_reminders = [
        (followup, name)
        for followup, name in current_reminders
        if followup.next_followup_date == followup_today
    ]
    overdue_reminders = [
        (followup, name)
        for followup, name in current_reminders
        if followup.next_followup_date < followup_today
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
    reminder_opportunities = list(
        session.scalars(
            select(Opportunity)
            .where(*opportunity_filters)
            .options(joinedload(Opportunity.customer))
            .order_by(
                Opportunity.quote_followup_due_date.asc().nulls_last(),
                Opportunity.last_activity_at.asc(),
                Opportunity.id.asc(),
            )
        )
    )
    opportunity_reminders = []
    quote_followup_overdue_count = 0
    inactive_opportunity_count = 0
    for opportunity in reminder_opportunities:
        reminder_status = opportunity.reminder_status
        if reminder_status is OpportunityReminderStatus.NONE:
            continue
        if reminder_status is OpportunityReminderStatus.QUOTE_FOLLOWUP_DUE:
            quote_followup_overdue_count += 1
        elif reminder_status is OpportunityReminderStatus.INACTIVE:
            inactive_opportunity_count += 1
        opportunity_reminders.append(
            {
                "id": opportunity.id,
                "name": opportunity.name,
                "customer_id": opportunity.customer_id,
                "customer_name": opportunity.customer.company_name,
                "reminder_status": reminder_status,
                "quote_followup_due_date": opportunity.quote_followup_due_date,
                "last_activity_at": opportunity.last_activity_at,
            }
        )
    followup_reminder_summary, _ = list_customer_followup_reminders(session, user)
    return {
        "customer_count": customer_count,
        "followup_count": followup_count,
        "new_customers_today": new_customers_today,
        "due_followups": due_followups,
        "today_followup_count": len(today_reminders),
        "overdue_followup_count": len(overdue_reminders),
        "pending_followup_customer_count": len(current_reminders),
        "week_followup_count": week_followup_count,
        "today_due_customer_count": today_due_customer_count,
        "overdue_customer_count": overdue_customer_count,
        "week_followup_task_count": week_followup_task_count,
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
        "quote_followup_overdue_count": quote_followup_overdue_count,
        "inactive_opportunity_count": inactive_opportunity_count,
        "opportunity_reminders": opportunity_reminders[:10],
        "followup_reminder_overdue_count": followup_reminder_summary["overdue_count"],
        "followup_reminder_today_count": followup_reminder_summary["today_count"],
        "followup_reminder_upcoming_count": followup_reminder_summary["upcoming_count"],
        "followup_reminder_unfollowed_count": followup_reminder_summary["unfollowed_count"],
    }
