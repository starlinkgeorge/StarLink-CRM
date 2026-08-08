from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    contacts,
    customer_categories,
    customers,
    dashboard,
    followups,
    integrations,
    leads,
    opportunities,
    products,
    quotations,
    tags,
    users,
)
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="StarLink CRM API",
    version="7.0.0",
    openapi_url=f"{settings['api_prefix']}/openapi.json",
    docs_url=f"{settings['api_prefix']}/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings["cors_origins"].split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(users.router, prefix=settings["api_prefix"])
app.include_router(auth.router, prefix=settings["api_prefix"])
app.include_router(dashboard.router, prefix=settings["api_prefix"])
app.include_router(customers.router, prefix=settings["api_prefix"])
app.include_router(customer_categories.router, prefix=settings["api_prefix"])
app.include_router(tags.router, prefix=settings["api_prefix"])
app.include_router(contacts.router, prefix=settings["api_prefix"])
app.include_router(followups.router, prefix=settings["api_prefix"])
app.include_router(leads.router, prefix=settings["api_prefix"])
app.include_router(integrations.router, prefix=settings["api_prefix"])
app.include_router(opportunities.router, prefix=settings["api_prefix"])
app.include_router(products.category_router, prefix=settings["api_prefix"])
app.include_router(products.router, prefix=settings["api_prefix"])
app.include_router(quotations.router, prefix=settings["api_prefix"])


@app.get(f"{settings['api_prefix']}/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Confirm that the API process is accepting requests."""
    return {"status": "ok", "service": "starlink-crm-api"}
