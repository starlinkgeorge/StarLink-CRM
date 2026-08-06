from fastapi import FastAPI

from app.api import auth, contacts, customers, followups, users
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="StarLink CRM API",
    version="0.1.0",
    openapi_url=f"{settings['api_prefix']}/openapi.json",
    docs_url=f"{settings['api_prefix']}/docs",
)

app.include_router(users.router, prefix=settings["api_prefix"])
app.include_router(auth.router, prefix=settings["api_prefix"])
app.include_router(customers.router, prefix=settings["api_prefix"])
app.include_router(contacts.router, prefix=settings["api_prefix"])
app.include_router(followups.router, prefix=settings["api_prefix"])


@app.get(f"{settings['api_prefix']}/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Confirm that the API process is accepting requests."""
    return {"status": "ok", "service": "starlink-crm-api"}
