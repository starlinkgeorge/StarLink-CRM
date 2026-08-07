"""SQLAlchemy models exposed to Alembic and application code."""

from app.models.customer import Contact, Customer, CustomerLevel, CustomerStatus, CustomerTag, Tag
from app.models.customer_classification import CustomerCategory, CustomerScoreHistory
from app.models.customer_activity import CustomerStatusHistory
from app.models.auth import RefreshToken
from app.models.followup import FollowUp, FollowUpType
from app.models.lead import Lead, LeadStatus, Opportunity, OpportunityStage, OpportunityStageHistory
from app.models.product import Product, ProductCategory, ProductImage, OpportunityProduct
from app.models.quotation import Quotation, QuotationItem, QuotationStatus, QuotationVersion
from app.models.user import User, UserRole

__all__ = [
    "Contact", "Customer", "CustomerLevel", "CustomerStatus", "CustomerStatusHistory",
    "CustomerTag", "CustomerCategory", "CustomerScoreHistory", "FollowUp",
    "FollowUpType", "Lead", "LeadStatus", "Opportunity", "OpportunityStage",
    "OpportunityStageHistory", "OpportunityProduct", "Product", "ProductCategory",
    "ProductImage", "RefreshToken", "Tag", "User", "UserRole",
    "Quotation", "QuotationItem", "QuotationStatus", "QuotationVersion",
]
