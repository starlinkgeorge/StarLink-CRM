from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


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


class DashboardStats(BaseModel):
    customer_count: int
    followup_count: int
    new_customers_today: int
    due_followups: int
    today_followup_count: int
    overdue_followup_count: int
    pipeline: list[PipelineItem]
    upcoming_followups: list[UpcomingFollowUp]
    today_followups: list[FollowUpReminder]
    overdue_followups: list[FollowUpReminder]
    opportunity_count: int
    active_opportunity_count: int
    won_opportunity_count: int
    lost_opportunity_count: int
    opportunity_amounts: list[OpportunityAmountItem]
