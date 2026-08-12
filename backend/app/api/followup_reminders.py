from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.followup_reminder import CustomerFollowupReminderPage
from app.services.followup_reminder_service import (
    FollowupReminderStatus,
    list_customer_followup_reminders,
)


router = APIRouter(prefix="/followup-reminders", tags=["followup reminders"])


@router.get("", response_model=CustomerFollowupReminderPage)
def list_followup_reminders(
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> CustomerFollowupReminderPage:
    parsed_status: FollowupReminderStatus | None = None
    if status_filter:
        try:
            parsed_status = FollowupReminderStatus(status_filter.strip())
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Invalid follow-up reminder status.") from error
    summary, items = list_customer_followup_reminders(
        session, current_user, status_filter=parsed_status
    )
    return CustomerFollowupReminderPage(summary=summary, items=items)
