import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class OrderPaymentStatus(str, enum.Enum):
    UNPAID = "Unpaid"
    DEPOSIT_RECEIVED = "Deposit Received"
    PAID_IN_FULL = "Paid in Full"


class OrderProductionStatus(str, enum.Enum):
    NOT_STARTED = "Not Started"
    IN_PRODUCTION = "In Production"
    COMPLETED = "Completed"


class OrderShippingStatus(str, enum.Enum):
    PENDING_SHIPMENT = "Pending Shipment"
    SHIPPED = "Shipped"
    DELIVERED = "Delivered"


def _enum(enum_type, name: str):
    return Enum(enum_type, name=name, native_enum=True, values_callable=lambda cls: [item.value for item in cls])


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id", ondelete="SET NULL"), index=True)
    quotation_id: Mapped[int | None] = mapped_column(ForeignKey("quotations.id", ondelete="SET NULL"), unique=True, index=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    order_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    payment_status: Mapped[OrderPaymentStatus] = mapped_column(_enum(OrderPaymentStatus, "order_payment_status"), nullable=False, default=OrderPaymentStatus.UNPAID)
    production_status: Mapped[OrderProductionStatus] = mapped_column(_enum(OrderProductionStatus, "order_production_status"), nullable=False, default=OrderProductionStatus.NOT_STARTED)
    shipping_status: Mapped[OrderShippingStatus] = mapped_column(_enum(OrderShippingStatus, "order_shipping_status"), nullable=False, default=OrderShippingStatus.PENDING_SHIPMENT)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    shipped_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    rmb_received_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    freight_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0, server_default="0")
