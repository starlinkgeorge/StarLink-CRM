from datetime import date

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


class DashboardStats(BaseModel):
    customer_count: int
    followup_count: int
    new_customers_today: int
    due_followups: int
    pipeline: list[PipelineItem]
    upcoming_followups: list[UpcomingFollowUp]
