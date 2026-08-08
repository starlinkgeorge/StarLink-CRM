from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.lead import OpportunitySalesStage, OpportunityStage
from app.schemas.customer import CustomerRead
from app.schemas.followup import FollowUpRead
from app.schemas.product import OpportunityProductRead


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
    source_lead_id: int | None
    owner_id: int | None
    name: str
    interested_product: str | None
    inquiry_content: str | None
    amount: Decimal | None
    currency: str
    expected_close_date: date | None
    stage: OpportunityStage
    sales_stage: OpportunitySalesStage
    probability: int
    next_action: str | None
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


class OpportunityDetail(OpportunityListItem):
    customer: CustomerRead
    stage_history: list[OpportunityStageHistoryRead]
    sales_stage_history: list[OpportunitySalesStageHistoryRead]
    followups: list[FollowUpRead]
    products: list[OpportunityProductRead]


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
