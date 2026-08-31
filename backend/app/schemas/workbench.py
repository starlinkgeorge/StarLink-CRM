from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    due_date: date
    priority: Literal["high", "medium", "low"] = "medium"
    customer_id: int | None = Field(default=None, gt=0)


class TaskRead(BaseModel):
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


class DailyWorkNoteUpdate(BaseModel):
    content: str = Field(default="", max_length=10000)


class DailyWorkNoteRead(BaseModel):
    work_date: date
    content: str
    updated_at: datetime


class WorkbenchMetricRead(BaseModel):
    metric_group: str
    metric_key: str
    completed_value: Decimal
    target_value: Decimal


class WorkbenchMetricUpdate(BaseModel):
    metric_group: str = Field(min_length=1, max_length=40)
    metric_key: str = Field(min_length=1, max_length=80)
    completed_value: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    target_value: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class WorkbenchToday(BaseModel):
    today: date
    tasks: list[TaskRead]
    daily_note: DailyWorkNoteRead | None
    metrics: list[WorkbenchMetricRead]
    period: Literal["today", "week", "month"]
