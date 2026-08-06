from functools import lru_cache
from os import getenv


@lru_cache
def get_settings() -> dict[str, str]:
    """Return the minimal runtime configuration for the API foundation."""
    return {
        "environment": getenv("APP_ENV", "development"),
        "api_prefix": getenv("API_PREFIX", "/api/v1"),
    }
