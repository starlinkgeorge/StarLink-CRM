from functools import lru_cache
from os import getenv


DEFAULT_COMPANY_NAME = "Dalian StarLink International Trade Co., Ltd."
DEFAULT_COMPANY_ALIBABA_STORE = "https://starlinkforkids.en.alibaba.com"
DEFAULT_COMPANY_WEBSITE = "https://dlstarlink.com"
DEFAULT_COMPANY_EMAIL = "starlink_george@foxmail.com"
DEFAULT_COMPANY_WHATSAPP = "+86 17640412406"


def _environment() -> str:
    return getenv("APP_ENV", "development").strip().lower() or "development"


@lru_cache
def get_settings() -> dict[str, str]:
    """Return runtime configuration without embedding deployment-specific URLs."""
    company_website = getenv("COMPANY_WEBSITE", "").strip()
    alibaba_store = getenv("COMPANY_ALIBABA_STORE", "").strip()
    # Keep older .env files working when both links were stored in one value.
    if "&" in company_website:
        legacy_links = [part.strip() for part in company_website.split("&") if part.strip()]
        if len(legacy_links) >= 2:
            alibaba_store = alibaba_store or legacy_links[0]
            company_website = legacy_links[-1]
    return {
        "environment": _environment(),
        "api_prefix": getenv("API_PREFIX", "/api/v1"),
        "database_url": getenv("DATABASE_URL", ""),
        "jwt_secret_key": getenv("JWT_SECRET_KEY", ""),
        "jwt_access_token_minutes": getenv("JWT_ACCESS_TOKEN_MINUTES", "15"),
        "jwt_refresh_token_days": getenv("JWT_REFRESH_TOKEN_DAYS", "14"),
        "cors_origins": getenv("CORS_ORIGINS", ""),
        "database_pool_mode": getenv("DATABASE_POOL_MODE", "queue").strip().lower(),
        "quotation_output_dir": getenv("QUOTATION_OUTPUT_DIR", "output/pdf"),
        "followup_attachment_dir": getenv(
            "FOLLOWUP_ATTACHMENT_DIR", "output/followup-attachments"
        ),
        "file_storage_backend": getenv("FILE_STORAGE_BACKEND", "local").strip().lower(),
        "blob_read_write_token": getenv("BLOB_READ_WRITE_TOKEN", ""),
        "product_image_base_url": getenv("PRODUCT_IMAGE_BASE_URL", "").strip().rstrip("/"),
        # Public business contact details have safe defaults so quotation exports
        # stay customer-ready when a deployment omits optional contact variables.
        # Deployments may still override any value through their environment.
        "company_name": getenv("COMPANY_NAME", DEFAULT_COMPANY_NAME).strip()
        or DEFAULT_COMPANY_NAME,
        "company_alibaba_store": alibaba_store or DEFAULT_COMPANY_ALIBABA_STORE,
        "company_website": company_website or DEFAULT_COMPANY_WEBSITE,
        "company_email": getenv("COMPANY_EMAIL", DEFAULT_COMPANY_EMAIL).strip()
        or DEFAULT_COMPANY_EMAIL,
        "company_whatsapp": getenv("COMPANY_WHATSAPP", DEFAULT_COMPANY_WHATSAPP).strip()
        or DEFAULT_COMPANY_WHATSAPP,
    }


def validate_production_settings() -> None:
    """Fail deployment startup early when required production secrets are absent."""
    settings = get_settings()
    if settings["environment"] != "production":
        return

    missing = [
        name
        for name, value in {
            "DATABASE_URL": settings["database_url"],
            "JWT_SECRET_KEY": settings["jwt_secret_key"],
            "CORS_ORIGINS": settings["cors_origins"],
            "PRODUCT_IMAGE_BASE_URL": settings["product_image_base_url"],
            "BLOB_READ_WRITE_TOKEN": settings["blob_read_write_token"],
        }.items()
        if not value.strip()
    ]
    if missing:
        raise RuntimeError(
            "Missing required production environment variables: " + ", ".join(missing)
        )
    if len(settings["jwt_secret_key"]) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must contain at least 32 characters in production."
        )
    if settings["database_pool_mode"] != "null":
        raise RuntimeError(
            "DATABASE_POOL_MODE must be 'null' in production serverless deployments."
        )
    if settings["file_storage_backend"] != "vercel_blob":
        raise RuntimeError("FILE_STORAGE_BACKEND must be 'vercel_blob' in production.")
