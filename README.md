# StarLink-CRM

StarLink-CRM is the foundation for a long-lived customer relationship management platform for **Dalian StarLink International Trade**, an exporter of Montessori educational products and wooden kindergarten furniture.

## Current release: CRM V3

The current release includes:

- JWT login and role-based access control
- Customer list with pagination, search, and CRM filters
- Customer detail profiles with contacts, tags, sales stage, and follow-up timeline
- Customer profiles capture customer type, acquisition source, interested products, and sales stage
- Follow-up creation with optional next-follow-up dates
- Dashboard statistics backed by PostgreSQL, including total follow-ups and upcoming work
- Lead inquiry pool, Lead conversion, Alibaba inquiry simulation, and opportunity management
- Product catalog with categories, specifications, prices, URL images, and opportunity product lines
- Versioned StarLink quotation workflow with product snapshots and PDF generation
- React + TypeScript + Tailwind frontend
- Python FastAPI + SQLAlchemy backend
- PostgreSQL service configuration
- Docker Compose and container build configuration
- Environment, documentation, scripts, and test placeholders

AI features and live third-party marketplace credentials remain outside this release. The Alibaba endpoint is an integration contract and local simulation only.

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
| Customer classification | `GET /customer-categories`, `POST /customer-categories`, `PUT /customer-categories/{id}`, `GET /customers?category_id={id}&score_min=50&score_max=100` |
| Leads | `GET /leads`, `POST /leads`, `GET /leads/{id}`, `POST /leads/{id}/convert` |
| Opportunities | `GET /opportunities`, `POST /opportunities`, `GET /opportunities/{id}`, `PUT /opportunities/{id}`, `PUT /opportunities/{id}/products` |
| Product categories | `GET /product-categories`, `POST /product-categories`, `PUT /product-categories/{id}` |
| Products | `GET /products`, `POST /products`, `GET /products/{id}`, `PUT /products/{id}` |
| Quotations | `GET /quotations`, `POST /quotations`, `GET /quotations/{id}`, `PUT /quotations/{id}`, `POST /quotations/{id}/versions`, `POST /quotations/{id}/pdf`, `GET /quotations/{id}/pdf`, `POST /quotations/{id}/send` |
| Alibaba integration | `GET /integrations/alibaba/status`, `POST /integrations/alibaba/inquiries` |
| Contacts | `POST /contacts`, `GET /contacts/{id}`, `PUT /contacts/{id}` |
| Follow-ups | `POST /followups`, `GET /followups?customer_id={id}` |
| Dashboard | `GET /dashboard/stats` |
| Tags | `GET /tags`, `POST /tags`, `PUT /tags/{id}`, `DELETE /tags/{id}` (soft deactivate), `POST /customers/{id}/tags/{tag_id}`, `DELETE /customers/{id}/tags/{tag_id}` |

The customer `q` parameter searches company name, primary contact name, country, and email. Empty or whitespace-only query and filter values are ignored, so the initial list request returns all visible customers. Customer creation accepts `customer_type`, `source`, `interested_product`, and `sales_stage`. The V3-facing `sales_stage` is synchronized with the legacy `status` field so existing V2.2 dashboard statistics remain compatible. Customer lists support `customer_type`, `interested_product`, `sales_stage`, `source`, `status`, `level`, `country`, and `tag_id` filters; the legacy `status` parameter remains available for existing clients. Customer details include related contacts, tags, and follow-ups. The customer timeline endpoint combines customer creation, follow-ups, and persisted sales-stage changes in newest-first order. Existing follow-up endpoints continue to read and write `followups` without payload changes.

V4 adds configurable customer categories and score-based grading without removing the legacy `level` field. `customer_score` is an integer from 0 to 100; saving a score automatically maps 80-100 to A, 50-79 to B, and 0-49 to C. Score changes are retained in `customer_score_history` with an optional reason. Customer lists support `category_id`, `score_min`, and `score_max` filters. Admin and Sales users may manage categories/tags and score customers within their normal customer scope; Viewer users can read but cannot change taxonomy or scores. Tag deletion is a soft deactivation so existing customer relationships remain intact.

Follow-up reminders reuse `next_followup_date`; no separate reminder record is required. The latest follow-up for each customer defines its current reminder, so an older planned date is superseded when a newer follow-up is recorded. Supported channels are `Email`, `WhatsApp`, `Alibaba`, `Phone`, and `Meeting`; the existing `content`, `next_followup_date`, and `created_at` fields remain backward compatible. Dashboard statistics expose `today_followup_count`, `overdue_followup_count`, `week_followup_count`, `today_followups`, and `overdue_followups`, while retaining the existing response fields for compatibility. Reminder lists contain up to ten visible customers per category and respect the current user's customer scope. Interactive API documentation is available at `/api/v1/docs` while the backend is running.

The Lead inquiry pool accepts new inquiries, supports pagination and filtering, and exposes a detail view. `POST /leads/{id}/convert` atomically creates a customer, its primary contact, and a base opportunity, then marks the Lead as `Converted`. The unique opportunity-to-Lead link prevents duplicate conversion. Admin and Sales users may create and convert Leads; Viewer users retain read-only access.

Opportunities use an independent lifecycle: `Lead`, `Qualified`, `Proposal`, `Negotiation`, `Won`, and `Lost`. Lists support pagination, search, stage filtering, and customer filtering. Opportunity details combine customer information, product and inquiry requirements, amount/currency, expected close date, immutable stage history, and the customer's follow-up records. Lead conversion carries the company name, product need, and inquiry content into the opportunity. Admin users manage all opportunities; Sales users create and update only opportunities assigned to themselves; Viewer users are read-only. Dashboard opportunity counts respect the same scope, and amounts are grouped by currency instead of mixing incompatible totals.

The product catalog stores hierarchical categories, SKU, dimensions, material, MOQ, reference price, currency, active state, and URL-based image lists with at most one primary image. Product lists accept `q`, `category_id`, and `is_active` filters; an empty `q` returns all products. Product images use `http` or `https` URLs in this phase. Opportunities link catalog products through `PUT /opportunities/{id}/products`, with per-line quantity and target price. The legacy free-text `interested_product` remains available, including on Lead conversion, to preserve existing inquiry data. Admin and Sales users may create and edit catalog records; Viewer users are read-only.

The 2025 solid-wood catalogue can be imported idempotently with `backend/scripts/import_product_catalog.py`. Rebuild the backend image and run `docker compose exec backend python scripts/import_product_catalog.py`; existing SKUs are skipped and new records are assigned to the `Solid Wood Furniture` category.

The backend startup runs `scripts/ensure_alembic_version.py` before `alembic upgrade head`. This keeps the Alembic version table able to store long revision IDs such as the V4 migration. The repair migration is `0012_expand_alembic_version`; existing migration files remain unchanged.

The matching catalogue images are stored under `frontend/public/product-images`. After rebuilding the frontend, run `docker compose exec backend python scripts/import_product_images.py` to attach the 45 image URLs to products. The image importer preserves any product that already has an image; set `PRODUCT_IMAGE_BASE_URL` when the frontend is hosted at a different public URL.

Quotations are created from an opportunity and its product lines. Each version stores immutable SKU, product name, picture, unit-price, quantity, and line-total snapshots, so later catalog edits do not alter historical quotations. A Draft version can be edited and regenerated; marking it Sent locks the version. Further changes copy the previous snapshot into V2, V3, and later versions. Generated PDFs use the StarLink company header and the requested `Item Name / Picture / Unit Price / QTY / Total Price` table, followed by product total, door-to-door shipping, amount, validity, payment term, and delivery time. The PDF files are persisted in the Docker `quotation_pdfs` volume and downloaded through an authenticated API endpoint.

Quotation PDF generation resolves URLs under `/product-images/` from the backend's local `PRODUCT_IMAGE_DIR` (default `/app/product-images`) before attempting public HTTP images. The backend Docker image copies the catalog image assets so product pictures remain available inside containers.

When saving a draft, blank payment terms, delivery time, currency, or shipping cost values are normalized to the configured defaults; product prices and quantities remain strictly validated.
Quotation draft updates keep nested product inputs as validated Pydantic objects through the service layer, preventing item updates from becoming unhandled 500 errors.

The first-phase Alibaba integration accepts simulated inquiries through an authenticated endpoint. It always sets Lead `source` to `Alibaba` and `status` to `New`, regardless of submitted source data. Existing Leads are returned instead of duplicated when a case-insensitive email match or company-and-contact match is found. The Settings page exposes connection state and a simulation button. No database migration is required for this integration phase; see [docs/alibaba-integration.md](docs/alibaba-integration.md) for the future production-authentication boundary.

Run API tests after installing backend development dependencies:

```bash
cd backend
pytest
```

## Frontend CRM interface

The React frontend includes login, dashboard, Lead inquiry list/detail/creation/conversion, opportunity list/detail/creation/update, product list/detail/creation/editing, quotation list/detail/version/PDF workflows, data-source settings, customer list, customer detail, customer creation, and follow-up creation pages. The product library supports search, category and active-state filters, URL image management, and enable/disable actions. Opportunity details support product lines with quantity and target price and provide the `Create Quotation` action. The Dashboard separates today's reminders from overdue customers and includes scoped opportunity statistics. Set `VITE_API_BASE_URL` in `frontend/.env` if the backend is not running at the local default, then run `npm install` and `npm run dev` from `frontend/`.

Before generating customer-facing PDFs, set the real company contact values in `.env`:

```text
COMPANY_WEBSITE=https://your-real-website.example
COMPANY_EMAIL=sales@your-real-domain.example
COMPANY_WHATSAPP=+86-your-real-number
```

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
