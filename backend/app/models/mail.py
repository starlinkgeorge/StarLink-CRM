from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import CreatedAtMixin


class EmailMessage(CreatedAtMixin, Base):
    __tablename__ = "email_messages"
    __table_args__ = (UniqueConstraint("sync_key", name="uq_email_messages_sync_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    in_reply_to_id: Mapped[int | None] = mapped_column(ForeignKey("email_messages.id", ondelete="SET NULL"), index=True)
    folder: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    sync_key: Mapped[str] = mapped_column(String(512), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(512), index=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    from_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    to_emails: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    cc_emails: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    body_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    customer: Mapped[Optional["Customer"]] = relationship()
    attachments: Mapped[list["EmailAttachment"]] = relationship(back_populates="message", cascade="all, delete-orphan", order_by="EmailAttachment.id")


class EmailAttachment(CreatedAtMixin, Base):
    __tablename__ = "email_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_message_id: Mapped[int] = mapped_column(ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    message: Mapped[EmailMessage] = relationship(back_populates="attachments")
