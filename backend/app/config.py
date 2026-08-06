from functools import lru_cache
from os import getenv


@lru_cache
def get_settings() -> dict[str, str]:
    """Return the minimal runtime configuration for the API foundation."""
    return {
        "environment": getenv("APP_ENV", "development"),
        "api_prefix": getenv("API_PREFIX", "/api/v1"),
        "database_url": getenv("DATABASE_URL", ""),
        "jwt_secret_key": getenv("JWT_SECRET_KEY", ""),
        "jwt_access_token_minutes": getenv("JWT_ACCESS_TOKEN_MINUTES", "15"),
        "jwt_refresh_token_days": getenv("JWT_REFRESH_TOKEN_DAYS", "14"),
        "cors_origins": getenv("CORS_ORIGINS", "http://localhost:5173"),
    }
