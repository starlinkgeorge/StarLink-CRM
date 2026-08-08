from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.models.customer import CustomerStatus
from app.models.followup import FollowUpType


class CustomerActivityRead(BaseModel):
    event_id: str
    event_type: Literal["customer_created", "followup", "status_changed"]
    occurred_at: datetime
    user_id: int | None = None
    content: str | None = None
    followup_type: FollowUpType | None = None
    followup_date: date | None = None
    next_followup_date: date | None = None
    opportunity_id: int | None = None
    old_status: CustomerStatus | None = None
    new_status: CustomerStatus | None = None
