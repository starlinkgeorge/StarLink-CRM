from datetime import date, datetime, timezone

from app.services.followup_reminder_service import (
    FollowupReminderStatus,
    calculate_followup_reminder,
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


def test_today_uses_asia_shanghai_not_utc_calendar_day() -> None:
    # 18:30 UTC is the following calendar day in China.
    assert shanghai_today(datetime(2026, 8, 12, 18, 30, tzinfo=timezone.utc)) == date(2026, 8, 13)
