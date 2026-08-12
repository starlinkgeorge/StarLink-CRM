"""Dynamic customer follow-up reminders for the China business day.

The V1 reminder state intentionally is not stored in PostgreSQL.  It is
derived every time from the customer archive's latest follow-up date and
follow-up stage, so it changes correctly as the calendar advances.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.user import User
    from sqlalchemy.orm import Session


CHINA_TIMEZONE = ZoneInfo("Asia/Shanghai")

# These values are the user's approved V1 cadence.  Do not silently fall back
# to a guessed cadence for an unconfigured or legacy follow-up stage.
FOLLOWUP_STAGE_INTERVAL_DAYS: dict[str, int] = {
    "新开发未回复": 2,
    "新开发已回复": 1,
    "已报价": 3,
    "已采购样品": 3,
    "已成交": 7,
    "已复购": 30,
    "冷客户": 30,
}


class FollowupReminderStatus(StrEnum):
    OVERDUE = "overdue"
    TODAY = "today"
    UPCOMING = "upcoming"
    NOT_NEEDED = "not_needed"
    UNFOLLOWED = "unfollowed"
    STAGE_UNSET = "stage_unset"


@dataclass(frozen=True)
class FollowupReminder:
    status: FollowupReminderStatus
    label: str
    suggested_followup_date: date | None
    priority: int
    overdue_days: int | None = None
    days_until_due: int | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def shanghai_today(now: datetime | None = None) -> date:
    """Return today's date for all CRM follow-up calculations."""
    if now is None:
        return datetime.now(CHINA_TIMEZONE).date()
    if now.tzinfo is None:
        # A caller that supplies a clock value is already supplying the
        # business-local clock.  This keeps tests deterministic.
        return now.date()
    return now.astimezone(CHINA_TIMEZONE).date()


def calculate_followup_reminder(
    latest_followup_date: date | None,
    followup_stage: str | None,
    *,
    today: date | None = None,
) -> FollowupReminder:
    """Calculate the V1 customer reminder without storing a derived value."""
    if latest_followup_date is None:
        return FollowupReminder(
            status=FollowupReminderStatus.UNFOLLOWED,
            label="尚未跟进",
            suggested_followup_date=None,
            priority=6,
        )

    normalized_stage = (followup_stage or "").strip()
    interval_days = FOLLOWUP_STAGE_INTERVAL_DAYS.get(normalized_stage)
    if interval_days is None:
        return FollowupReminder(
            status=FollowupReminderStatus.STAGE_UNSET,
            label="未设置跟进阶段",
            suggested_followup_date=None,
            priority=8,
        )

    current_day = today or shanghai_today()
    suggested_date = latest_followup_date + timedelta(days=interval_days)
    delta = (suggested_date - current_day).days
    if delta < 0:
        overdue_days = abs(delta)
        return FollowupReminder(
            status=FollowupReminderStatus.OVERDUE,
            label=f"已逾期 {overdue_days} 天",
            suggested_followup_date=suggested_date,
            priority=0,
            overdue_days=overdue_days,
            days_until_due=delta,
        )
    if delta == 0:
        return FollowupReminder(
            status=FollowupReminderStatus.TODAY,
            label="今天跟进",
            suggested_followup_date=suggested_date,
            priority=1,
            days_until_due=0,
        )
    if delta <= 3:
        label = "明天跟进" if delta == 1 else f"{delta}天后跟进"
        return FollowupReminder(
            status=FollowupReminderStatus.UPCOMING,
            label=label,
            suggested_followup_date=suggested_date,
            priority=1 + delta,
            days_until_due=delta,
        )
    return FollowupReminder(
        status=FollowupReminderStatus.NOT_NEEDED,
        label="暂不需要",
        suggested_followup_date=suggested_date,
        priority=7,
        days_until_due=delta,
    )


def _sort_key(item: dict[str, object]) -> tuple[int, int, str, int]:
    reminder = item["followup_reminder"]
    assert isinstance(reminder, dict)
    priority = int(reminder["priority"])
    overdue_days = int(reminder["overdue_days"] or 0)
    days_until_due = int(reminder["days_until_due"] or 0)
    # More-overdue customers first. Upcoming customers retain tomorrow,
    # two-days, then three-days order. Stable text/id fallbacks make the list
    # deterministic when dates are identical.
    secondary = -overdue_days if priority == 0 else days_until_due
    return (priority, secondary, str(item["company_name"]).casefold(), int(item["id"]))


def _serialize_customer(customer: Customer, *, today: date) -> dict[str, object]:
    reminder = calculate_followup_reminder(
        customer.latest_followup_date,
        customer.followup_stage,
        today=today,
    ).as_dict()
    return {
        "id": customer.id,
        "customer_name": customer.contact_name,
        "company_name": customer.company_name,
        "country": customer.country,
        "customer_level_value": customer.customer_level_value,
        "customer_total_score": customer.customer_total_score,
        "followup_stage": customer.followup_stage,
        "latest_followup_date": customer.latest_followup_date,
        "suggested_followup_date": reminder["suggested_followup_date"],
        "followup_reminder": reminder,
        "whatsapp": customer.whatsapp,
        "email": customer.email,
    }


def list_customer_followup_reminders(
    session: Session,
    user: User,
    *,
    status_filter: FollowupReminderStatus | None = None,
    today: date | None = None,
) -> tuple[dict[str, int], list[dict[str, object]]]:
    """Return all accessible customers, ranked by the V1 reminder urgency."""
    from sqlalchemy import select

    from app.models.customer import Customer
    from app.services.access_service import customer_scope

    current_day = today or shanghai_today()
    scope = customer_scope(user)
    statement = select(Customer)
    if scope is not None:
        statement = statement.where(scope)
    rows = [_serialize_customer(customer, today=current_day) for customer in session.scalars(statement)]
    summary = {
        "overdue_count": sum(
            item["followup_reminder"]["status"] == FollowupReminderStatus.OVERDUE
            for item in rows
        ),
        "today_count": sum(
            item["followup_reminder"]["status"] == FollowupReminderStatus.TODAY
            for item in rows
        ),
        "upcoming_count": sum(
            item["followup_reminder"]["status"] == FollowupReminderStatus.UPCOMING
            for item in rows
        ),
        "unfollowed_count": sum(
            item["followup_reminder"]["status"] == FollowupReminderStatus.UNFOLLOWED
            for item in rows
        ),
    }
    if status_filter is not None:
        rows = [
            item
            for item in rows
            if item["followup_reminder"]["status"] == status_filter
        ]
    rows.sort(key=_sort_key)
    return summary, rows
