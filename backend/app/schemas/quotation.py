from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.quotation import QuotationStatus


class QuotationItemInput(BaseModel):
    product_id: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class QuotationTerms(BaseModel):
    currency: str = Field(default="USD", min_length=3, max_length=3)
    payment_term: str = Field(default="30% deposit, balance before shipment", min_length=1, max_length=500)
    delivery_time: str = Field(default="30-45 days after deposit", min_length=1, max_length=500)
    validity_days: int = Field(default=30, ge=1, le=365)
    shipping_cost: Decimal = Field(default=0, ge=0, max_digits=14, decimal_places=2)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class QuotationCreate(QuotationTerms):
    opportunity_id: int = Field(gt=0)
    items: list[QuotationItemInput] | None = Field(default=None, min_length=1, max_length=100)


class QuotationUpdate(BaseModel):
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    payment_term: str | None = Field(default=None, min_length=1, max_length=500)
    delivery_time: str | None = Field(default=None, min_length=1, max_length=500)
    validity_days: int | None = Field(default=None, ge=1, le=365)
    shipping_cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    items: list[QuotationItemInput] | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_optional_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else None


class QuotationItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int | None
    sku_snapshot: str
    product_name_snapshot: str
    picture_snapshot: str | None
    unit_price: Decimal
    quantity: Decimal
    line_total: Decimal


class QuotationVersionSummary(BaseModel):
    id: int
    version_no: int
    currency: str
    total_amount: Decimal
    pdf_url: str | None
    created_at: datetime


class QuotationVersionRead(QuotationVersionSummary):
    payment_term: str
    delivery_time: str
    validity_days: int
    shipping_cost: Decimal
    subtotal: Decimal
    items: list[QuotationItemRead]


class QuotationListItem(BaseModel):
    id: int
    quotation_number: str
    customer_id: int
    customer_company: str
    opportunity_id: int | None
    opportunity_name: str | None
    status: QuotationStatus
    current_version: int
    currency: str
    total_amount: Decimal
    created_at: datetime
    updated_at: datetime


class CompanyContact(BaseModel):
    name: str
    website: str
    email: str
    whatsapp: str


class QuotationDetail(QuotationListItem):
    versions: list[QuotationVersionSummary]
    selected_version: QuotationVersionRead
    company_contact: CompanyContact


class QuotationPage(BaseModel):
    items: list[QuotationListItem]
    total: int
    limit: int
    offset: int
