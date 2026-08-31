"""Persistent, non-secret operational settings for the CRM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.system_setting import SystemSetting
from app.models.user import User, UserRole
from app.schemas.system_settings import (
    CompanyProfileSettings,
    FollowupRulesSettings,
    QuotationOrderDefaultsSettings,
    SystemSettingsRead,
    SystemSettingsUpdate,
)
from app.services.errors import ForbiddenError


SYSTEM_SETTINGS_KEY = "system_settings_v1"


@dataclass(frozen=True)
class FollowupRules:
    rule_start_date: date
    new_customer_first_followup_days: int
    new_customer_unanswered_reminder_days: int
    communicating_reminder_days: int
    quoted_reminder_days: int
    cold_customer_after_days: int
    cold_customer_reminder_days: int


def _defaults() -> SystemSettingsRead:
    runtime = get_settings()
    return SystemSettingsRead(
        followup_rules=FollowupRulesSettings(),
        company_profile=CompanyProfileSettings(
            company_name=runtime["company_name"],
            english_name="",
            logo_url="",
            address="",
            phone=runtime["company_whatsapp"],
            email=runtime["company_email"],
            website=runtime["company_website"],
        ),
        quotation_order_defaults=QuotationOrderDefaultsSettings(),
    )


def get_system_settings(session: Session) -> SystemSettingsRead:
    row = session.get(SystemSetting, SYSTEM_SETTINGS_KEY)
    if row is None:
        return _defaults()
    try:
        return SystemSettingsRead.model_validate_json(row.value)
    except (ValueError, TypeError):
        # Old/malformed optional configuration must never cause CRM reads to fail.
        return _defaults()


def update_system_settings(
    session: Session, payload: SystemSettingsUpdate, current_user: User
) -> SystemSettingsRead:
    if current_user.role is not UserRole.ADMIN:
        raise ForbiddenError("Only Admin accounts can update system settings.")
    serialized = payload.model_dump_json()
    row = session.get(SystemSetting, SYSTEM_SETTINGS_KEY)
    if row is None:
        row = SystemSetting(key=SYSTEM_SETTINGS_KEY, value=serialized)
        session.add(row)
    else:
        row.value = serialized
    session.commit()
    return payload


def get_followup_rules(session: Session | None = None) -> FollowupRules:
    settings = get_system_settings(session) if session is not None else _defaults()
    return FollowupRules(**settings.followup_rules.model_dump())


def get_quotation_order_defaults(session: Session) -> QuotationOrderDefaultsSettings:
    return get_system_settings(session).quotation_order_defaults
