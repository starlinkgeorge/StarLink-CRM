import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, String, Table, Text
from sqlalchemy.ext.hybrid import hybrid_property
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


class CustomerFollowUpReminderStatus(str, enum.Enum):
    """Computed state of the customer's currently scheduled follow-up."""

    NONE = "None"
    SCHEDULED = "Scheduled"
    TODAY = "Today"
    OVERDUE = "Overdue"


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
    # Customer-archive fields follow the user's source workbook.  Existing
    # CRM fields remain in place so commercial-record foreign keys and legacy
    # API consumers continue to work without data loss.
    customer_acquired_at: Mapped[Optional[date]] = mapped_column(Date, index=True)
    position: Mapped[Optional[str]] = mapped_column(String(120))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    customer_type: Mapped[Optional[str]] = mapped_column(String(80))
    source: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    source_platform: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    original_inquiry: Mapped[Optional[str]] = mapped_column(Text)
    interested_product: Mapped[Optional[str]] = mapped_column(String(500))
    customer_level_value: Mapped[Optional[int]] = mapped_column(Integer)
    customer_size: Mapped[Optional[int]] = mapped_column(Integer)
    customer_total_score: Mapped[Optional[int]] = mapped_column(Integer)
    followup_stage: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    # The persisted value is preserved for archive compatibility. The public
    # hybrid property below overlays the live cold-customer judgement whenever
    # a new customer reaches its acquisition-date + 15-day boundary.
    automatic_stage_judgement_value: Mapped[Optional[str]] = mapped_column(
        "automatic_stage_judgement", String(120)
    )
    latest_followup_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    # Persisted for filtering and future reporting.  Read paths still derive
    # the effective value from the acquisition date and stage, so no cron is
    # required for a customer to become cold at the fifteen-day boundary.
    is_cold_customer_value: Mapped[bool] = mapped_column(
        "is_cold_customer", Boolean, nullable=False, server_default="false", default=False, index=True
    )
    response_status: Mapped[Optional[str]] = mapped_column(String(80))
    followup_requirement: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    # Import-only identity: hidden from the public API, immutable external
    # data such as an Excel row can be re-run without creating a new customer.
    archive_import_key: Mapped[Optional[str]] = mapped_column(String(160), unique=True)
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
    # These are denormalized from the latest follow-up.  They make reminder
    # dashboards inexpensive while the original follow-up history remains the
    # source of truth.
    next_followup_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    last_followup_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    owner: Mapped[Optional["User"]] = relationship(back_populates="owned_customers")
    category: Mapped[Optional["CustomerCategory"]] = relationship(back_populates="customers")
    score_history: Mapped[list["CustomerScoreHistory"]] = relationship(
        back_populates="customer",
        cascade="save-update, merge",
        order_by="(CustomerScoreHistory.created_at.desc(), CustomerScoreHistory.id.desc())",
    )
    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="customer", cascade="save-update, merge"
    )
    tags: Mapped[list["Tag"]] = relationship(secondary=CustomerTag, back_populates="customers")
    followups: Mapped[list["FollowUp"]] = relationship(
        back_populates="customer",
        cascade="save-update, merge",
        order_by="(FollowUp.followup_date.desc(), FollowUp.created_at.desc(), FollowUp.id.desc())",
    )
    quotations: Mapped[list["Quotation"]] = relationship(back_populates="customer")

    @hybrid_property
    def automatic_stage_judgement(self) -> Optional[str]:
        from app.services.customer_followup_stage_service import (
            calculate_automatic_stage_judgement,
        )

        return calculate_automatic_stage_judgement(
            self.latest_followup_date,
            self.automatic_stage_judgement_value,
        )

    @automatic_stage_judgement.setter
    def automatic_stage_judgement(self, value: Optional[str]) -> None:
        self.automatic_stage_judgement_value = value

    @automatic_stage_judgement.expression
    def automatic_stage_judgement(cls):
        return cls.automatic_stage_judgement_value

    @property
    def is_cold_customer(self) -> bool:
        """Return the live cold-customer state for every read path."""
        return self.effective_is_cold_customer

    @is_cold_customer.setter
    def is_cold_customer(self, value: bool) -> None:
        # Keep the persisted flag useful for reporting/indexing, while the
        # public state remains calendar-correct without requiring a cron job.
        self.is_cold_customer_value = bool(value)

    @property
    def followup_reminder_status(self) -> CustomerFollowUpReminderStatus:
        if self.next_followup_date is None:
            return CustomerFollowUpReminderStatus.NONE
        from app.services.followup_reminder_service import shanghai_today

        today = shanghai_today()
        if self.next_followup_date < today:
            return CustomerFollowUpReminderStatus.OVERDUE
        if self.next_followup_date == today:
            return CustomerFollowUpReminderStatus.TODAY
        return CustomerFollowUpReminderStatus.SCHEDULED

    @property
    def suggested_followup_date(self) -> Optional[date]:
        """V1 cadence-derived date, calculated from the customer archive fields."""
        # A function-local import prevents the model/service import graph from
        # becoming circular during SQLAlchemy model registration.
        from app.services.followup_reminder_service import calculate_customer_followup_reminder

        return calculate_customer_followup_reminder(
            self.customer_acquired_at,
            self.effective_latest_followup_date,
            self.followup_stage,
            is_cold_customer=self.effective_is_cold_customer,
        ).suggested_followup_date

    @property
    def effective_latest_followup_date(self) -> Optional[date]:
        """Prefer a real FollowUp date when that history is loaded."""
        if "followups" in self.__dict__:
            dates = [followup.followup_date for followup in self.followups if followup.followup_date]
            if dates:
                return max(dates)
        return self.latest_followup_date

    @property
    def effective_is_cold_customer(self) -> bool:
        from app.services.followup_reminder_service import is_customer_cold

        return is_customer_cold(self.customer_acquired_at, self.followup_stage)

    @property
    def calculated_followup_reminder_status(self) -> str:
        """Live V1 status; unlike legacy next_followup_date it is never stored."""
        from app.services.followup_reminder_service import calculate_customer_followup_reminder

        return calculate_customer_followup_reminder(
            self.customer_acquired_at,
            self.effective_latest_followup_date,
            self.followup_stage,
            is_cold_customer=self.effective_is_cold_customer,
        ).status.value

    @property
    def calculated_followup_reminder_label(self) -> str:
        from app.services.followup_reminder_service import calculate_customer_followup_reminder

        return calculate_customer_followup_reminder(
            self.customer_acquired_at,
            self.effective_latest_followup_date,
            self.followup_stage,
            is_cold_customer=self.effective_is_cold_customer,
        ).label


class Contact(CreatedAtMixin, Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        # Contacts are customer-history records.  They must not disappear if
        # somebody attempts to delete the parent customer outside the API.
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
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
