from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.followup import FollowUp
from app.models.user import User
from app.services.access_service import customer_scope


def get_dashboard_stats(session: Session, user: User) -> tuple[int, int]:
    filters = []
    scope = customer_scope(user)
    if scope is not None:
        filters.append(scope)
    customer_count = session.scalar(select(func.count()).select_from(Customer).where(*filters)) or 0
    followup_count = (
        session.scalar(
            select(func.count()).select_from(FollowUp).join(Customer).where(*filters)
        )
        or 0
    )
    return customer_count, followup_count
