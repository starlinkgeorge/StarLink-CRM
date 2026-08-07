from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.customer import CustomerStatus
from app.models.lead import LeadStatus
from app.schemas.contact import ContactRead
from app.schemas.customer import CustomerRead


class LeadFields(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    contact_name: str = Field(min_length=1, max_length=120)
    country: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=320)
    phone: Optional[str] = Field(default=None, max_length=50)
    whatsapp: Optional[str] = Field(default=None, max_length=50)
    source: Optional[str] = Field(default=None, max_length=80)
    inquiry_content: Optional[str] = Field(default=None, max_length=10000)
    interested_product: Optional[str] = Field(default=None, max_length=500)
    status: LeadStatus = LeadStatus.NEW


class LeadCreate(LeadFields):
    @field_validator("status")
    @classmethod
    def status_must_not_be_converted(cls, value: LeadStatus) -> LeadStatus:
        if value is LeadStatus.CONVERTED:
            raise ValueError("A Lead can only become Converted through the conversion endpoint.")
        return value


class LeadRead(LeadFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: UUID
    created_at: datetime
    updated_at: datetime


class LeadDetail(LeadRead):
    converted_customer_id: int | None = None
    converted_opportunity_id: int | None = None


class LeadPage(BaseModel):
    items: list[LeadRead]
    total: int
    limit: int
    offset: int


class OpportunityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: UUID
    customer_id: int
    source_lead_id: int | None
    owner_id: int | None
    name: str
    interested_product: str | None
    stage: CustomerStatus
    created_at: datetime
    updated_at: datetime


class LeadConversionRead(BaseModel):
    lead: LeadRead
    customer: CustomerRead
    contact: ContactRead
    opportunity: OpportunityRead
