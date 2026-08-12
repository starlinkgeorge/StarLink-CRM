from datetime import date

from pydantic import BaseModel


class FollowupReminderState(BaseModel):
    status: str
    label: str
    suggested_followup_date: date | None = None
    overdue_days: int | None = None
    days_until_due: int | None = None


class CustomerFollowupReminder(BaseModel):
    id: int
    customer_name: str | None = None
    company_name: str
    country: str | None = None
    customer_level_value: int | None = None
    customer_total_score: int | None = None
    followup_stage: str | None = None
    latest_followup_date: date | None = None
    suggested_followup_date: date | None = None
    followup_reminder: FollowupReminderState
    whatsapp: str | None = None
    email: str | None = None


class FollowupReminderSummary(BaseModel):
    overdue_count: int
    today_count: int
    upcoming_count: int
    unfollowed_count: int


class CustomerFollowupReminderPage(BaseModel):
    summary: FollowupReminderSummary
    items: list[CustomerFollowupReminder]
