import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FollowUpType(str, enum.Enum):
    EMAIL = "Email"
    WHATSAPP = "WhatsApp"
    ALIBABA = "Alibaba"
    PHONE = "Phone"
    MEETING = "Meeting"


class FollowUp(Base):
    __tablename__ = "followups"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type: Mapped[FollowUpType] = mapped_column(
        Enum(
            FollowUpType,
            name="followup_type",
            native_enum=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    followup_date: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    next_followup_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    customer: Mapped["Customer"] = relationship(back_populates="followups")
    opportunity: Mapped[Optional["Opportunity"]] = relationship(back_populates="followups")
    user: Mapped["User"] = relationship(back_populates="followups")
    attachments: Mapped[list["FollowUpAttachment"]] = relationship(
        back_populates="followup",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(FollowUpAttachment.created_at.asc(), FollowUpAttachment.id.asc())",
    )


class FollowUpAttachment(Base):
    __tablename__ = "followup_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    followup_id: Mapped[int] = mapped_column(
        ForeignKey("followups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    followup: Mapped[FollowUp] = relationship(back_populates="attachments")
