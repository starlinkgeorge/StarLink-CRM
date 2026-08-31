from datetime import date

from pydantic import BaseModel, Field, field_validator


class FollowupRulesSettings(BaseModel):
    rule_start_date: date = date(2026, 8, 12)
    new_customer_first_followup_days: int = Field(default=3, ge=1, le=365)
    new_customer_unanswered_reminder_days: int = Field(default=3, ge=1, le=365)
    communicating_reminder_days: int = Field(default=3, ge=1, le=365)
    quoted_reminder_days: int = Field(default=1, ge=1, le=365)
    cold_customer_after_days: int = Field(default=15, ge=1, le=3650)
    cold_customer_reminder_days: int = Field(default=30, ge=1, le=3650)


class CompanyProfileSettings(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    english_name: str = Field(default="", max_length=255)
    logo_url: str = Field(default="", max_length=1000)
    address: str = Field(default="", max_length=1000)
    phone: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=320)
    website: str = Field(default="", max_length=255)

    @field_validator("company_name", "english_name", "logo_url", "address", "phone", "email", "website")
    @classmethod
    def strip_values(cls, value: str) -> str:
        return value.strip()


class QuotationOrderDefaultsSettings(BaseModel):
    default_currency: str = Field(default="USD", min_length=3, max_length=3)
    default_quotation_validity_days: int = Field(default=30, ge=1, le=365)
    default_payment_term: str = Field(default="30% deposit, balance before shipment", min_length=1, max_length=500)
    default_delivery_time: str = Field(default="30-45 days after deposit", min_length=1, max_length=500)

    @field_validator("default_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("default_payment_term", "default_delivery_time")
    @classmethod
    def strip_required_values(cls, value: str) -> str:
        return value.strip()


class SystemSettingsRead(BaseModel):
    followup_rules: FollowupRulesSettings
    company_profile: CompanyProfileSettings
    quotation_order_defaults: QuotationOrderDefaultsSettings


class SystemSettingsUpdate(SystemSettingsRead):
    pass
