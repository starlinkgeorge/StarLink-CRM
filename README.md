# StarLink-CRM

StarLink-CRM is the foundation for a long-lived customer relationship management platform for **Dalian StarLink International Trade**, an exporter of Montessori educational products and wooden kindergarten furniture.

## Current release: CRM V2.2

The current release includes:

- JWT login and role-based access control
- Customer list with pagination, search, and CRM filters
- Customer detail profiles with contacts, tags, sales stage, and follow-up timeline
- Customer profiles capture customer type, acquisition source, interested products, and sales stage
- Follow-up creation with optional next-follow-up dates
- Dashboard statistics backed by PostgreSQL, including total follow-ups and upcoming work
- React + TypeScript + Tailwind frontend
- Python FastAPI + SQLAlchemy backend
- PostgreSQL service configuration
- Docker Compose and container build configuration
- Environment, documentation, scripts, and test placeholders

AI and third-party marketplace integrations are intentionally outside this release.

## Prerequisites

- Node.js 20+
- Python 3.11+
- Docker Desktop (optional, for the complete local stack)

## Run locally

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

The frontend is served at `http://localhost:5173` by default.

### Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API health endpoint is available at `http://localhost:8000/api/v1/health`.

### Database migration

Set `DATABASE_URL` to a PostgreSQL connection string, then apply all pending schema migrations:

```bash
cd backend
alembic upgrade head
```

Migration `0005_repair_v3_customer_columns` repairs databases whose Alembic revision advanced while the V3 customer columns were missing. It conditionally adds `customer_type`, `interested_product`, and `sales_stage`, backfills `sales_stage` from the legacy `status` value, and leaves already-correct schemas unchanged.

See [docs/database-design.md](docs/database-design.md) for the CRM data model.

## Authentication and API access

Set a unique, high-entropy `JWT_SECRET_KEY` in `.env` before running the backend. Passwords are bcrypt hashes; API clients submit `password` only to create users or log in, and password values are never returned.

Obtain tokens with `POST /api/v1/auth/login` using `email` and `password`. Send the access token on protected API calls:

```text
Authorization: Bearer <access_token>
```

`POST /api/v1/auth/refresh` rotates a valid refresh token. Refresh token values are never stored in the database; only SHA-256 token digests are stored.

Create the first administrator only from a trusted local terminal after applying migrations:

```bash
cd backend
python scripts/create_admin.py
```

Roles: `Admin` manages all records and users; `Sales` reads and manages only customers assigned to itself; `Viewer` has read-only CRM access. All endpoints below require authentication:

| Resource | Endpoints |
| --- | --- |
| Users | `GET /users`, `POST /users`, `GET /users/{id}` |
| Customers | `GET /customers?limit=20&offset=0&q=keyword`, `POST /customers`, `GET /customers/{id}`, `GET /customers/{id}/timeline`, `PUT /customers/{id}`, `DELETE /customers/{id}` |
| Leads | `GET /leads`, `POST /leads`, `GET /leads/{id}`, `POST /leads/{id}/convert` |
| Alibaba integration | `GET /integrations/alibaba/status`, `POST /integrations/alibaba/inquiries` |
| Contacts | `POST /contacts`, `GET /contacts/{id}`, `PUT /contacts/{id}` |
| Follow-ups | `POST /followups`, `GET /followups?customer_id={id}` |
| Dashboard | `GET /dashboard/stats` |
| Tags | `GET /tags`, `POST /tags`, `POST /customers/{id}/tags/{tag_id}`, `DELETE /customers/{id}/tags/{tag_id}` |

The customer `q` parameter searches company name, primary contact name, country, and email. Empty or whitespace-only query and filter values are ignored, so the initial list request returns all visible customers. Customer creation accepts `customer_type`, `source`, `interested_product`, and `sales_stage`. The V3-facing `sales_stage` is synchronized with the legacy `status` field so existing V2.2 dashboard statistics remain compatible. Customer lists support `customer_type`, `interested_product`, `sales_stage`, `source`, `status`, `level`, `country`, and `tag_id` filters; the legacy `status` parameter remains available for existing clients. Customer details include related contacts, tags, and follow-ups. The customer timeline endpoint combines customer creation, follow-ups, and persisted sales-stage changes in newest-first order. Existing follow-up endpoints continue to read and write `followups` without payload changes.

Follow-up reminders reuse `next_followup_date`; no separate reminder record is required. The latest follow-up for each customer defines its current reminder, so an older planned date is superseded when a newer follow-up is recorded. Dashboard statistics expose `today_followup_count`, `overdue_followup_count`, `today_followups`, and `overdue_followups`, while retaining the existing response fields for compatibility. Reminder lists contain up to ten visible customers per category and respect the current user's customer scope. Interactive API documentation is available at `/api/v1/docs` while the backend is running.

The Lead inquiry pool accepts new inquiries, supports pagination and filtering, and exposes a detail view. `POST /leads/{id}/convert` atomically creates a customer, its primary contact, and a base opportunity, then marks the Lead as `Converted`. The unique opportunity-to-Lead link prevents duplicate conversion. Admin and Sales users may create and convert Leads; Viewer users retain read-only access.

The first-phase Alibaba integration accepts simulated inquiries through an authenticated endpoint. It always sets Lead `source` to `Alibaba` and `status` to `New`, regardless of submitted source data. Existing Leads are returned instead of duplicated when a case-insensitive email match or company-and-contact match is found. The Settings page exposes connection state and a simulation button. No database migration is required for this integration phase; see [docs/alibaba-integration.md](docs/alibaba-integration.md) for the future production-authentication boundary.

Run API tests after installing backend development dependencies:

```bash
cd backend
pytest
```

## Frontend CRM interface

The React frontend includes login, dashboard, Lead inquiry list/detail/creation/conversion, data-source settings, customer list, customer detail, customer creation, and follow-up creation pages. The Dashboard separates today's reminders from overdue customers. The customer detail page shows the current reminder state plus a newest-first activity timeline containing customer creation, follow-ups, and sales-stage changes. Set `VITE_API_BASE_URL` in `frontend/.env` if the backend is not running at the local default, then run `npm install` and `npm run dev` from `frontend/`.

### Full local stack with Docker

```bash
cp .env.example .env
docker compose up --build
```

The backend image installs its explicit runtime dependency list from `backend/requirements.txt`; it does not build the local Python package during image construction.

## Project layout

```text
StarLink-CRM/
├── frontend/       # React + TypeScript application
├── backend/        # FastAPI application
├── database/       # PostgreSQL initialization and database notes
├── docker/         # Container build definitions
├── docs/           # Architecture and project documentation
├── scripts/        # Local development helpers
└── tests/          # Cross-service test space
```

## Configuration

Copy `.env.example` to `.env` before running Docker Compose. Never commit `.env` files or real credentials.

## Next steps

1. Agree on user roles, customer lifecycle, and data ownership rules.
2. Define the PostgreSQL schema and create versioned migrations.
3. Add authentication, authorization, audit logging, and API error conventions.
4. Establish CI checks for formatting, tests, dependency security, and container builds.

See [docs/architecture.md](docs/architecture.md) for the initial architecture decisions.
