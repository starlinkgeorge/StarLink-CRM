# Initial architecture

## Components

- **Frontend:** React and TypeScript, built with Vite.
- **Backend:** FastAPI, exposing versioned HTTP endpoints under `/api/v1`.
- **Database:** PostgreSQL 16.
- **Local orchestration:** Docker Compose.

## Boundary decisions

- The frontend contains presentation and browser interaction only.
- The backend owns validation, authorization, business rules, and database access.
- PostgreSQL is accessed by the backend only; it is not exposed to browser code.
- Business domains are intentionally deferred until requirements are approved.

## Operational baseline

Environment-specific values live in `.env` files and are never committed. Container definitions are intended for local development first; production deployment hardening is a separate, reviewed phase.
