"""Vercel FastAPI entrypoint.

Vercel discovers an ``app`` object from this supported root entrypoint.  It
deliberately does not run Alembic: schema upgrades must be applied as a
controlled release step before deploying a new serverless function.
"""

from app.config import validate_production_settings

validate_production_settings()

from app.main import app  # noqa: E402
