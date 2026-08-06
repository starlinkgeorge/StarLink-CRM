from pydantic import BaseModel


class DashboardStats(BaseModel):
    customer_count: int
    followup_count: int
