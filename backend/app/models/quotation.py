import enum
from decimal import Decimal
from typing import Optional

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin


class QuotationStatus(str, enum.Enum):
    DRAFT = "Draft"
    SENT = "Sent"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    EXPIRED = "Expired"


class Quotation(TimestampMixin, Base):
    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    opportunity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[QuotationStatus] = mapped_column(
        Enum(
            QuotationStatus,
            name="quotation_status",
            native_enum=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
        default=QuotationStatus.DRAFT,
        index=True,
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    customer: Mapped["Customer"] = relationship(back_populates="quotations")
    opportunity: Mapped[Optional["Opportunity"]] = relationship(back_populates="quotations")
    versions: Mapped[list["QuotationVersion"]] = relationship(
        back_populates="quotation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="QuotationVersion.version_no.desc()",
    )


class QuotationVersion(CreatedAtMixin, Base):
    __tablename__ = "quotation_versions"
    __table_args__ = (
        UniqueConstraint("quotation_id", "version_no", name="uq_quotation_version_no"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    payment_term: Mapped[str] = mapped_column(String(500), nullable=False)
    delivery_time: Mapped[str] = mapped_column(String(500), nullable=False)
    validity_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    pdf_url: Mapped[Optional[str]] = mapped_column(String(1000))

    quotation: Mapped[Quotation] = relationship(back_populates="versions")
    items: Mapped[list["QuotationItem"]] = relationship(
        back_populates="version",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="QuotationItem.id",
    )


class QuotationItem(Base):
    __tablename__ = "quotation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_version_id: Mapped[int] = mapped_column(
        ForeignKey("quotation_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    sku_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    picture_snapshot: Mapped[Optional[str]] = mapped_column(String(1000))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    version: Mapped[QuotationVersion] = relationship(back_populates="items")
    product: Mapped[Optional["Product"]] = relationship(back_populates="quotation_items")
