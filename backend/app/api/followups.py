from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.followup import FollowUpCreate, FollowUpRead
from app.services import followup_service
from app.services.errors import NotFoundError

router = APIRouter(prefix="/followups", tags=["followups"])


@router.post("", response_model=FollowUpRead, status_code=status.HTTP_201_CREATED)
def create_followup(payload: FollowUpCreate, session: Session = Depends(get_db_session)) -> FollowUpRead:
    try:
        return followup_service.create_followup(session, payload)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("", response_model=list[FollowUpRead])
def list_customer_followups(
    customer_id: int = Query(gt=0), session: Session = Depends(get_db_session)
) -> list[FollowUpRead]:
    try:
        return followup_service.list_customer_followups(session, customer_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
