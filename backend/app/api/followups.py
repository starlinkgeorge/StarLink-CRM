from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.api.dependencies import get_current_user
from app.models.user import User
from app.schemas.followup import FollowUpCreate, FollowUpRead
from app.services import access_service, customer_service, followup_service
from app.services.errors import ForbiddenError, NotFoundError

router = APIRouter(prefix="/followups", tags=["followups"])


@router.post("", response_model=FollowUpRead, status_code=status.HTTP_201_CREATED)
def create_followup(
    payload: FollowUpCreate, session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> FollowUpRead:
    try:
        customer = customer_service.get_customer(session, payload.customer_id)
        access_service.ensure_customer_manage_access(current_user, customer)
        if current_user.role.value == "Sales" and payload.user_id != current_user.id:
            raise ForbiddenError("Sales users may only create their own follow-up records.")
        return followup_service.create_followup(session, payload)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error


@router.get("", response_model=list[FollowUpRead])
def list_customer_followups(
    customer_id: int = Query(gt=0), session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[FollowUpRead]:
    try:
        customer = customer_service.get_customer(session, customer_id)
        access_service.ensure_customer_read_access(current_user, customer)
        return followup_service.list_customer_followups(session, customer_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
