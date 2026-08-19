from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.order import OrderPaymentStatus, OrderProductionStatus, OrderShippingStatus

class OrderFields(BaseModel):
    order_no: str = Field(min_length=1, max_length=80)
    order_date: date
    currency: str = Field(min_length=3, max_length=3)
    order_amount: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    payment_status: OrderPaymentStatus = OrderPaymentStatus.UNPAID
    production_status: OrderProductionStatus = OrderProductionStatus.NOT_STARTED
    shipping_status: OrderShippingStatus = OrderShippingStatus.PENDING_SHIPMENT
    expected_delivery_date: date | None = None
    shipped_at: date | None = None
    notes: str | None = None
    rmb_received_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    purchase_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    freight_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    @field_validator("currency")
    @classmethod
    def upper_currency(cls, value: str) -> str: return value.strip().upper()

class OrderCreate(OrderFields):
    customer_id: int = Field(gt=0)
    opportunity_id: int | None = Field(default=None, gt=0)
    quotation_id: int | None = Field(default=None, gt=0)
    owner_id: int | None = Field(default=None, gt=0)

class OrderUpdate(BaseModel):
    order_no: str | None = Field(default=None, min_length=1, max_length=80)
    order_date: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    order_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    payment_status: OrderPaymentStatus | None = None
    production_status: OrderProductionStatus | None = None
    shipping_status: OrderShippingStatus | None = None
    expected_delivery_date: date | None = None
    shipped_at: date | None = None
    notes: str | None = None
    rmb_received_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    purchase_cost: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    freight_cost: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value is not None else value

class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; order_no: str; customer_id: int; opportunity_id: int | None; quotation_id: int | None
    order_date: date; currency: str; order_amount: Decimal; owner_id: int | None; created_by_id: int
    payment_status: OrderPaymentStatus; production_status: OrderProductionStatus; shipping_status: OrderShippingStatus
    expected_delivery_date: date | None; shipped_at: date | None; notes: str | None
    rmb_received_amount: Decimal; purchase_cost: Decimal; freight_cost: Decimal
    profit: Decimal; profit_margin: Decimal | None; realized_exchange_rate: Decimal | None
    customer_company: str; owner_name: str | None; created_at: datetime; updated_at: datetime

class OrderPage(BaseModel):
    items: list[OrderRead]; total: int; limit: int; offset: int


class WonOrderBackfillCandidate(BaseModel):
    """One historical Won opportunity considered by the Admin-only backfill tool."""

    opportunity_id: int
    opportunity_name: str
    customer_id: int
    customer_company: str
    quotation_id: int | None = None
    quotation_number: str | None = None
    order_date: date | None = None
    order_date_source: str | None = None
    reason: str | None = None


class WonOrderBackfillPreview(BaseModel):
    total_won: int
    already_ordered: int
    eligible_auto_build: int
    requires_date_confirmation: int
    unbuildable: int
    candidates: list[WonOrderBackfillCandidate]


class WonOrderBackfillRequest(BaseModel):
    """A date explicitly confirmed by Admin for records without Won history."""

    fallback_order_date: date | None = None


class WonOrderBackfillResult(BaseModel):
    created: int
    already_ordered: int
    requires_date_confirmation: int
    unbuildable: int
    created_orders: list[OrderRead]
    skipped: list[WonOrderBackfillCandidate]
