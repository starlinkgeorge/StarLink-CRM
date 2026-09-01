"""SQLAlchemy models exposed to Alembic and application code."""

from app.models.customer import (
    Contact,
    Customer,
    CustomerFollowUpReminderStatus,
    CustomerLevel,
    CustomerStatus,
    CustomerTag,
    Tag,
)
from app.models.customer_classification import CustomerCategory, CustomerScoreHistory
from app.models.customer_activity import CustomerStatusHistory
from app.models.auth import RefreshToken
from app.models.followup import FollowUp, FollowUpAttachment, FollowUpType
from app.models.inquiry import Inquiry, InquiryStatus
from app.models.opportunity import (
    Opportunity,
    OpportunityDealStage,
    OpportunityDealStageHistory,
    OpportunityReminderStatus,
    OpportunitySalesStage,
    OpportunitySalesStageHistory,
    OpportunityStage,
    OpportunityStageHistory,
)
from app.models.product import Product, ProductCategory, ProductImage, OpportunityProduct
from app.models.quotation import Quotation, QuotationItem, QuotationStatus, QuotationVersion
from app.models.order import Order, OrderPaymentStatus, OrderProductionStatus, OrderShippingStatus
from app.models.system_setting import SystemSetting
from app.models.task import Task
from app.models.sales_goal import AnnualSalesTarget, OtherSalesAmount
from app.models.user import User, UserRole

__all__ = [
    "Contact", "Customer", "CustomerFollowUpReminderStatus", "CustomerLevel", "CustomerStatus", "CustomerStatusHistory",
    "CustomerTag", "CustomerCategory", "CustomerScoreHistory", "FollowUp",
    "FollowUpAttachment", "FollowUpType", "Inquiry", "InquiryStatus", "Opportunity",
    "OpportunityDealStage", "OpportunityDealStageHistory", "OpportunityReminderStatus", "OpportunitySalesStage",
    "OpportunitySalesStageHistory", "OpportunityStage",
    "OpportunityStageHistory", "OpportunityProduct", "Product", "ProductCategory",
    "ProductImage", "RefreshToken", "Tag", "User", "UserRole",
    "Quotation", "QuotationItem", "QuotationStatus", "QuotationVersion",
    "Order", "OrderPaymentStatus", "OrderProductionStatus", "OrderShippingStatus",
    "SystemSetting",
    "Task",
    "AnnualSalesTarget", "OtherSalesAmount",
]
