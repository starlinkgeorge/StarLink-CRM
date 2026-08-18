from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
        return value.strip().upper() or "USD"

    @field_validator("payment_term", mode="before")
    @classmethod
    def normalize_payment_term(cls, value: str) -> str:
        return value.strip() or "30% deposit, balance before shipment"

    @field_validator("delivery_time", mode="before")
    @classmethod
    def normalize_delivery_time(cls, value: str) -> str:
        return value.strip() or "30-45 days after deposit"

    @field_validator("shipping_cost", mode="before")
    @classmethod
    def normalize_shipping_cost(cls, value: Decimal | str) -> Decimal | str:
        return Decimal("0") if value is None or str(value).strip() == "" else value

    @field_validator("validity_days", mode="before")
    @classmethod
    def normalize_validity_days(cls, value: int | str) -> int | str:
        return 30 if value is None or str(value).strip() in {"", "0"} else value


class QuotationCreate(QuotationTerms):
    opportunity_id: int | None = Field(default=None, gt=0)
    customer_id: int | None = Field(default=None, gt=0)
    items: list[QuotationItemInput] | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_creation_context(self) -> "QuotationCreate":
        if self.opportunity_id is None and self.customer_id is None:
            raise ValueError("必须提供商机或客户以创建报价。")
        if self.opportunity_id is not None and self.customer_id is not None:
            raise ValueError("创建报价时只能提供商机或客户之一。")
        return self


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
        return value.strip().upper() or "USD" if value is not None else None

    @field_validator("payment_term", mode="before")
    @classmethod
    def normalize_optional_payment_term(cls, value: str | None) -> str | None:
        return value.strip() or "30% deposit, balance before shipment" if value is not None else None

    @field_validator("delivery_time", mode="before")
    @classmethod
    def normalize_optional_delivery_time(cls, value: str | None) -> str | None:
        return value.strip() or "30-45 days after deposit" if value is not None else None

    @field_validator("shipping_cost", mode="before")
    @classmethod
    def normalize_optional_shipping_cost(cls, value: Decimal | str | None) -> Decimal | str | None:
        return Decimal("0") if value is not None and str(value).strip() == "" else value

    @field_validator("validity_days", mode="before")
    @classmethod
    def normalize_optional_validity_days(cls, value: int | str | None) -> int | str | None:
        return 30 if value is not None and str(value).strip() in {"", "0"} else value


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
