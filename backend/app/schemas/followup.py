from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.followup import FollowUpType


class FollowUpCreate(BaseModel):
    customer_id: int = Field(gt=0)
    user_id: int = Field(gt=0)
    type: FollowUpType
    content: str = Field(min_length=1)
    next_followup_date: Optional[date] = None


class FollowUpRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    user_id: int
    type: FollowUpType
    content: str
    next_followup_date: Optional[date]
    created_at: datetime
