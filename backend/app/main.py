from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="StarLink CRM API",
    version="0.1.0",
    openapi_url=f"{settings['api_prefix']}/openapi.json",
    docs_url=f"{settings['api_prefix']}/docs",
)


@app.get(f"{settings['api_prefix']}/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Confirm that the API process is accepting requests."""
    return {"status": "ok", "service": "starlink-crm-api"}
