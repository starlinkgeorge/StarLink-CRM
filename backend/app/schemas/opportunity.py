from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.opportunity import (
    OpportunityDealStage,
    OpportunityReminderStatus,
    OpportunitySalesStage,
    OpportunityStage,
)
from app.schemas.contact import ContactRead
from app.schemas.customer import CustomerRead
from app.schemas.followup import FollowUpRead
from app.schemas.product import OpportunityProductRead
from app.schemas.quotation import QuotationListItem


class OpportunityFields(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    interested_product: str | None = Field(default=None, max_length=500)
    inquiry_content: str | None = Field(default=None, max_length=10000)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    expected_close_date: date | None = None
    # stage remains accepted for V3 API compatibility. sales_stage is the V7 pipeline.
    stage: OpportunityStage | None = None
    sales_stage: OpportunitySalesStage | None = None
    deal_stage: OpportunityDealStage | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    next_action: str | None = Field(default=None, max_length=500)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class OpportunityCreate(OpportunityFields):
    customer_id: int = Field(gt=0)
    owner_id: int | None = Field(default=None, gt=0)


class OpportunityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    interested_product: str | None = Field(default=None, max_length=500)
    inquiry_content: str | None = Field(default=None, max_length=10000)
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    expected_close_date: date | None = None
    stage: OpportunityStage | None = None
    sales_stage: OpportunitySalesStage | None = None
    deal_stage: OpportunityDealStage | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    next_action: str | None = Field(default=None, max_length=500)
    owner_id: int | None = Field(default=None, gt=0)

    @field_validator("currency")
    @classmethod
    def normalize_optional_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else value


class OpportunityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: UUID
    customer_id: int
    owner_id: int | None
    name: str
    interested_product: str | None
    inquiry_content: str | None
    amount: Decimal | None
    currency: str
    expected_close_date: date | None
    stage: OpportunityStage
    sales_stage: OpportunitySalesStage
    deal_stage: OpportunityDealStage
    probability: int
    next_action: str | None
    last_activity_at: datetime
    last_followup_at: datetime | None
    quotation_sent_at: datetime | None
    quote_followup_due_date: date | None
    reminder_status: OpportunityReminderStatus
    created_at: datetime
    updated_at: datetime


class OpportunityListItem(OpportunityRead):
    customer_company: str
    owner_name: str | None


class OpportunityStageHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    opportunity_id: int
    old_stage: OpportunityStage | None
    new_stage: OpportunityStage
    changed_by_id: int | None
    created_at: datetime


class OpportunitySalesStageHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    opportunity_id: int
    old_sales_stage: OpportunitySalesStage | None
    new_sales_stage: OpportunitySalesStage
    changed_by_id: int | None
    created_at: datetime


class OpportunityDealStageHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    opportunity_id: int
    old_deal_stage: OpportunityDealStage | None
    new_deal_stage: OpportunityDealStage
    changed_by_id: int | None
    created_at: datetime


class OpportunityDetail(OpportunityListItem):
    customer: CustomerRead
    contacts: list[ContactRead]
    stage_history: list[OpportunityStageHistoryRead]
    sales_stage_history: list[OpportunitySalesStageHistoryRead]
    deal_stage_history: list[OpportunityDealStageHistoryRead]
    followups: list[FollowUpRead]
    products: list[OpportunityProductRead]
    quotations: list[QuotationListItem]


class OpportunityPage(BaseModel):
    items: list[OpportunityListItem]
    total: int
    limit: int
    offset: int


class OpportunityPipelineColumn(BaseModel):
    sales_stage: OpportunitySalesStage
    count: int
    opportunities: list[OpportunityListItem]


class OpportunityPipeline(BaseModel):
    columns: list[OpportunityPipelineColumn]


class OpportunityDealPipelineColumn(BaseModel):
    deal_stage: OpportunityDealStage
    count: int
    opportunities: list[OpportunityListItem]


class OpportunityDealPipeline(BaseModel):
    columns: list[OpportunityDealPipelineColumn]
