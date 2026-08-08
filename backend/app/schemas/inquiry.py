from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.inquiry import InquiryStatus
from app.schemas.contact import ContactRead
from app.schemas.customer import CustomerRead
from app.schemas.opportunity import OpportunityRead


class InquiryFields(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    contact_name: str = Field(min_length=1, max_length=120)
    country: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=320)
    phone: Optional[str] = Field(default=None, max_length=50)
    whatsapp: Optional[str] = Field(default=None, max_length=50)
    source: str = Field(default="Alibaba", min_length=1, max_length=80)
    source_platform: str = Field(default="Alibaba", min_length=1, max_length=80)
    interested_product: Optional[str] = Field(default=None, max_length=500)
    inquiry_content: str = Field(min_length=1, max_length=10000)
    status: InquiryStatus = InquiryStatus.NEW

    @field_validator(
        "company_name",
        "contact_name",
        "source",
        "source_platform",
        "inquiry_content",
    )
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be blank.")
        return cleaned


class InquiryCreate(InquiryFields):
    pass


class InquiryUpdate(BaseModel):
    company_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    contact_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    country: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=320)
    phone: Optional[str] = Field(default=None, max_length=50)
    whatsapp: Optional[str] = Field(default=None, max_length=50)
    source: Optional[str] = Field(default=None, min_length=1, max_length=80)
    source_platform: Optional[str] = Field(default=None, min_length=1, max_length=80)
    interested_product: Optional[str] = Field(default=None, max_length=500)
    inquiry_content: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    status: Optional[InquiryStatus] = None

    @field_validator(
        "company_name",
        "contact_name",
        "source",
        "source_platform",
        "inquiry_content",
    )
    @classmethod
    def trim_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be blank.")
        return cleaned


class InquiryRead(InquiryFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: UUID
    customer_id: Optional[int] = None
    converted_opportunity_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class InquiryPage(BaseModel):
    items: list[InquiryRead]
    total: int
    limit: int
    offset: int


class InquiryConversionRead(BaseModel):
    inquiry: InquiryRead
    customer: CustomerRead
    contact: ContactRead
    opportunity: OpportunityRead
