from pydantic import BaseModel

from app.schemas.customer import CustomerDetail, CustomerScoreHistoryRead
from app.schemas.customer_activity import CustomerActivityRead
from app.schemas.opportunity import OpportunityListItem
from app.schemas.quotation import QuotationListItem


class CustomerCenter(CustomerDetail):
    """A permission-scoped, read-only view of every customer-facing CRM record."""

    opportunities: list[OpportunityListItem]
    quotations: list[QuotationListItem]
    activities: list[CustomerActivityRead]
    score_history: list[CustomerScoreHistoryRead]
