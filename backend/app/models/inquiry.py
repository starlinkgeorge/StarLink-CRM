import enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class InquiryStatus(str, enum.Enum):
    NEW = "New"
    PROCESSING = "Processing"
    CONVERTED = "Converted"
    CLOSED = "Closed"


class Inquiry(TimestampMixin, Base):
    """An external marketplace inquiry before it is converted into CRM records."""

    __tablename__ = "inquiries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('New', 'Processing', 'Converted', 'Closed')",
            name="ck_inquiries_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), default=uuid4, nullable=False, unique=True
    )
    customer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )
    converted_opportunity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"), unique=True
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    contact_name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    whatsapp: Mapped[Optional[str]] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="Alibaba", index=True)
    source_platform: Mapped[str] = mapped_column(
        String(80), nullable=False, default="Alibaba", index=True
    )
    interested_product: Mapped[Optional[str]] = mapped_column(String(500))
    inquiry_content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[InquiryStatus] = mapped_column(
        String(30), nullable=False, default=InquiryStatus.NEW, index=True
    )
