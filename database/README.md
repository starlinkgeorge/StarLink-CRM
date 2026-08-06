# Database foundation

PostgreSQL 16 is the supported local database for StarLink-CRM. The schema is owned by the FastAPI backend and evolves through Alembic migrations in `backend/alembic/versions/`.

- Keep `init/` for database bootstrap operations only.
- Use versioned Alembic migrations for every schema change.
- Do not place credentials or production data in this directory.

Apply the current schema from `backend/` with `alembic upgrade head` after setting `DATABASE_URL`.
