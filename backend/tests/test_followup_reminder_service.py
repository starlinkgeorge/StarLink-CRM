from datetime import date, datetime, timezone

from app.services.followup_reminder_service import (
    FollowupReminderStatus,
    calculate_customer_followup_reminder,
    calculate_followup_reminder,
    is_followup_reminder_applicable,
    shanghai_today,
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
        date(2026, 8, 9), "新开发已回复", today=date(2026, 8, 12)
    ).label == "已逾期 2 天"
    assert calculate_followup_reminder(
        date(2026, 8, 11), "新开发已回复", today=date(2026, 8, 12)
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
