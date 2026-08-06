# StarLink-CRM

StarLink-CRM is the foundation for a long-lived customer relationship management platform for **Dalian StarLink International Trade**, an exporter of Montessori educational products and wooden kindergarten furniture.

## Scope of this initial release

This release establishes only the project foundation:

- React + TypeScript frontend skeleton
- Python FastAPI backend skeleton with a health endpoint
- PostgreSQL service configuration
- Docker Compose and container build configuration
- Environment, documentation, scripts, and test placeholders

No customer-management, AI, authentication, or other business features are included yet.

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

Set `DATABASE_URL` to a PostgreSQL connection string, then run the initial schema migration:

```bash
cd backend
alembic upgrade head
```

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
| Customers | `GET /customers?limit=20&offset=0&q=keyword`, `POST /customers`, `GET /customers/{id}`, `PUT /customers/{id}`, `DELETE /customers/{id}` |
| Contacts | `POST /contacts`, `GET /contacts/{id}`, `PUT /contacts/{id}` |
| Follow-ups | `POST /followups`, `GET /followups?customer_id={id}` |
| Dashboard | `GET /dashboard/stats` |

The customer `q` parameter searches company name, primary contact name, country, and email. Customer details include related contacts, tags, and follow-up records. Interactive API documentation is available at `/api/v1/docs` while the backend is running.

Run API tests after installing backend development dependencies:

```bash
cd backend
pytest
```

## Frontend CRM interface

The React frontend includes login, dashboard, customer list, customer detail, customer creation, and follow-up creation pages. Set `VITE_API_BASE_URL` in `frontend/.env` if the backend is not running at the local default, then run `npm install` and `npm run dev` from `frontend/`.

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
