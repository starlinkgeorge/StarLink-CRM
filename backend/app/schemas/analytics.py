"""Read models for the business-analytics API."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel


class AnalyticsPeriod(str, Enum):
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
    CUSTOM = "custom"


class AnalyticsDateRange(BaseModel):
    start_date: date
    end_date: date
    comparison_start_date: date
    comparison_end_date: date
    label: str


class AnalyticsCurrencyAmount(BaseModel):
    currency: str
    amount: Decimal


class AnalyticsKpis(BaseModel):
    new_customer_count: int
    new_customer_change_percent: float | None = None
    quotation_count: int
    quotation_count_change_percent: float | None = None
    quotation_amounts: list[AnalyticsCurrencyAmount]
    previous_quotation_amounts: list[AnalyticsCurrencyAmount]
    won_opportunity_count: int
    won_opportunity_change_percent: float | None = None
    won_amounts: list[AnalyticsCurrencyAmount]
    previous_won_amounts: list[AnalyticsCurrencyAmount]
    quoted_opportunity_count: int
    quote_to_win_rate: float | None = None


class AnalyticsTrendPoint(BaseModel):
    bucket: str
    new_customer_count: int
    quotation_count: int
    won_opportunity_count: int


class AnalyticsBreakdownItem(BaseModel):
    value: str
    count: int
    percentage: float


class AnalyticsQuotedProductItem(BaseModel):
    sku: str
    product_name: str
    quotation_count: int
    total_quantity: Decimal
    quotation_amounts: list[AnalyticsCurrencyAmount]


class AnalyticsFunnelItem(BaseModel):
    stage: str
    count: int


class AnalyticsFollowupSummary(BaseModel):
    created_followup_count: int
    overdue_count: int
    today_count: int
    upcoming_count: int
    unfollowed_count: int


class BusinessAnalyticsOverview(BaseModel):
    period: AnalyticsPeriod
    date_range: AnalyticsDateRange
    kpis: AnalyticsKpis
    trend: list[AnalyticsTrendPoint]
    source_analysis: list[AnalyticsBreakdownItem]
    country_analysis: list[AnalyticsBreakdownItem]
    interested_product_analysis: list[AnalyticsBreakdownItem]
    customer_type_analysis: list[AnalyticsBreakdownItem]
    quoted_products: list[AnalyticsQuotedProductItem]
    sales_funnel: list[AnalyticsFunnelItem]
    followup_summary: AnalyticsFollowupSummary
