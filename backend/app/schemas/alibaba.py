from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.lead import LeadRead


class AlibabaInquiryCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    contact_name: str = Field(min_length=1, max_length=120)
    country: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    whatsapp: str | None = Field(default=None, max_length=50)
    inquiry_content: str | None = Field(default=None, max_length=10000)
    interested_product: str | None = Field(default=None, max_length=500)
    source: str | None = Field(default=None, max_length=80)

    @field_validator("company_name", "contact_name")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be blank.")
        return cleaned

    @field_validator(
        "country",
        "email",
        "phone",
        "whatsapp",
        "inquiry_content",
        "interested_product",
        "source",
    )
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class AlibabaInquiryResult(BaseModel):
    lead_id: int
    lead_public_id: UUID
    created: bool
    lead: LeadRead


class AlibabaIntegrationStatus(BaseModel):
    provider: Literal["Alibaba"] = "Alibaba"
    connected: bool
    mode: Literal["simulation"] = "simulation"
