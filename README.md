# StarLink-CRM

StarLink-CRM is the foundation for a long-lived customer relationship management platform for **Dalian StarLink International Trade**, an exporter of Montessori educational products and wooden kindergarten furniture.

## Current release: CRM V10

The current release includes:

- JWT login and role-based access control
- Customer list with pagination, search, and CRM filters
- Customer detail profiles with contacts, tags, sales stage, and follow-up timeline
- Customer profiles capture customer type, acquisition source, interested products, and sales stage
- Full follow-up timeline with edit/delete, opportunity links, file attachments, activity date, and next-follow-up dates
- Customer Center that unifies the profile, contacts, opportunities, quotations, follow-ups, attachments, and customer activity in one view
- V7 sales pipeline with seven Kanban stages, probability, next action, estimated amount, expected close date, and immutable sales-stage history
- V8 Alibaba inquiry management with manual entry, search/filtering, source analytics, and atomic Inquiry → Customer + Contact + Opportunity conversion
- V9 foreign-trade opportunity workflow with six business stages, deal-stage audit history, amount, probability, expected-close-date management, and a customer/contact/product/quotation/follow-up sales workspace
- V10 customer and opportunity follow-up reminders, including today/overdue/week dashboard summaries, quote follow-up reminders, and inactivity alerts
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

The frontend API client automatically refreshes an expired access token once and retries the original request. If the
refresh token is expired or revoked, the session is cleared and the user is returned to the login page instead of
leaving every page in a failed-loading state.

Create the first administrator only from a trusted local terminal after applying migrations:

```bash
cd backend
python scripts/create_admin.py
```

Roles: `Admin` manages all records and users; `Sales` reads and manages only customers assigned to itself; `Viewer` has read-only CRM access. All endpoints below require authentication:

| Resource | Endpoints |
| --- | --- |
| Users | `GET /users`, `POST /users`, `GET /users/{id}` |
| Customers | `GET /customers?limit=20&offset=0&q=keyword`, `POST /customers`, `GET /customers/{id}`, `GET /customers/{id}/center`, `GET /customers/{id}/timeline`, `PUT /customers/{id}`, `DELETE /customers/{id}` |
| Customer classification | `GET /customer-categories`, `POST /customer-categories`, `PUT /customer-categories/{id}`, `GET /customers?category_id={id}&score_min=50&score_max=100` |
| Leads | `GET /leads`, `POST /leads`, `GET /leads/{id}`, `POST /leads/{id}/convert` |
| Inquiries | `GET /inquiries`, `POST /inquiries`, `GET /inquiries/{id}`, `PUT /inquiries/{id}`, `POST /inquiries/{id}/convert` |
| Opportunities | `GET /opportunities?deal_stage={stage}`, `GET /opportunities/pipeline` (V7 compatibility), `GET /opportunities/deal-pipeline` (V9), `POST /opportunities`, `GET /opportunities/{id}`, `PUT /opportunities/{id}`, `PUT /opportunities/{id}/products` |
| Product categories | `GET /product-categories`, `POST /product-categories`, `PUT /product-categories/{id}` |
| Products | `GET /products`, `POST /products`, `GET /products/{id}`, `PUT /products/{id}` |
| Quotations | `GET /quotations?customer_id={id}`, `POST /quotations`, `GET /quotations/{id}`, `PUT /quotations/{id}`, `POST /quotations/{id}/versions`, `POST /quotations/{id}/pdf`, `GET /quotations/{id}/pdf`, `POST /quotations/{id}/send` |
| Alibaba integration | `GET /integrations/alibaba/status`, `POST /integrations/alibaba/inquiries` |
| Contacts | `POST /contacts`, `GET /contacts/{id}`, `PUT /contacts/{id}` |
| Follow-ups | `POST /followups`, `GET /followups?customer_id={id}`, `PUT /followups/{id}`, `DELETE /followups/{id}`, `POST /followups/{id}/attachments`, `GET /followups/{id}/attachments/{attachment_id}`, `DELETE /followups/{id}/attachments/{attachment_id}` |
| Dashboard | `GET /dashboard/stats` |
| Tags | `GET /tags`, `POST /tags`, `PUT /tags/{id}`, `DELETE /tags/{id}` (soft deactivate), `POST /customers/{id}/tags/{tag_id}`, `DELETE /customers/{id}/tags/{tag_id}` |

The customer `q` parameter searches company name, primary contact name, country, and email. Empty or whitespace-only query and filter values are ignored, so the initial list request returns all visible customers. Customer creation accepts `customer_type`, `source`, `interested_product`, and `sales_stage`. The V3-facing `sales_stage` is synchronized with the legacy `status` field so existing V2.2 dashboard statistics remain compatible. Customer lists support `customer_type`, `interested_product`, `sales_stage`, `source`, `status`, `level`, `country`, and `tag_id` filters; the legacy `status` parameter remains available for existing clients. Customer details include related contacts, tags, and follow-ups. The customer timeline endpoint combines customer creation, follow-ups, and persisted sales-stage changes in newest-first order. Existing follow-up endpoints continue to read and write `followups` without payload changes.

V4 adds configurable customer categories and score-based grading without removing the legacy `level` field. `customer_score` is an integer from 0 to 100; saving a score automatically maps 80-100 to A, 50-79 to B, and 0-49 to C. Score changes are retained in `customer_score_history` with an optional reason. Customer lists support `category_id`, `score_min`, and `score_max` filters. Admin and Sales users may manage categories/tags and score customers within their normal customer scope; Viewer users can read but cannot change taxonomy or scores. Tag deletion is a soft deactivation so existing customer relationships remain intact.

V5 expands follow-ups without changing the legacy records or create payload. Each record can optionally link to an opportunity, records a business `followup_date`, supports edit/delete, and can store multiple attachments. Supported channels are `Email`, `WhatsApp`, `Alibaba`, `Phone`, and `Meeting`. `next_followup_date` still drives reminders: the latest follow-up for each customer defines its current reminder, so an older planned date is superseded when a newer follow-up is recorded. Dashboard statistics expose `today_followup_count`, `overdue_followup_count`, `week_followup_count`, `today_followups`, and `overdue_followups`, while retaining the existing response fields for compatibility. Reminder lists contain up to ten visible customers per category and respect the current user's customer scope. Attachments accept PDF, image, Office, and TXT files up to 10 MB and are stored outside the database in `FOLLOWUP_ATTACHMENT_DIR` (a persistent Docker volume by default). Interactive API documentation is available at `/api/v1/docs` while the backend is running.

Apply migration `0013_v5_followup_management` with `alembic upgrade head`. It backfills `followup_date` from existing `created_at` values and adds only nullable opportunity links, timestamps, and the new attachment table; it does not remove or rewrite legacy follow-up content.

V6 adds the read-only Customer Center endpoint and page without changing the database schema. `GET /customers/{id}/center` returns the same customer fields as the legacy detail endpoint plus permission-scoped opportunities, quotations, activities, score history, follow-ups, and attachment metadata. The legacy `/customers/{id}`, timeline, opportunity, and quotation endpoints remain unchanged. `GET /quotations` also accepts optional `customer_id` filtering. No new Alembic migration is required for this API/UI-only release.

V7 adds a sales pipeline without replacing the existing V3 `opportunities.stage` enum or its immutable history. The new `sales_stage` values are `New Lead`, `Contacted`, `Requirement Confirmed`, `Quotation Sent`, `Negotiation`, `Won`, and `Lost`. The API maps each V7 stage to the closest legacy stage, so existing Lead conversion, quotation, dashboard, and integration clients remain compatible. Opportunities now also have `probability` (0-100), `next_action`, and the existing `amount`/`expected_close_date` fields are presented as estimated sales values. `GET /opportunities/pipeline` returns seven permission-scoped Kanban columns; Sales users see only their assigned opportunities and Viewer users remain read-only. Dashboard statistics retain every existing field and add `opportunity_pipeline`, `opportunity_total_amounts`, and `pending_followup_customer_count`.

Apply migration `0014_v7_sales_pipeline` with `alembic upgrade head`. It adds fields and a sales-stage history table, backfills V7 stages/probabilities from the legacy stage, and does not delete or alter the existing `stage` field or `opportunity_stage_history` table.

V8 adds an independent `inquiries` table for external marketplace inquiries and leaves the older `leads` table and its Alibaba simulation endpoint unchanged. Each Inquiry records the acquisition channel, source platform, contact information, product need, original content, and a processing status (`New`, `Processing`, `Converted`, or `Closed`). `POST /inquiries/{id}/convert` is transactional: it creates a customer, primary contact, V7 `New Lead` opportunity, and both opportunity-history records before marking the Inquiry as `Converted`. The new customer retains `source`, `source_platform`, and `original_inquiry`, while all fields are nullable on existing customers for safe migration. Dashboard stats now include `today_inquiry_count`, `pending_inquiry_count`, and `inquiry_source_stats`. Admin and Sales can create, update, and convert inquiries; Viewer users remain read-only.

Apply migration `0015_v8_alibaba_inquiry_management` with `alembic upgrade head`. It only adds the nullable customer source-context columns, backfills `source_platform` from the existing `source` where possible, and creates the new `inquiries` table with indexes and a status check constraint. No existing Lead, Customer, Opportunity, Follow-up, or Quotation field is removed or changed.

V9 adds the user-facing opportunity stages `New Inquiry`, `Contacted`, `Quoted`, `Negotiating`, `Won`, and `Lost`. `deal_stage` is the canonical V9 field shown in the opportunity list, detail workspace, and six-column sales board. Existing V3 `stage` and V7 `sales_stage` fields remain available and are mapped automatically on create and update, so existing inquiry conversion, dashboard, quotation, and API clients keep working. Opportunity details now aggregate the customer, contacts, catalog products, related quotations, and relevant follow-up records alongside amount, probability, estimated close date, and next action.

Apply migration `0016_v9_opportunity_deal_management` with `alembic upgrade head`. It backfills `deal_stage` from the existing V7 sales stage, creates the indexed immutable `opportunity_deal_stage_history` table, and does not remove or rewrite any existing opportunity column or history table. The migration takes a PostgreSQL transaction advisory lock so two concurrent startup/manual Alembic upgrades cannot both apply it.

The Lead inquiry pool accepts new inquiries, supports pagination and filtering, and exposes a detail view. `POST /leads/{id}/convert` atomically creates a customer, its primary contact, and a base opportunity, then marks the Lead as `Converted`. The unique opportunity-to-Lead link prevents duplicate conversion. Admin and Sales users may create and convert Leads; Viewer users retain read-only access.

Opportunities use an independent lifecycle: `Lead`, `Qualified`, `Proposal`, `Negotiation`, `Won`, and `Lost`. Lists support pagination, search, stage filtering, and customer filtering. Opportunity details combine customer information, product and inquiry requirements, amount/currency, expected close date, immutable stage history, and the customer's follow-up records. Lead conversion carries the company name, product need, and inquiry content into the opportunity. Admin users manage all opportunities; Sales users create and update only opportunities assigned to themselves; Viewer users are read-only. Dashboard opportunity counts respect the same scope, and amounts are grouped by currency instead of mixing incompatible totals.

The product catalog stores hierarchical categories, SKU, dimensions, material, MOQ, reference price, currency, active state, and URL-based image lists with at most one primary image. Product lists accept `q`, `category_id`, and `is_active` filters; an empty `q` returns all products. Product images use `http` or `https` URLs in this phase. Opportunities link catalog products through `PUT /opportunities/{id}/products`, with per-line quantity and target price. The legacy free-text `interested_product` remains available, including on Lead conversion, to preserve existing inquiry data. Admin and Sales users may create and edit catalog records; Viewer users are read-only.

The 2025 solid-wood catalogue can be imported idempotently with `backend/scripts/import_product_catalog.py`. Rebuild the backend image and run `docker compose exec backend python scripts/import_product_catalog.py`; existing SKUs are skipped and new records are assigned to the `Solid Wood Furniture` category.

The 2025 **Wooden Furniture** catalogue is available through `backend/scripts/import_wooden_furniture_catalog.py`. It creates the 85 `K-F-001` through `K-F-085` catalogue products in the `2025 Wooden Furniture` category, including USD reference prices, source dimensions, and the matching PDF-extracted product image. Existing SKUs and product images are preserved, so it is safe to rerun:

```bash
docker compose up -d --build
docker compose exec backend python scripts/import_wooden_furniture_catalog.py
```

The 2025 **Montessori Materials** catalogue is available through
`backend/scripts/import_montessori_materials_catalog.py`. It creates 494
products across Practical Life, Sensorial, Language, Mathematics, Biology,
Geography, Infant & Toddler, Educational Toys, and Role Play categories. USD
reference prices, source dimensions, weights, and PDF-extracted product images
are included. The import is safe to rerun: existing SKUs are preserved and an
image is added only when that product currently has none.

```bash
docker compose up -d --build
docker compose exec backend python scripts/import_montessori_materials_catalog.py
```

The backend startup runs `scripts/ensure_alembic_version.py` before `alembic upgrade head`. This keeps the Alembic version table able to store long revision IDs such as the V4 migration. The repair migration is `0012_expand_alembic_version`; existing migration files remain unchanged.

The matching catalogue images are stored under `frontend/public/product-images`. After rebuilding the frontend, run `docker compose exec backend python scripts/import_product_images.py` to attach the 45 image URLs to products. The image importer preserves any product that already has an image; set `PRODUCT_IMAGE_BASE_URL` when the frontend is hosted at a different public URL.

Quotations are created from an opportunity and its product lines. Each version stores immutable SKU, product name, picture, unit-price, quantity, and line-total snapshots, so later catalog edits do not alter historical quotations. A Draft version can be edited and regenerated; marking it Sent locks the version. Further changes copy the previous snapshot into V2, V3, and later versions. Generated PDFs use the StarLink company header and the requested `Item Name / Picture / Unit Price / QTY / Total Price` table, followed by product total, door-to-door shipping, amount, validity, payment term, and delivery time. The PDF files are persisted in the Docker `quotation_pdfs` volume and downloaded through an authenticated API endpoint.

When editing a quotation, the product picker supports a server-backed search
by SKU, product name, or material. Type a search term and matching products are
shown directly in the page; click a result to add it to the draft. Products
already on the draft are excluded from the results.

Apply `0017_v10_sales_followup_reminders` and the additive repair migration
`0018_repair_v10_opportunity_reminder_schema` on databases that may have a
stale Alembic stamp. The repair only adds missing V10 reminder columns and
preserves existing customer, opportunity, inquiry, quotation, and follow-up
data.

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
COMPANY_ALIBABA_STORE=https://www.alibaba.com/store/your-store
COMPANY_WEBSITE=https://your-real-website.example
COMPANY_EMAIL=sales@your-real-domain.example
COMPANY_WHATSAPP=+86-your-real-number
```

Quotation PDFs show the Alibaba Store and Company Website on separate lines. Product rows use fixed-size, vertically centered pictures, with the product name/SKU hierarchy and numeric columns aligned for business quotation readability; the totals and formal terms section follow the same template.
Older `.env` files that stored the two website links as `Alibaba URL&Company URL` are split automatically for backward compatibility; new deployments should use the two explicit variables above.

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
