from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services.followup_reminder_service import (
    FollowupReminderStatus,
    calculate_customer_followup_reminder,
    calculate_followup_reminder,
    is_followup_reminder_applicable,
    shanghai_today,
)
from app.services.customer_followup_stage_service import (
    COLD_CUSTOMER_STAGE,
    calculate_automatic_stage_judgement,
    normalize_manual_followup_stage,
)


def test_quotation_stage_calculates_three_day_cadence() -> None:
    reminder = calculate_followup_reminder(
        date(2026, 8, 10), "已报价", today=date(2026, 8, 12)
    )
    assert reminder.suggested_followup_date == date(2026, 8, 13)
    assert reminder.status is FollowupReminderStatus.UPCOMING
    assert reminder.label == "明天跟进"


def test_reminder_statuses_cover_overdue_today_upcoming_and_not_needed() -> None:
    assert calculate_followup_reminder(
        date(2026, 8, 9), "沟通中", today=date(2026, 8, 12)
    ).label == "已逾期 2 天"
    assert calculate_followup_reminder(
        date(2026, 8, 11), "沟通中", today=date(2026, 8, 12)
    ).status is FollowupReminderStatus.TODAY
    assert calculate_followup_reminder(
        date(2026, 8, 11), "已报价", today=date(2026, 8, 12)
    ).label == "2天后跟进"
    assert calculate_followup_reminder(
        date(2026, 8, 12), "已复购", today=date(2026, 8, 12)
    ).status is FollowupReminderStatus.NOT_NEEDED


def test_missing_latest_followup_is_actionable() -> None:
    reminder = calculate_followup_reminder(None, "已报价", today=date(2026, 8, 12))
    assert reminder.status is FollowupReminderStatus.UNFOLLOWED
    assert reminder.label == "尚未跟进"
    assert reminder.suggested_followup_date is None


def test_archive_acquisition_date_controls_reminder_eligibility() -> None:
    before_cutoff = calculate_customer_followup_reminder(
        date(2026, 8, 11),
        date(2026, 8, 10),
        "已报价",
        today=date(2026, 8, 12),
    )
    missing_date = calculate_customer_followup_reminder(
        None,
        None,
        "已报价",
        today=date(2026, 8, 12),
    )

    assert not is_followup_reminder_applicable(date(2026, 8, 11))
    assert not is_followup_reminder_applicable(None)
    assert before_cutoff.status is FollowupReminderStatus.NOT_APPLICABLE
    assert before_cutoff.label == "不适用"
    assert before_cutoff.suggested_followup_date is None
    assert missing_date.status is FollowupReminderStatus.NOT_APPLICABLE
    assert missing_date.label == "不适用"


def test_cutoff_date_is_eligible_and_missing_followup_is_actionable() -> None:
    reminder = calculate_customer_followup_reminder(
        date(2026, 8, 12),
        None,
        "已报价",
        today=date(2026, 8, 12),
    )

    assert is_followup_reminder_applicable(date(2026, 8, 12))
    assert reminder.status is FollowupReminderStatus.UNFOLLOWED
    assert reminder.label == "尚未跟进"


def test_today_uses_asia_shanghai_not_utc_calendar_day() -> None:
    # 18:30 UTC is the following calendar day in China.
    assert shanghai_today(datetime(2026, 8, 12, 18, 30, tzinfo=timezone.utc)) == date(2026, 8, 13)


def test_legacy_manual_stages_normalize_without_changing_cold_customer() -> None:
    assert normalize_manual_followup_stage("新开发未回复") == "新客户未回复"
    assert normalize_manual_followup_stage("新开发已回复") == "沟通中"
    assert normalize_manual_followup_stage("已采购样品") == "已成交样品"
    assert normalize_manual_followup_stage("冷客户") == "冷客户"
    reminder = calculate_followup_reminder(
        date(2026, 8, 10), "新开发未回复", today=date(2026, 8, 12)
    )
    assert reminder.suggested_followup_date == date(2026, 8, 12)


def test_automatic_cold_customer_is_strictly_more_than_thirty_days() -> None:
    today = date(2026, 8, 12)
    assert calculate_automatic_stage_judgement(date(2026, 7, 12), "沟通中", today=today) == COLD_CUSTOMER_STAGE
    assert calculate_automatic_stage_judgement(date(2026, 7, 13), "沟通中", today=today) == "沟通中"
    assert calculate_automatic_stage_judgement(None, "已报价", today=today) == "已报价"


def test_customer_schema_normalizes_known_legacy_stages_and_rejects_cold_customer() -> None:
    created = CustomerCreate(company_name="Stage compatibility", followup_stage="新开发未回复")
    updated = CustomerUpdate(followup_stage="已采购样品")

    assert created.followup_stage == "新客户未回复"
    assert updated.followup_stage == "已成交样品"
    with pytest.raises(ValidationError):
        CustomerUpdate(followup_stage="冷客户")


def test_customer_read_schema_preserves_unknown_historical_stage() -> None:
    payload = CustomerRead.model_validate(
        {
            "id": 42,
            "company_name": "Historical Stage Company",
            "customer_score": 0,
            "level": "C",
            "status": "Lead",
            "sales_stage": "Lead",
            "followup_stage": "已发目录",
            "created_at": datetime(2026, 8, 13),
            "updated_at": datetime(2026, 8, 13),
        }
    )

    assert payload.followup_stage == "已发目录"


def test_unknown_historical_stage_does_not_break_reminder_calculation() -> None:
    reminder = calculate_followup_reminder(
        date(2026, 8, 10), "已发目录", today=date(2026, 8, 13)
    )

    assert reminder.status is FollowupReminderStatus.STAGE_UNSET
