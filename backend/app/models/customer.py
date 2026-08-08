import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAtMixin, TimestampMixin


class CustomerLevel(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"


class CustomerStatus(str, enum.Enum):
    LEAD = "Lead"
    CONTACTED = "Contacted"
    QUOTATION = "Quotation"
    NEGOTIATION = "Negotiation"
    WON = "Won"
    LOST = "Lost"


CustomerTag = Table(
    "customer_tags",
    Base.metadata,
    Column("customer_id", ForeignKey("customers.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contact_name: Mapped[Optional[str]] = mapped_column(String(120))
    country: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    whatsapp: Mapped[Optional[str]] = mapped_column(String(50))
    website: Mapped[Optional[str]] = mapped_column(String(255))
    customer_type: Mapped[Optional[str]] = mapped_column(String(80))
    source: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    interested_product: Mapped[Optional[str]] = mapped_column(String(500))
    level: Mapped[CustomerLevel] = mapped_column(
        Enum(
            CustomerLevel,
            name="customer_level",
            native_enum=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
        default=CustomerLevel.C,
    )
    status: Mapped[CustomerStatus] = mapped_column(
        Enum(
            CustomerStatus,
            name="customer_status",
            native_enum=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
        default=CustomerStatus.LEAD,
        index=True,
    )
    sales_stage: Mapped[CustomerStatus] = mapped_column(
        Enum(
            CustomerStatus,
            name="customer_status",
            native_enum=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
        default=CustomerStatus.LEAD,
    )
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customer_categories.id", ondelete="SET NULL"), index=True
    )
    customer_score: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    score_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    owner: Mapped[Optional["User"]] = relationship(back_populates="owned_customers")
    category: Mapped[Optional["CustomerCategory"]] = relationship(back_populates="customers")
    score_history: Mapped[list["CustomerScoreHistory"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(CustomerScoreHistory.created_at.desc(), CustomerScoreHistory.id.desc())",
    )
    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan", passive_deletes=True
    )
    tags: Mapped[list["Tag"]] = relationship(secondary=CustomerTag, back_populates="customers")
    followups: Mapped[list["FollowUp"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(FollowUp.followup_date.desc(), FollowUp.created_at.desc(), FollowUp.id.desc())",
    )
    quotations: Mapped[list["Quotation"]] = relationship(back_populates="customer")


class Contact(CreatedAtMixin, Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[Optional[str]] = mapped_column(String(120))
    email: Mapped[Optional[str]] = mapped_column(String(320))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    whatsapp: Mapped[Optional[str]] = mapped_column(String(50))

    customer: Mapped["Customer"] = relationship(back_populates="contacts")


class Tag(CreatedAtMixin, Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    color: Mapped[str] = mapped_column(String(20), nullable=False, server_default="#2563eb")
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default="true")

    customers: Mapped[list["Customer"]] = relationship(secondary=CustomerTag, back_populates="tags")
