from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.system_settings import SystemSettingsRead, SystemSettingsUpdate
from app.services import system_settings_service
from app.services.errors import ForbiddenError


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SystemSettingsRead)
def get_settings(
    session: Session = Depends(get_db_session), current_user: User = Depends(get_current_user)
) -> SystemSettingsRead:
    return system_settings_service.get_system_settings(session)


@router.put("", response_model=SystemSettingsRead)
def update_settings(
    payload: SystemSettingsUpdate,
    session: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> SystemSettingsRead:
    try:
        return system_settings_service.update_system_settings(session, payload, current_user)
    except ForbiddenError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
