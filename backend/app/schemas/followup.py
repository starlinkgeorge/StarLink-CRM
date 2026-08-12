from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.followup import FollowUpType
from app.services.followup_reminder_service import shanghai_today


class FollowUpCreate(BaseModel):
    customer_id: int = Field(gt=0)
    user_id: int | None = Field(default=None, gt=0)
    opportunity_id: int | None = Field(default=None, gt=0)
    type: FollowUpType
    followup_date: date = Field(default_factory=shanghai_today)
    content: str = Field(min_length=1, max_length=5000)
    next_followup_date: Optional[date] = None


class FollowUpUpdate(BaseModel):
    opportunity_id: int | None = Field(default=None, gt=0)
    type: FollowUpType | None = None
    followup_date: date | None = None
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    next_followup_date: date | None = None


class FollowUpAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    content_type: str | None
    size_bytes: int
    created_at: datetime


class FollowUpRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    opportunity_id: int | None
    user_id: int
    type: FollowUpType
    followup_date: date
    content: str
    next_followup_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    attachments: list[FollowUpAttachmentRead] = Field(default_factory=list)
