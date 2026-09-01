from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models.opportunity import OpportunityReminderStatus, OpportunitySalesStage


class PipelineItem(BaseModel):
    status: str
    count: int


class UpcomingFollowUp(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    type: str
    content: str
    next_followup_date: date


class FollowUpReminder(UpcomingFollowUp):
    reminder_status: Literal["today", "overdue"]


class OpportunityAmountItem(BaseModel):
    currency: str
    amount: Decimal


class OpportunityPipelineItem(BaseModel):
    sales_stage: OpportunitySalesStage
    count: int


class OpportunityReminder(BaseModel):
    id: int
    name: str
    customer_id: int
    customer_name: str
    reminder_status: OpportunityReminderStatus
    quote_followup_due_date: date | None = None
    last_activity_at: datetime


class DashboardStats(BaseModel):
    customer_count: int
    followup_count: int
    new_customers_today: int
    due_followups: int
    today_followup_count: int
    overdue_followup_count: int
    pending_followup_customer_count: int
    week_followup_count: int
    today_due_customer_count: int
    overdue_customer_count: int
    week_followup_task_count: int
    pipeline: list[PipelineItem]
    upcoming_followups: list[UpcomingFollowUp]
    today_followups: list[FollowUpReminder]
    overdue_followups: list[FollowUpReminder]
    opportunity_count: int
    active_opportunity_count: int
    won_opportunity_count: int
    lost_opportunity_count: int
    opportunity_amounts: list[OpportunityAmountItem]
    opportunity_total_amounts: list[OpportunityAmountItem]
    opportunity_pipeline: list[OpportunityPipelineItem]
    quote_followup_overdue_count: int
    inactive_opportunity_count: int
    opportunity_reminders: list[OpportunityReminder]
    followup_reminder_overdue_count: int
    followup_reminder_today_count: int
    followup_reminder_upcoming_count: int
    followup_reminder_unfollowed_count: int


class DashboardTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    due_date: date
    priority: Literal["high", "medium", "low"] = "medium"
    customer_id: int | None = Field(default=None, gt=0)


class DashboardTaskRead(BaseModel):
    id: int
    title: str
    due_date: date
    priority: Literal["high", "medium", "low"]
    status: Literal["pending", "completed"]
    customer_id: int | None
    customer_name: str | None
    created_by_id: int
    created_at: datetime
    completed_at: datetime | None
