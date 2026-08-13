import enum
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class OpportunityStage(str, enum.Enum):
    LEAD = "Lead"
    QUALIFIED = "Qualified"
    PROPOSAL = "Proposal"
    NEGOTIATION = "Negotiation"
    WON = "Won"
    LOST = "Lost"


class OpportunitySalesStage(str, enum.Enum):
    """The customer-facing sales process, kept separate from the V3 legacy stage."""

    NEW_LEAD = "New Lead"
    CONTACTED = "Contacted"
    REQUIREMENT_CONFIRMED = "Requirement Confirmed"
    QUOTATION_SENT = "Quotation Sent"
    NEGOTIATION = "Negotiation"
    WON = "Won"
    LOST = "Lost"


class OpportunityDealStage(str, enum.Enum):
    """V9's concise, user-facing sales process for foreign-trade opportunities."""

    NEW_INQUIRY = "New Inquiry"
    CONTACTED = "Contacted"
    QUOTED = "Quoted"
    NEGOTIATING = "Negotiating"
    WON = "Won"
    LOST = "Lost"


class OpportunityReminderStatus(str, enum.Enum):
    """Computed reminder state for an open opportunity."""

    NONE = "None"
    QUOTE_FOLLOWUP_DUE = "Quote Follow-up Due"
    INACTIVE = "Inactive"


QUOTE_FOLLOWUP_DAYS = 3
INACTIVITY_DAYS = 14


class Opportunity(TimestampMixin, Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint(
            "probability >= 0 AND probability <= 100",
            name="ck_opportunities_probability_range",
        ),
        CheckConstraint(
            "sales_stage IN ('New Lead', 'Contacted', 'Requirement Confirmed', "
            "'Quotation Sent', 'Negotiation', 'Won', 'Lost')",
            name="ck_opportunities_sales_stage",
        ),
        CheckConstraint(
            "deal_stage IN ('New Inquiry', 'Contacted', 'Quoted', 'Negotiating', 'Won', 'Lost')",
            name="ck_opportunities_deal_stage",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), default=uuid4, nullable=False, unique=True
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    interested_product: Mapped[Optional[str]] = mapped_column(String(500))
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    expected_close_date: Mapped[Optional[date]] = mapped_column(Date)
    inquiry_content: Mapped[Optional[str]] = mapped_column(Text)
    sales_stage: Mapped[OpportunitySalesStage] = mapped_column(
        String(40), nullable=False, default=OpportunitySalesStage.NEW_LEAD, index=True
    )
    deal_stage: Mapped[OpportunityDealStage] = mapped_column(
        String(40), nullable=False, default=OpportunityDealStage.NEW_INQUIRY, index=True
    )
    probability: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    next_action: Mapped[Optional[str]] = mapped_column(String(500))
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    last_followup_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    quotation_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    quote_followup_due_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    stage: Mapped[OpportunityStage] = mapped_column(
        Enum(
            OpportunityStage,
            name="opportunity_stage",
            native_enum=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
        default=OpportunityStage.LEAD,
        index=True,
    )

    customer: Mapped["Customer"] = relationship()
    owner: Mapped[Optional["User"]] = relationship()
    followups: Mapped[list["FollowUp"]] = relationship(back_populates="opportunity")
    stage_history: Mapped[list["OpportunityStageHistory"]] = relationship(
        back_populates="opportunity",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(OpportunityStageHistory.created_at.desc(), OpportunityStageHistory.id.desc())",
    )
    sales_stage_history: Mapped[list["OpportunitySalesStageHistory"]] = relationship(
        back_populates="opportunity",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=(
            "OpportunitySalesStageHistory.created_at.desc(), "
            "OpportunitySalesStageHistory.id.desc()"
        ),
    )
    deal_stage_history: Mapped[list["OpportunityDealStageHistory"]] = relationship(
        back_populates="opportunity",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=(
            "OpportunityDealStageHistory.created_at.desc(), "
            "OpportunityDealStageHistory.id.desc()"
        ),
    )
    product_items: Mapped[list["OpportunityProduct"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan", passive_deletes=True
    )
    quotations: Mapped[list["Quotation"]] = relationship(back_populates="opportunity")

    @property
    def reminder_status(self) -> OpportunityReminderStatus:
        if self.deal_stage in (
            OpportunityDealStage.WON,
            OpportunityDealStage.LOST,
            OpportunityDealStage.WON.value,
            OpportunityDealStage.LOST.value,
        ):
            return OpportunityReminderStatus.NONE
        today = date.today()
        has_followed_up_after_quote = (
            self.quotation_sent_at is not None
            and self.last_followup_at is not None
            and self.last_followup_at >= self.quotation_sent_at
        )
        if (
            self.quote_followup_due_date is not None
            and self.quote_followup_due_date <= today
            and not has_followed_up_after_quote
        ):
            return OpportunityReminderStatus.QUOTE_FOLLOWUP_DUE
        if self.last_activity_at is not None and self.last_activity_at.date() <= (
            today - timedelta(days=INACTIVITY_DAYS)
        ):
            return OpportunityReminderStatus.INACTIVE
        return OpportunityReminderStatus.NONE


class OpportunityStageHistory(Base):
    __tablename__ = "opportunity_stage_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    old_stage: Mapped[Optional[OpportunityStage]] = mapped_column(
        Enum(
            OpportunityStage,
            name="opportunity_stage",
            native_enum=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        )
    )
    new_stage: Mapped[OpportunityStage] = mapped_column(
        Enum(
            OpportunityStage,
            name="opportunity_stage",
            native_enum=True,
            values_callable=lambda enum_class: [member.value for member in enum_class],
        ),
        nullable=False,
    )
    changed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    opportunity: Mapped[Opportunity] = relationship(back_populates="stage_history")


class OpportunitySalesStageHistory(Base):
    __tablename__ = "opportunity_sales_stage_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    old_sales_stage: Mapped[Optional[OpportunitySalesStage]] = mapped_column(String(40))
    new_sales_stage: Mapped[OpportunitySalesStage] = mapped_column(String(40), nullable=False)
    changed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    opportunity: Mapped[Opportunity] = relationship(back_populates="sales_stage_history")


class OpportunityDealStageHistory(Base):
    """Immutable V9 business-stage history, independent from V3/V7 compatibility data."""

    __tablename__ = "opportunity_deal_stage_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    opportunity_id: Mapped[int] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    old_deal_stage: Mapped[Optional[OpportunityDealStage]] = mapped_column(String(40))
    new_deal_stage: Mapped[OpportunityDealStage] = mapped_column(String(40), nullable=False)
    changed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    opportunity: Mapped[Opportunity] = relationship(back_populates="deal_stage_history")
