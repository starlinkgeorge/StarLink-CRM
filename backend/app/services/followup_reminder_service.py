"""Dynamic customer follow-up reminders for the China business day.

Reminder dates and cold-customer state are calculated on reads from the
customer's acquisition date, current manual stage, and real follow-up history.
The database flag is refreshed whenever a customer or follow-up changes, but a
calendar day passing never depends on a cron job to make the read correct.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from app.services.customer_followup_stage_service import normalize_manual_followup_stage
from app.services.system_settings_service import FollowupRules, get_followup_rules

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.user import User
    from sqlalchemy.orm import Session


CHINA_TIMEZONE = ZoneInfo("Asia/Shanghai")
COLD_CUSTOMER_AFTER_DAYS = 15
NEW_CUSTOMER_STAGE = "新客户未回复"

# Approved cadence.  Do not infer a cadence for historical unknown stages.
FOLLOWUP_STAGE_INTERVAL_DAYS: dict[str, int] = {
    "新客户未回复": 3,
    "沟通中": 3,
    "已报价": 1,
    "已成交样品": 3,
    # Closed/repeat stages intentionally retain the existing low-frequency
    # cadence; they never receive a new high-frequency development reminder.
    "已成交": 7,
    "已复购": 30,
}


class FollowupReminderStatus(StrEnum):
    OVERDUE = "overdue"
    TODAY = "today"
    UPCOMING = "upcoming"
    NOT_NEEDED = "not_needed"
    UNFOLLOWED = "unfollowed"
    STAGE_UNSET = "stage_unset"
    NOT_APPLICABLE = "not_applicable"


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
        return now.date()
    return now.astimezone(CHINA_TIMEZONE).date()


def cold_customer_effective_date(
    customer_acquired_at: date | None, *, rules: FollowupRules | None = None
) -> date | None:
    if customer_acquired_at is None:
        return None
    return customer_acquired_at + timedelta(
        days=(rules or get_followup_rules()).cold_customer_after_days
    )


def is_customer_cold(
    customer_acquired_at: date | None,
    followup_stage: str | None,
    *,
    today: date | None = None,
    rules: FollowupRules | None = None,
) -> bool:
    """Whether a still-unanswered new customer has become cold.

    The fifteen-day age is deliberately based only on acquisition date.  A
    later follow-up does not restart that commercial clock.
    """
    effective_date = cold_customer_effective_date(customer_acquired_at, rules=rules)
    return bool(
        effective_date is not None
        and normalize_manual_followup_stage(followup_stage) == NEW_CUSTOMER_STAGE
        and (today or shanghai_today()) >= effective_date
    )


def sync_customer_cold_status(
    customer: Customer, *, today: date | None = None, session: Session | None = None
) -> None:
    """Refresh the persisted flag after a write without changing history."""
    customer.is_cold_customer = is_customer_cold(
        customer.customer_acquired_at,
        customer.followup_stage,
        today=today,
        rules=get_followup_rules(session),
    )


def _reminder_for_due_date(
    suggested_date: date,
    *,
    today: date,
    priority_offset: int = 0,
) -> FollowupReminder:
    delta = (suggested_date - today).days
    if delta < 0:
        overdue_days = abs(delta)
        return FollowupReminder(
            FollowupReminderStatus.OVERDUE,
            f"已逾期 {overdue_days} 天",
            suggested_date,
            priority_offset,
            overdue_days=overdue_days,
            days_until_due=delta,
        )
    if delta == 0:
        return FollowupReminder(
            FollowupReminderStatus.TODAY, "今天跟进", suggested_date, priority_offset + 1, days_until_due=0
        )
    if delta <= 3:
        label = "明天跟进" if delta == 1 else f"{delta}天后跟进"
        return FollowupReminder(
            FollowupReminderStatus.UPCOMING, label, suggested_date, priority_offset + 1 + delta, days_until_due=delta
        )
    return FollowupReminder(
        FollowupReminderStatus.NOT_NEEDED, "暂不需要", suggested_date, priority_offset + 8, days_until_due=delta
    )


def calculate_customer_followup_reminder(
    customer_acquired_at: date | None,
    latest_followup_date: date | None,
    followup_stage: str | None,
    *,
    is_cold_customer: bool | None = None,
    today: date | None = None,
    rules: FollowupRules | None = None,
) -> FollowupReminder:
    """Calculate one safe, real-time reminder for a customer.

    ``is_cold_customer`` is accepted for model/API compatibility.  The state is
    always recalculated from acquisition date and stage so a stale database flag
    cannot produce a wrong reminder after a calendar boundary.
    """
    if customer_acquired_at is None:
        return FollowupReminder(FollowupReminderStatus.NOT_APPLICABLE, "不适用", None, 99)

    current_day = today or shanghai_today()
    active_rules = rules or get_followup_rules()
    normalized_stage = normalize_manual_followup_stage(followup_stage) or ""
    cold = is_customer_cold(
        customer_acquired_at, normalized_stage, today=current_day, rules=active_rules
    )
    if cold:
        base_date = latest_followup_date or cold_customer_effective_date(
            customer_acquired_at, rules=active_rules
        )
        assert base_date is not None
        return _reminder_for_due_date(
            base_date + timedelta(days=active_rules.cold_customer_reminder_days),
            today=current_day,
            priority_offset=30,
        )

    # Imported/new records can legitimately have an acquisition date but no
    # manual stage or real follow-up yet.  They remain actionable instead of
    # being hidden behind the historical "stage unset" compatibility state.
    if latest_followup_date is None and not normalized_stage:
        suggested_date = customer_acquired_at + timedelta(
            days=active_rules.new_customer_first_followup_days
        )
        return FollowupReminder(
            FollowupReminderStatus.UNFOLLOWED,
            "尚未跟进",
            suggested_date,
            25,
            days_until_due=(suggested_date - current_day).days,
        )

    interval_days = {
        NEW_CUSTOMER_STAGE: active_rules.new_customer_unanswered_reminder_days,
        "沟通中": active_rules.communicating_reminder_days,
        "已报价": active_rules.quoted_reminder_days,
        "已成交样品": FOLLOWUP_STAGE_INTERVAL_DAYS["已成交样品"],
        "已成交": FOLLOWUP_STAGE_INTERVAL_DAYS["已成交"],
        "已复购": FOLLOWUP_STAGE_INTERVAL_DAYS["已复购"],
    }.get(normalized_stage)
    if interval_days is None:
        return FollowupReminder(FollowupReminderStatus.STAGE_UNSET, "未设置跟进阶段", None, 90)

    # A newly acquired customer has no follow-up record yet: acquisition date
    # is the trusted baseline for its first reminder.
    base_date = latest_followup_date or customer_acquired_at
    return _reminder_for_due_date(base_date + timedelta(days=interval_days), today=current_day)


def calculate_followup_reminder(
    latest_followup_date: date | None,
    followup_stage: str | None,
    *,
    today: date | None = None,
    rules: FollowupRules | None = None,
) -> FollowupReminder:
    """Legacy helper retained for callers that have no acquisition date."""
    if latest_followup_date is None:
        return FollowupReminder(FollowupReminderStatus.UNFOLLOWED, "尚未跟进", None, 80)
    normalized_stage = normalize_manual_followup_stage(followup_stage) or ""
    active_rules = rules or get_followup_rules()
    interval_days = {
        NEW_CUSTOMER_STAGE: active_rules.new_customer_unanswered_reminder_days,
        "沟通中": active_rules.communicating_reminder_days,
        "已报价": active_rules.quoted_reminder_days,
        "已成交样品": FOLLOWUP_STAGE_INTERVAL_DAYS["已成交样品"],
        "已成交": FOLLOWUP_STAGE_INTERVAL_DAYS["已成交"],
        "已复购": FOLLOWUP_STAGE_INTERVAL_DAYS["已复购"],
    }.get(normalized_stage)
    if interval_days is None:
        return FollowupReminder(FollowupReminderStatus.STAGE_UNSET, "未设置跟进阶段", None, 90)
    return _reminder_for_due_date(
        latest_followup_date + timedelta(days=interval_days), today=today or shanghai_today()
    )


def is_followup_reminder_applicable(
    customer_acquired_at: date | None,
    *,
    has_followup_since_rule_start: bool = False,
    rules: FollowupRules | None = None,
) -> bool:
    """Keep pre-rule customers out until a real later follow-up reactivates them."""
    if customer_acquired_at is None:
        return False
    active_rules = rules or get_followup_rules()
    return (
        customer_acquired_at >= active_rules.rule_start_date
        or has_followup_since_rule_start
    )


def _sort_key(item: dict[str, object]) -> tuple[int, int, str, int]:
    reminder = item["followup_reminder"]
    assert isinstance(reminder, dict)
    stage = normalize_manual_followup_stage(item.get("followup_stage")) or ""
    # Higher-intent customers stay ahead of cold customers even if their dates
    # are all currently actionable.
    stage_priority = {"已报价": 0, "沟通中": 10, "新客户未回复": 20}.get(stage, 40)
    if bool(item.get("is_cold_customer")):
        stage_priority = 30
    overdue_days = int(reminder["overdue_days"] or 0)
    days_until_due = int(reminder["days_until_due"] or 0)
    urgency = int(reminder["priority"])
    secondary = -overdue_days if reminder["status"] == FollowupReminderStatus.OVERDUE else days_until_due
    return (stage_priority, urgency, secondary, str(item["company_name"]).casefold(), int(item["id"]))


def _serialize_customer(
    customer: Customer, *, today: date, rules: FollowupRules
) -> dict[str, object]:
    latest_followup_date = customer.effective_latest_followup_date
    has_followup_since_rule_start = any(
        followup.followup_date >= rules.rule_start_date
        for followup in customer.followups
        if followup.followup_date is not None
    )
    if not is_followup_reminder_applicable(
        customer.customer_acquired_at,
        has_followup_since_rule_start=has_followup_since_rule_start,
        rules=rules,
    ):
        reminder = FollowupReminder(
            FollowupReminderStatus.NOT_APPLICABLE,
            "跟进规则开始前获得",
            None,
            99,
        ).as_dict()
        return {
            "id": customer.id,
            "customer_name": customer.contact_name,
            "company_name": customer.company_name,
            "country": customer.country,
            "customer_level_value": customer.customer_level_value,
            "customer_total_score": customer.customer_total_score,
            "followup_stage": customer.followup_stage,
            "latest_followup_date": latest_followup_date,
            "is_cold_customer": False,
            "suggested_followup_date": None,
            "followup_reminder": reminder,
            "whatsapp": customer.whatsapp,
            "email": customer.email,
        }
    cold = is_customer_cold(
        customer.customer_acquired_at, customer.followup_stage, today=today, rules=rules
    )
    reminder = calculate_customer_followup_reminder(
        customer.customer_acquired_at,
        latest_followup_date,
        customer.followup_stage,
        is_cold_customer=cold,
        today=today,
        rules=rules,
    ).as_dict()
    return {
        "id": customer.id,
        "customer_name": customer.contact_name,
        "company_name": customer.company_name,
        "country": customer.country,
        "customer_level_value": customer.customer_level_value,
        "customer_total_score": customer.customer_total_score,
        "followup_stage": customer.followup_stage,
        "latest_followup_date": latest_followup_date,
        "is_cold_customer": cold,
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
    """Return accessible reminder customers, ranked by commercial priority."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.customer import Customer
    from app.services.access_service import customer_scope

    current_day = today or shanghai_today()
    rules = get_followup_rules(session)
    scope = customer_scope(user)
    statement = select(Customer).options(selectinload(Customer.followups)).where(
        Customer.customer_acquired_at.is_not(None)
    )
    if scope is not None:
        statement = statement.where(scope)
    rows = [
        _serialize_customer(customer, today=current_day, rules=rules)
        for customer in session.scalars(statement)
    ]
    summary = {
        "overdue_count": sum(item["followup_reminder"]["status"] == FollowupReminderStatus.OVERDUE for item in rows),
        "today_count": sum(item["followup_reminder"]["status"] == FollowupReminderStatus.TODAY for item in rows),
        "upcoming_count": sum(item["followup_reminder"]["status"] == FollowupReminderStatus.UPCOMING for item in rows),
        "unfollowed_count": sum(item["followup_reminder"]["status"] == FollowupReminderStatus.UNFOLLOWED for item in rows),
    }
    if status_filter is not None:
        rows = [item for item in rows if item["followup_reminder"]["status"] == status_filter]
    rows.sort(key=_sort_key)
    return summary, rows
