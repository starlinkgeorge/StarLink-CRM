# Database foundation

PostgreSQL 16 is the supported local database for StarLink-CRM.

- Place first-run SQL in `init/`.
- Use versioned migrations (for example, Alembic) once application data models are designed.
- Do not place credentials or production data in this directory.

The initial schema is intentionally empty because no business data model has been approved.
