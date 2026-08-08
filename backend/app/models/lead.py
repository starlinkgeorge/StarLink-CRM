import enum
from datetime import date, datetime
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


class LeadStatus(str, enum.Enum):
    NEW = "New"
    CONTACTED = "Contacted"
    QUALIFIED = "Qualified"
    CONVERTED = "Converted"
    LOST = "Lost"


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
    )

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
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    expected_close_date: Mapped[Optional[date]] = mapped_column(Date)
    inquiry_content: Mapped[Optional[str]] = mapped_column(Text)
    sales_stage: Mapped[OpportunitySalesStage] = mapped_column(
        String(40), nullable=False, default=OpportunitySalesStage.NEW_LEAD, index=True
    )
    probability: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    next_action: Mapped[Optional[str]] = mapped_column(String(500))
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

    source_lead: Mapped[Optional[Lead]] = relationship(back_populates="opportunity")
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
    product_items: Mapped[list["OpportunityProduct"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan", passive_deletes=True
    )
    quotations: Mapped[list["Quotation"]] = relationship(back_populates="opportunity")


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
