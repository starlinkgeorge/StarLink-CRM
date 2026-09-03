from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
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
    forwarded_from_id: Mapped[int | None] = mapped_column(ForeignKey("email_messages.id", ondelete="SET NULL"), index=True)
    mail_folder_id: Mapped[int | None] = mapped_column(ForeignKey("mail_folders.id", ondelete="SET NULL"), index=True)
    folder: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    sync_key: Mapped[str] = mapped_column(String(512), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(512), index=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False, server_default="")
    from_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    from_name: Mapped[str | None] = mapped_column(String(500))
    to_emails: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    cc_emails: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    to_display: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    cc_display: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    body_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    html_body: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    bcc_emails: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    thread_key: Mapped[str | None] = mapped_column(String(512), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", index=True)
    is_starred: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), index=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), index=True)
    tracking_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    tracking_token: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    first_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    open_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    customer: Mapped[Optional["Customer"]] = relationship()
    mail_folder: Mapped[Optional["MailFolder"]] = relationship(back_populates="messages")
    attachments: Mapped[list["EmailAttachment"]] = relationship(back_populates="message", cascade="all, delete-orphan", order_by="EmailAttachment.id")
    open_events: Mapped[list["EmailOpenEvent"]] = relationship(back_populates="message", cascade="all, delete-orphan", order_by="EmailOpenEvent.id")


class EmailAttachment(CreatedAtMixin, Base):
    __tablename__ = "email_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_message_id: Mapped[int] = mapped_column(ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    message: Mapped[EmailMessage] = relationship(back_populates="attachments")


class MailFolder(CreatedAtMixin, Base):
    """A CRM filing label which never changes a message's IMAP Inbox/Sent role."""

    __tablename__ = "mail_folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    bound_addresses: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)

    customer: Mapped[Optional["Customer"]] = relationship()
    messages: Mapped[list[EmailMessage]] = relationship(back_populates="mail_folder")


class EmailOpenEvent(Base):
    """A minimal audit row for an external tracking-pixel request.

    Deliberately no IP address, user agent, or recipient identifier is stored.
    """

    __tablename__ = "email_open_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_message_id: Mapped[int] = mapped_column(
        ForeignKey("email_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    message: Mapped[EmailMessage] = relationship(back_populates="open_events")


class MailboxSyncState(Base):
    """Persistent IMAP cursor for one server mailbox."""

    __tablename__ = "mailbox_sync_states"
    __table_args__ = (UniqueConstraint("mailbox", name="uq_mailbox_sync_states_mailbox"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    mailbox: Mapped[str] = mapped_column(String(512), nullable=False)
    uid_validity: Mapped[str | None] = mapped_column(String(128))
    last_synced_uid: Mapped[int | None] = mapped_column(BigInteger)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
