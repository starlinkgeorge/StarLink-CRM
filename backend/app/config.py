from functools import lru_cache
from os import getenv


@lru_cache
def get_settings() -> dict[str, str]:
    """Return the minimal runtime configuration for the API foundation."""
    company_website = getenv("COMPANY_WEBSITE", "").strip()
    alibaba_store = getenv("COMPANY_ALIBABA_STORE", "").strip()
    # Keep older .env files working when both links were stored in one value.
    if "&" in company_website:
        legacy_links = [part.strip() for part in company_website.split("&") if part.strip()]
        if len(legacy_links) >= 2:
            alibaba_store = alibaba_store or legacy_links[0]
            company_website = legacy_links[-1]
    return {
        "environment": getenv("APP_ENV", "development"),
        "api_prefix": getenv("API_PREFIX", "/api/v1"),
        "database_url": getenv("DATABASE_URL", ""),
        "jwt_secret_key": getenv("JWT_SECRET_KEY", ""),
        "jwt_access_token_minutes": getenv("JWT_ACCESS_TOKEN_MINUTES", "15"),
        "jwt_refresh_token_days": getenv("JWT_REFRESH_TOKEN_DAYS", "14"),
        "cors_origins": getenv("CORS_ORIGINS", "http://localhost:5173"),
        "quotation_output_dir": getenv("QUOTATION_OUTPUT_DIR", "output/pdf"),
        "followup_attachment_dir": getenv(
            "FOLLOWUP_ATTACHMENT_DIR", "output/followup-attachments"
        ),
        "company_alibaba_store": alibaba_store,
        "company_website": company_website,
        "company_email": getenv("COMPANY_EMAIL", ""),
        "company_whatsapp": getenv("COMPANY_WHATSAPP", ""),
    }
