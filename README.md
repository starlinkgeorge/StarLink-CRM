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

### Full local stack with Docker

```bash
cp .env.example .env
docker compose up --build
```

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
