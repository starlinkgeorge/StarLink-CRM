from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class AnnualSalesTargetUpdate(BaseModel):
    target_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)


class AnnualSalesTargetRead(BaseModel):
    target_year: int
    currency: str
    target_amount: Decimal


class OtherSalesAmountInput(BaseModel):
    sale_date: date
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    note: str = Field(default="", max_length=1000)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("note")
    @classmethod
    def strip_note(cls, value: str) -> str:
        return value.strip()


class OtherSalesAmountRead(OtherSalesAmountInput):
    id: int
    created_at: datetime


class SalesCurrencyBreakdown(BaseModel):
    currency: str
    crm_order_amount: Decimal
    manual_amount: Decimal
    actual_amount: Decimal


class SalesTargetPeriod(BaseModel):
    key: str
    label: str
    actual_amount: Decimal
    target_amount: Decimal
    completion_percent: Decimal | None
    remaining_amount: Decimal


class SalesTargetAnalysis(BaseModel):
    crm_order_amount: Decimal
    manual_amount: Decimal
    actual_total_amount: Decimal
    completion_percent: Decimal | None
    time_progress_percent: Decimal
    pace_percent: Decimal | None
    pace_label: str
    remaining_amount: Decimal
    monthly_required_amount: Decimal


class SalesTargetProgress(BaseModel):
    year: int
    currency: str
    annual_target: AnnualSalesTargetRead | None
    periods: list[SalesTargetPeriod]
    annual_analysis: SalesTargetAnalysis
    currency_breakdown: list[SalesCurrencyBreakdown]
