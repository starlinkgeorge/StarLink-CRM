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
    customer_type: Optional[str] = Field(default=None, max_length=80)
    source: Optional[str] = Field(default=None, max_length=80)
    source_platform: Optional[str] = Field(default=None, max_length=80)
    original_inquiry: Optional[str] = Field(default=None, max_length=10000)
    interested_product: Optional[str] = Field(default=None, max_length=500)
    category_id: Optional[int] = Field(default=None, gt=0)
    customer_score: Optional[int] = Field(default=None, ge=0, le=100)
    level: CustomerLevel = CustomerLevel.C
    status: CustomerStatus = CustomerStatus.LEAD
    sales_stage: CustomerStatus = CustomerStatus.LEAD
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
    customer_type: Optional[str] = Field(default=None, max_length=80)
    source: Optional[str] = Field(default=None, max_length=80)
    source_platform: Optional[str] = Field(default=None, max_length=80)
    original_inquiry: Optional[str] = Field(default=None, max_length=10000)
    interested_product: Optional[str] = Field(default=None, max_length=500)
    category_id: Optional[int] = Field(default=None, gt=0)
    customer_score: Optional[int] = Field(default=None, ge=0, le=100)
    level: Optional[CustomerLevel] = None
    status: Optional[CustomerStatus] = None
    sales_stage: Optional[CustomerStatus] = None
    owner_id: Optional[int] = Field(default=None, gt=0)


class CustomerCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    color: str
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CustomerRead(CustomerFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_score: int
    score_updated_at: Optional[datetime] = None
    category: Optional["CustomerCategoryRead"] = None
    created_at: datetime
    updated_at: datetime


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    color: str
    is_active: bool
    created_at: datetime


class CustomerCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=255)
    color: str = Field(default="#2563eb", min_length=4, max_length=20)
    sort_order: int = Field(default=0, ge=0, le=100000)
    is_active: bool = True


class CustomerCategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=255)
    color: Optional[str] = Field(default=None, min_length=4, max_length=20)
    sort_order: Optional[int] = Field(default=None, ge=0, le=100000)
    is_active: Optional[bool] = None


class CustomerScoreUpdate(BaseModel):
    score: int = Field(ge=0, le=100)
    reason: Optional[str] = Field(default=None, max_length=500)


class CustomerScoreHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    old_score: Optional[int] = None
    new_score: int
    reason: Optional[str] = None
    changed_by_id: Optional[int] = None
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
