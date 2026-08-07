import enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.customer import CustomerStatus
from app.models.mixins import TimestampMixin


class LeadStatus(str, enum.Enum):
    NEW = "New"
    CONTACTED = "Contacted"
    QUALIFIED = "Qualified"
    CONVERTED = "Converted"
    LOST = "Lost"


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), default=uuid4, nullable=False, unique=True
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contact_name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(320), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    whatsapp: Mapped[Optional[str]] = mapped_column(String(50))
    source: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    inquiry_content: Mapped[Optional[str]] = mapped_column(Text)
    interested_product: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[LeadStatus] = mapped_column(
        Enum(
            LeadStatus,
            name="lead_status",
            native_enum=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
        default=LeadStatus.NEW,
        index=True,
    )

    opportunity: Mapped[Optional["Opportunity"]] = relationship(
        back_populates="source_lead", uselist=False
    )


class Opportunity(TimestampMixin, Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), default=uuid4, nullable=False, unique=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_lead_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("leads.id", ondelete="SET NULL"), unique=True
    )
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    interested_product: Mapped[Optional[str]] = mapped_column(String(500))
    stage: Mapped[CustomerStatus] = mapped_column(
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

    source_lead: Mapped[Optional[Lead]] = relationship(back_populates="opportunity")
    customer: Mapped["Customer"] = relationship()
    owner: Mapped[Optional["User"]] = relationship()
