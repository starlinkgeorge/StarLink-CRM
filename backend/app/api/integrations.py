from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.alibaba import (
    AlibabaInquiryCreate,
    AlibabaInquiryResult,
    AlibabaIntegrationStatus,
)
from app.services import alibaba_integration_service
from app.services.errors import ForbiddenError

router = APIRouter(prefix="/integrations/alibaba", tags=["integrations"])


@router.get("/status", response_model=AlibabaIntegrationStatus)
def get_alibaba_status(
    current_user: User = Depends(get_current_user),
) -> AlibabaIntegrationStatus:
    del current_user
    return AlibabaIntegrationStatus(connected=False)


@router.post("/inquiries", response_model=AlibabaInquiryResult)
def receive_alibaba_inquiry(
    payload: AlibabaInquiryCreate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> AlibabaInquiryResult:
    try:
        customer, created = alibaba_integration_service.receive_inquiry(
            session, payload, current_user
        )
        return AlibabaInquiryResult(
            customer_id=customer.id,
            created=created,
            customer=customer,
        )
    except ForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
