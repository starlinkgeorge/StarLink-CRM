from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.customer import CustomerLevel, CustomerStatus
from app.schemas.contact import ContactRead
from app.schemas.followup import FollowUpRead


class CustomerFields(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    contact_name: Optional[str] = Field(default=None, max_length=120)
    country: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=320)
    phone: Optional[str] = Field(default=None, max_length=50)
    whatsapp: Optional[str] = Field(default=None, max_length=50)
    website: Optional[str] = Field(default=None, max_length=255)
    source: Optional[str] = Field(default=None, max_length=80)
    level: CustomerLevel = CustomerLevel.C
    status: CustomerStatus = CustomerStatus.LEAD
    owner_id: Optional[int] = Field(default=None, gt=0)


class CustomerCreate(CustomerFields):
    pass


class CustomerUpdate(BaseModel):
    company_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    contact_name: Optional[str] = Field(default=None, max_length=120)
    country: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=320)
    phone: Optional[str] = Field(default=None, max_length=50)
    whatsapp: Optional[str] = Field(default=None, max_length=50)
    website: Optional[str] = Field(default=None, max_length=255)
    source: Optional[str] = Field(default=None, max_length=80)
    level: Optional[CustomerLevel] = None
    status: Optional[CustomerStatus] = None
    owner_id: Optional[int] = Field(default=None, gt=0)


class CustomerRead(CustomerFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime


class CustomerDetail(CustomerRead):
    contacts: list[ContactRead]
    tags: list[TagRead]
    followups: list[FollowUpRead]


class CustomerPage(BaseModel):
    items: list[CustomerRead]
    total: int
    limit: int
    offset: int
