from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services.customer_followup_stage_service import (
    calculate_automatic_stage_judgement,
    normalize_manual_followup_stage,
)
from app.services.followup_reminder_service import (
    FollowupReminderStatus,
    calculate_customer_followup_reminder,
    cold_customer_effective_date,
    is_customer_cold,
    shanghai_today,
)


def _reminder(acquired: date, latest: date | None, stage: str, today: date):
    return calculate_customer_followup_reminder(acquired, latest, stage, today=today)


def test_new_customer_first_reminder_is_acquisition_plus_three_days() -> None:
    reminder = _reminder(date(2026, 8, 20), None, "新客户未回复", date(2026, 8, 20))
    assert reminder.suggested_followup_date == date(2026, 8, 23)


def test_customer_without_stage_or_followup_is_still_actionable() -> None:
    reminder = calculate_customer_followup_reminder(
        date(2026, 8, 20), None, None, today=date(2026, 8, 20)
    )
    assert reminder.status is FollowupReminderStatus.UNFOLLOWED
    assert reminder.label == "尚未跟进"
    assert reminder.suggested_followup_date == date(2026, 8, 23)


def test_new_customer_followup_resets_to_three_days() -> None:
    reminder = _reminder(date(2026, 8, 20), date(2026, 8, 23), "新客户未回复", date(2026, 8, 23))
    assert reminder.suggested_followup_date == date(2026, 8, 26)


def test_talking_customer_uses_three_day_cadence() -> None:
    reminder = _reminder(date(2026, 8, 20), date(2026, 8, 23), "沟通中", date(2026, 8, 23))
    assert reminder.suggested_followup_date == date(2026, 8, 26)


def test_quoted_customer_uses_one_day_cadence() -> None:
    reminder = _reminder(date(2026, 8, 20), date(2026, 8, 23), "已报价", date(2026, 8, 23))
    assert reminder.suggested_followup_date == date(2026, 8, 24)
    assert reminder.label == "明天跟进"


def test_new_customer_becomes_cold_at_acquisition_plus_fifteen_days() -> None:
    acquired = date(2026, 8, 1)
    assert cold_customer_effective_date(acquired) == date(2026, 8, 16)
    assert not is_customer_cold(acquired, "新客户未回复", today=date(2026, 8, 15))
    assert is_customer_cold(acquired, "新客户未回复", today=date(2026, 8, 16))


def test_followup_history_does_not_restart_cold_clock() -> None:
    assert is_customer_cold(date(2026, 8, 1), "新客户未回复", today=date(2026, 8, 16))
    reminder = _reminder(date(2026, 8, 1), date(2026, 8, 13), "新客户未回复", date(2026, 8, 16))
    assert reminder.suggested_followup_date == date(2026, 9, 12)


def test_cold_customer_followup_uses_thirty_days() -> None:
    reminder = _reminder(date(2026, 8, 1), date(2026, 8, 16), "新客户未回复", date(2026, 8, 16))
    assert reminder.suggested_followup_date == date(2026, 9, 15)


def test_cold_customer_becomes_active_when_stage_changes_to_talking() -> None:
    acquired, latest, today = date(2026, 8, 1), date(2026, 8, 16), date(2026, 8, 16)
    assert is_customer_cold(acquired, "新客户未回复", today=today)
    assert not is_customer_cold(acquired, "沟通中", today=today)
    assert _reminder(acquired, latest, "沟通中", today).suggested_followup_date == date(2026, 8, 19)


def test_cold_customer_becomes_active_when_stage_changes_to_quoted() -> None:
    acquired, latest, today = date(2026, 8, 1), date(2026, 8, 16), date(2026, 8, 16)
    assert not is_customer_cold(acquired, "已报价", today=today)
    assert _reminder(acquired, latest, "已报价", today).suggested_followup_date == date(2026, 8, 17)


def test_closed_stage_clears_cold_and_does_not_use_cold_cadence() -> None:
    acquired, latest, today = date(2026, 8, 1), date(2026, 8, 16), date(2026, 8, 16)
    assert not is_customer_cold(acquired, "已成交", today=today)
    assert _reminder(acquired, latest, "已成交", today).suggested_followup_date == date(2026, 8, 23)


def test_missing_acquisition_date_and_unknown_stage_are_safe() -> None:
    assert not is_customer_cold(None, "新客户未回复", today=date(2026, 8, 16))
    assert _reminder(None, date(2026, 8, 16), "新客户未回复", date(2026, 8, 16)).status is FollowupReminderStatus.NOT_APPLICABLE
    assert _reminder(date(2026, 8, 1), date(2026, 8, 16), "已发目录", date(2026, 8, 16)).status is FollowupReminderStatus.STAGE_UNSET


def test_asia_shanghai_clock_and_historical_schema_compatibility() -> None:
    assert shanghai_today(datetime(2026, 8, 12, 18, 30, tzinfo=timezone.utc)) == date(2026, 8, 13)
    assert normalize_manual_followup_stage("新开发未回复") == "新客户未回复"
    created = CustomerCreate(company_name="Stage", followup_stage="新开发未回复")
    updated = CustomerUpdate(followup_stage="已采购样品")
    assert created.followup_stage == "新客户未回复"
    assert updated.followup_stage == "已成交样品"
    with pytest.raises(ValidationError):
        CustomerUpdate(followup_stage="冷客户")
    historical = CustomerRead.model_validate({
        "id": 42, "company_name": "Historical", "customer_score": 0,
        "level": "C", "status": "Lead", "sales_stage": "Lead",
        "followup_stage": "已发目录", "created_at": datetime(2026, 8, 13),
        "updated_at": datetime(2026, 8, 13),
    })
    assert historical.followup_stage == "已发目录"
    assert calculate_automatic_stage_judgement(date(2026, 7, 1), "历史判断", today=date(2026, 8, 16)) == "历史判断"
