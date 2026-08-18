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
- Opportunity list, detail, and both sales Kanban endpoints return the computed reminder state used by the dashboard and work queues
- Dashboard statistics backed by PostgreSQL, including total follow-ups and upcoming work
- Alibaba inquiry simulation, customer management, and opportunity management
- Product catalog with categories, specifications, prices, URL images, and opportunity product lines
- StarLink quotation workflow with immutable internal snapshots and PDF generation; customer-first creation opens one blank draft directly in the formal quotation editor, where products and commercial terms are entered
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

For the Vercel + Neon production deployment procedure, environment-variable
reference, storage behavior, and release smoke test, read
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Docker Compose remains the supported
local development environment.

The production `vercel.json` uses Vercel Services: `/api` and `/api/*` are
routed to the FastAPI service, while Vite assets and catalogue product images
retain their original paths. The frontend service explicitly declares Vite and
its SPA rewrite to `/index.html`, so direct visits and refreshes of client
routes such as `/products`, `/customers`, `/opportunities`, and `/quotations`
load the SPA.

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

StarLink CRM normalizes standard Neon `postgresql://` and `postgres://` URLs to
SQLAlchemy's `postgresql+psycopg://` dialect, so migrations and the API use
psycopg v3 consistently.

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
| Customers | `GET /customers?limit=20&offset=0&q=keyword`, `POST /customers`, `GET /customers/{id}`, `GET /customers/{id}/center`, `GET /customers/{id}/timeline`, `PUT /customers/{id}`, `DELETE /customers/{id}` (Admin-only list action with confirmation; customers linked to quotations cannot be deleted) |
| Customer classification | `GET /customer-categories`, `POST /customer-categories`, `PUT /customer-categories/{id}`, `GET /customers?category_id={id}&score_min=50&score_max=100` |
| Inquiries | `GET /inquiries`, `POST /inquiries`, `GET /inquiries/{id}`, `PUT /inquiries/{id}`, `POST /inquiries/{id}/convert` |
| Opportunities | `GET /opportunities?deal_stage={stage}`, `GET /opportunities/pipeline` (V7 compatibility), `GET /opportunities/deal-pipeline` (V9), `POST /opportunities`, `GET /opportunities/{id}`, `PUT /opportunities/{id}`, `DELETE /opportunities/{id}` (Admin-only; retains related quotations, follow-ups, and inquiries), `PUT /opportunities/{id}/products` |
| Product categories | `GET /product-categories`, `POST /product-categories`, `PUT /product-categories/{id}` |
| Products | `GET /products`, `POST /products`, `GET /products/{id}`, `PUT /products/{id}`, `DELETE /products/{id}` |
| Quotations | `GET /quotations?customer_id={id}`, `POST /quotations`, `GET /quotations/{id}`, `PUT /quotations/{id}`, `DELETE /quotations/{id}` (Admin-only; removes quotation versions/items only), `POST /quotations/{id}/versions`, `POST /quotations/{id}/pdf`, `GET /quotations/{id}/pdf`, `GET /quotations/{id}/excel`, `POST /quotations/{id}/send` |
| Alibaba integration | `GET /integrations/alibaba/status`, `POST /integrations/alibaba/inquiries` |
| Contacts | `POST /contacts`, `GET /contacts/{id}`, `PUT /contacts/{id}` |
| Follow-ups | `POST /followups`, `GET /followups?customer_id={id}`, `PUT /followups/{id}`, `DELETE /followups/{id}`, `POST /followups/{id}/attachments`, `GET /followups/{id}/attachments/{attachment_id}`, `DELETE /followups/{id}/attachments/{attachment_id}` |
| Dashboard | `GET /dashboard/stats` |
| Business analytics | `GET /analytics/overview?period=today|week|month|year|custom&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` |
| Tags | `GET /tags`, `POST /tags`, `PUT /tags/{id}`, `DELETE /tags/{id}` (soft deactivate), `POST /customers/{id}/tags/{tag_id}`, `DELETE /customers/{id}/tags/{tag_id}` |

The customer `q` parameter searches company name, primary contact name, country, and email. Empty or whitespace-only query and filter values are ignored, so the initial list request returns all visible customers. Customer creation accepts `customer_type`, `source`, `interested_product`, and `sales_stage`. The V3-facing `sales_stage` is synchronized with the legacy `status` field so existing V2.2 dashboard statistics remain compatible. Customer lists support `customer_type`, `interested_product`, `sales_stage`, `source`, `status`, `level`, `country`, and `tag_id` filters; the legacy `status` parameter remains available for existing clients. Customer details include related contacts, tags, and follow-ups. The customer timeline endpoint combines customer creation, follow-ups, and persisted sales-stage changes in newest-first order. Existing follow-up endpoints continue to read and write `followups` without payload changes.

V4 adds configurable customer categories and score-based grading without removing the legacy `level` field. `customer_score` is an integer from 0 to 100; saving a score automatically maps 80-100 to A, 50-79 to B, and 0-49 to C. Score changes are retained in `customer_score_history` with an optional reason. Customer lists support `category_id`, `score_min`, and `score_max` filters. Admin and Sales users may manage categories/tags and score customers within their normal customer scope; Viewer users can read but cannot change taxonomy or scores. Tag deletion is a soft deactivation so existing customer relationships remain intact.

V5 expands follow-ups without changing the legacy records or create payload. Each record can optionally link to an opportunity, records a business `followup_date`, supports edit/delete, and can store multiple attachments. Supported channels are `Email`, `WhatsApp`, `Alibaba`, `Phone`, and `Meeting`. `next_followup_date` still drives reminders: the latest follow-up for each customer defines its current reminder, so an older planned date is superseded when a newer follow-up is recorded. Dashboard statistics expose `today_followup_count`, `overdue_followup_count`, `week_followup_count`, `today_followups`, and `overdue_followups`, while retaining the existing response fields for compatibility. Reminder lists contain up to ten visible customers per category and respect the current user's customer scope. Attachments accept PDF, image, Office, and TXT files up to 10 MB and are stored outside the database in `FOLLOWUP_ATTACHMENT_DIR` (a persistent Docker volume by default). Interactive API documentation is available at `/api/v1/docs` while the backend is running.

Apply migration `0013_v5_followup_management` with `alembic upgrade head`. It backfills `followup_date` from existing `created_at` values and adds only nullable opportunity links, timestamps, and the new attachment table; it does not remove or rewrite legacy follow-up content.

V6 adds the read-only Customer Center endpoint and page without changing the database schema. `GET /customers/{id}/center` returns the same customer fields as the legacy detail endpoint plus permission-scoped opportunities, quotations, activities, score history, follow-ups, and attachment metadata. The legacy `/customers/{id}`, timeline, opportunity, and quotation endpoints remain unchanged. `GET /quotations` also accepts optional `customer_id` filtering. No new Alembic migration is required for this API/UI-only release.

V7 adds a sales pipeline without replacing the existing V3 `opportunities.stage` enum or its immutable history. The new `sales_stage` values are `New Lead`, `Contacted`, `Requirement Confirmed`, `Quotation Sent`, `Negotiation`, `Won`, and `Lost`. The API maps each V7 stage to the closest legacy stage, so existing quotation, dashboard, and integration clients remain compatible. Opportunities now also have `probability` (0-100), `next_action`, and the existing `amount`/`expected_close_date` fields are presented as estimated sales values. `GET /opportunities/pipeline` returns seven permission-scoped Kanban columns; Sales users see only their assigned opportunities and Viewer users remain read-only. Dashboard statistics retain every existing field and add `opportunity_pipeline`, `opportunity_total_amounts`, and `pending_followup_customer_count`.

Apply migration `0014_v7_sales_pipeline` with `alembic upgrade head`. It adds fields and a sales-stage history table, backfills V7 stages/probabilities from the legacy stage, and does not delete or alter the existing `stage` field or `opportunity_stage_history` table.

V8 adds an independent `inquiries` table for external marketplace inquiries. Each Inquiry records the acquisition channel, source platform, contact information, product need, original content, and a processing status (`New`, `Processing`, `Converted`, or `Closed`). `POST /inquiries/{id}/convert` is transactional: it creates a customer, primary contact, V7 `New Lead` opportunity, and both opportunity-history records before marking the Inquiry as `Converted`. The new customer retains `source`, `source_platform`, and `original_inquiry`, while all fields are nullable on existing customers for safe migration. Dashboard stats now include `today_inquiry_count`, `pending_inquiry_count`, and `inquiry_source_stats`. Admin and Sales can create, update, and convert inquiries; Viewer users remain read-only.

Apply migration `0015_v8_alibaba_inquiry_management` with `alembic upgrade head`. It only adds the nullable customer source-context columns, backfills `source_platform` from the existing `source` where possible, and creates the new `inquiries` table with indexes and a status check constraint. No existing Customer, Opportunity, Follow-up, or Quotation field is removed or changed.

V9 adds the user-facing opportunity stages `New Inquiry`, `Contacted`, `Quoted`, `Negotiating`, `Won`, and `Lost`. `deal_stage` is the canonical V9 field shown in the opportunity list, detail workspace, and six-column sales board. Existing V3 `stage` and V7 `sales_stage` fields remain available and are mapped automatically on create and update, so existing inquiry conversion, dashboard, quotation, and API clients keep working. Opportunity details now aggregate the customer, contacts, catalog products, related quotations, and relevant follow-up records alongside amount, probability, estimated close date, and next action.

Apply migration `0016_v9_opportunity_deal_management` with `alembic upgrade head`. It backfills `deal_stage` from the existing V7 sales stage, creates the indexed immutable `opportunity_deal_stage_history` table, and does not remove or rewrite any existing opportunity column or history table. The migration takes a PostgreSQL transaction advisory lock so two concurrent startup/manual Alembic upgrades cannot both apply it.

Alibaba inquiries and manually entered customers now flow directly into customer management. From a customer, follow-ups and quotations can create or associate an opportunity; the core flow is `Alibaba inquiry / manual customer → customer management → follow-up → quotation → opportunity → closing`.

Opportunities use an independent lifecycle: `Lead`, `Qualified`, `Proposal`, `Negotiation`, `Won`, and `Lost`. Lists support pagination, search, stage filtering, and customer filtering. Opportunity details combine customer information, product and inquiry requirements, amount/currency, expected close date, immutable stage history, and the customer's follow-up records. Admin users manage all opportunities; Sales users create and update only opportunities assigned to themselves; Viewer users are read-only. Dashboard opportunity counts respect the same scope, and amounts are grouped by currency instead of mixing incompatible totals.

The product catalog stores hierarchical categories, SKU, dimensions, material, MOQ, reference price, currency, active state, and URL-based image lists with at most one primary image. Product lists accept `q`, `category_id`, and `is_active` filters; an empty `q` returns all products. Product images use `http` or `https` URLs in this phase. Opportunities link catalog products through `PUT /opportunities/{id}/products`, with per-line quantity and target price. The legacy free-text `interested_product` remains available to preserve customer and inquiry data. Admin and Sales users may create and edit catalog records; Viewer users are read-only. Only Admin users can delete an unlinked product; products still linked to an opportunity must first be removed from that opportunity. Historical quotation snapshots remain intact.

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

The 2025 **Outdoor Playthings** catalogue is available through
`backend/scripts/import_outdoor_playthings_catalog.py`. It creates 71 outdoor
products across Sand & Water Play, Nature & Planting, Outdoor Art & Creative,
Outdoor Living, Outdoor Role Play, Outdoor Traffic, and Outdoor Custom
Products. It includes the source USD reference prices, dimensions, materials,
and the matching PDF-extracted product pictures where the catalogue contains a
product image. The source PDF repeats three model codes; the importer safely
uses the CRM SKUs `JT-06-UNICYCLE`, `JT-06-SET`, `JT-07-CRANE`,
`JT-07-SET`, and `G3-BLACKBOARD` for the distinct products while preserving
the printed model code in the description. Product pictures supplied after the
catalogue import are also mapped for `HW-02`, `HW-04`, `YS-04`, and `ZZ-04`.
Existing SKU records and images are preserved, so rerunning the import is safe.

```bash
docker compose up -d --build
docker compose exec backend python scripts/import_outdoor_playthings_catalog.py
```

To attach only the four late-supplied images for `HW-02`, `HW-04`, `YS-04`,
and `ZZ-04`, use the targeted, idempotent maintenance script instead:

```bash
docker compose exec backend python scripts/attach_late_outdoor_images.py
```

For the deployed Neon database, run the same script with the local
`DATABASE_URL` environment variable that was used for production migrations:

```powershell
docker compose run --rm --no-deps -e DATABASE_URL=$env:DATABASE_URL backend python scripts/attach_late_outdoor_images.py
```

The backend startup runs `scripts/ensure_alembic_version.py` before `alembic upgrade head`. This keeps the Alembic version table able to store long revision IDs such as the V4 migration. The repair migration is `0012_expand_alembic_version`; existing migration files remain unchanged.

The matching catalogue images are stored under `frontend/public/product-images`. After rebuilding the frontend, run `docker compose exec backend python scripts/import_product_images.py` to attach the 45 image URLs to products. The image importer preserves any product that already has an image; set `PRODUCT_IMAGE_BASE_URL` when the frontend is hosted at a different public URL.

Quotations can be created either from an opportunity and its product lines, or directly from a Customer Center. A customer-originated quotation creates or links its sales opportunity in the same transaction: it reuses only one active opportunity with the same customer, currency, and exact product set; ambiguous, closed, or different-product projects create a new opportunity instead. New quote opportunities are assigned to the logged-in user, start at `Quoted` / `Quotation Sent`, use the existing stage probability rule, and copy the quotation's products, quantities, prices, and final amount (including shipping). Each immutable internal snapshot stores SKU, product name, picture, unit-price, quantity, and line-total data, so later catalog edits do not alter historical quotations. A Draft can be edited and regenerated; marking it Sent locks that snapshot. Further changes create a new immutable snapshot while retaining the previous history. New quotation numbers use `SLQ-YYYYMMDD-N`, where `N` starts at `1` each China business day and is allocated from the highest existing numeric suffix for that day. Historical quotation numbers remain unchanged. Customer-facing quotation pages, PDF exports, and Excel exports show the quotation number and date without exposing internal revision identifiers. Generated PDFs use the StarLink company header and the requested `Item Name / Picture / Unit Price / QTY / Total Price` table, followed by product total, door-to-door shipping, amount, validity, payment term, and delivery time. The PDF files are persisted in the Docker `quotation_pdfs` volume and downloaded through an authenticated API endpoint.

When editing a quotation, the product picker supports a server-backed search
by SKU, product name, or material. Type a search term and matching products are
shown directly in the page; click a result to add it to the draft. Products
already on the draft are excluded from the results.
The quotation editor keeps the search control on the left and a fixed-height,
independently scrollable result pane on the right, so searching or adding a
product does not move the quotation table.
To add a group of catalogue items, enter up to 50 SKU models separated by
spaces, commas, or line breaks, then use **Add all results**. Existing quotation
lines are never duplicated.

Customer-originated quotations use the same live product catalogue and now
include a dedicated multi-product picker. Search by exact SKU, product name,
category, material, or description; pasted SKU models can be separated by
spaces or commas. Product-name words are also evaluated as consecutive phrases
so names such as `Pink Tower` and `Brown Stair` remain searchable in one
request. Results are capped at 50 products, can be selected in bulk, and never
add a product ID that is already on the quotation. Each selected line retains
its own editable unit price and quantity before the existing quotation,
opportunity-sync, PDF, and Excel workflows run.

Apply `0017_v10_sales_followup_reminders` and the additive repair migration
`0018_repair_v10_opportunity_reminder_schema` on databases that may have a
stale Alembic stamp. The repair only adds missing V10 reminder columns and
preserves existing customer, opportunity, inquiry, quotation, and follow-up
data.

Quotation PDF generation resolves URLs under `/product-images/` from the backend's local `PRODUCT_IMAGE_DIR` (default `/app/product-images`) before attempting public HTTP images. The backend Docker image copies the catalog image assets so product pictures remain available inside containers.

When saving a draft, blank payment terms, delivery time, currency, or shipping cost values are normalized to the configured defaults; product prices and quantities remain strictly validated.
Quotation draft updates keep nested product inputs as validated Pydantic objects through the service layer, preventing item updates from becoming unhandled 500 errors.

Each quotation can also be downloaded as an editable Excel workbook through
`GET /quotations/{id}/excel?version_no={version}` or the **下载 Excel** button
on the quotation detail page. Excel exports are generated from the selected
immutable snapshot and keep the product name/SKU, picture,
unit-price, quantity, shipping cost, validity, payment terms, and delivery
time. The editable cells are highlighted in yellow, and line totals, product
total, and final amount remain Excel formulas so they recalculate after local
edits. Downloading Excel is read-only and does not change the quotation,
stored snapshot, or PDF.

The first-phase Alibaba integration accepts simulated inquiries through an authenticated endpoint. It always sets the Customer `source` and `source_platform` to `Alibaba`, regardless of submitted source data. Existing customers are returned instead of duplicated when a case-insensitive email match or company-and-contact match is found. The Settings page exposes connection state and a simulation button. No database migration is required for this integration phase; see [docs/alibaba-integration.md](docs/alibaba-integration.md) for the future production-authentication boundary.

Run API tests after installing backend development dependencies:

```bash
cd backend
pytest
```

## Frontend CRM interface

The React frontend includes login, dashboard, Alibaba inquiry list/detail/creation/conversion, opportunity list/detail/creation/update, product list/detail/creation/editing, quotation list/detail/PDF workflows, data-source settings, customer list, customer detail, customer creation, and follow-up creation pages. The product library supports search, category and active-state filters, URL image management, and enable/disable actions. Opportunity details support product lines with quantity and target price and provide the `Create Quotation` action. The Dashboard separates today's reminders from overdue customers and includes scoped opportunity statistics. Set `VITE_API_BASE_URL` in `frontend/.env` if the backend is not running at the local default, then run `npm install` and `npm run dev` from `frontend/`.

Quotation exports read public company details from the centralized backend settings. The
following defaults are included for StarLink and can be overridden by deployment
environment variables when necessary:

```text
COMPANY_NAME=Dalian StarLink International Trade Co., Ltd.
COMPANY_ALIBABA_STORE=https://starlinkforkids.en.alibaba.com
COMPANY_WEBSITE=https://dlstarlink.com
COMPANY_EMAIL=starlink_george@foxmail.com
COMPANY_WHATSAPP=+86 17640412406
```

Quotation PDFs show the Alibaba Store and Company Website on separate lines. They use the packaged StarLink wordmark at `backend/app/assets/starlink-logo.png`, with a print-safe text fallback if the asset is unavailable; the visible left edge of the logo is aligned to the company-information grid below it. Product rows use fixed-size, vertically centered pictures, with the product name/SKU hierarchy and numeric columns aligned for business quotation readability; the totals and formal terms section follow the same template. The template before this branded redesign is preserved in Git tag `quotation-template-pre-logo-20260811` for rollback.
Older `.env` files that stored the two website links as `Alibaba URL&Company URL` are split automatically for backward compatibility; new deployments should use the two explicit variables above.

### Full local stack with Docker

```bash
cp .env.example .env
docker compose up --build
```

The backend image installs its explicit runtime dependency list from `backend/requirements.txt`; it does not build the local Python package during image construction.

### 客户档案表导入

“客户管理”以 Excel 工作表 **客户档案表** 的 20 个字段为业务标准。`0019_customer_archive_fields` 只新增可空字段和索引，不会删除 `customers`、改写客户 ID，或破坏 contacts、opportunities、quotations、inquiries、followups 的 `customer_id` 关联。已有 CRM 的销售阶段只会被映射到新的“跟进阶段”展示字段；原有枚举字段仍保留给旧页面和 Dashboard 使用。

客户管理列表以每页 10 位客户显示档案表的核心字段；表格顶部的横向滚动条与数据表同步，便于在页首查看所有列。列表同时提供页码、总页数和跳页输入框。`GET /api/v1/customers` 未传 `limit` 时默认返回 10 位客户；其他模块仍可显式传入所需的安全页大小。

新增及编辑客户档案会严格使用工作簿的数据验证选项。工作簿没有 Named Range 或隐藏 Sheet 选项源；所有下拉选项直接定义在“客户档案表”中，且均允许为空。

| 字段 | Excel 下拉选项（原顺序） |
| --- | --- |
| 来源 | 询盘、RFQ、访客营销、中国制造、FB、INS、领英、开发信、WhatsApp、客户介绍 |
| 客户类型 | 幼儿园、网店、实体店、个人 |
| 兴趣产品 | 家具、蒙氏、木制玩具、皮克勒、学习塔、其它 |
| 客户等级 | 1、2、3、4 |
| 客户体量 | 1、2、3、4 |
| 跟进阶段 | 新客户未回复、沟通中、已报价、已成交样品、已成交、已复购 |

| Excel 字段 | CRM 字段 |
| --- | --- |
| 获得客户时间、来源、客户名、公司名、职位、备注、国家 | `customer_acquired_at`、`source`、`contact_name`、`company_name`、`position`、`notes`、`country` |
| 客户类型、兴趣产品、WhatsApp、邮箱、电话 | `customer_type`、`interested_product`、`whatsapp`、`email`、`phone` |
| 客户等级、客户体量、客户总分 | `customer_level_value`、`customer_size`、`customer_total_score` |
| 跟进阶段、自动阶段判断、最近跟进日期 | `followup_stage`、`automatic_stage_judgement`、`latest_followup_date` |

先进行无数据库的只读预检：

```powershell
docker compose exec backend python scripts/import_customer_archive.py /tmp/George外贸工作表.xlsx --validate-only
```

在本地 Docker 数据库执行实际导入前，先应用迁移，再把上传文件复制到 backend 容器。导入按保存的 Excel 行键、完全一致的邮箱、完全一致的 WhatsApp 或完整的“公司名+客户名+国家”精确匹配，因此可安全重复执行，且不会做模糊合并。

```powershell
docker compose up -d --build
docker compose exec backend alembic upgrade head
$backendContainer = docker compose ps -q backend
docker cp "C:\Users\1\Desktop\George外贸工作表.xlsx" "${backendContainer}:/tmp/George外贸工作表.xlsx"
docker compose exec backend python scripts/import_customer_archive.py /tmp/George外贸工作表.xlsx
```

脚本会输出 Excel 总行数、空白/公式行、有效客户、明确重复、新增、更新、失败行及 CRM 最终客户数。空单元格保持 `null`；电话和 WhatsApp 一律按文本导入，不会转换成科学计数法。

## Project layout

## Customer archive filtering and export

The customer-management page supports combined archive-field filters while
keeping pagination fixed at 10 results per page. Date fields accept inclusive
from/to values; the Excel-validated archive fields use the same controlled
options as customer create and edit forms.

Use **Export all customers** to download every customer record accessible to
the signed-in user as a real `.xlsx` workbook. The workbook contains one
`客户档案表` sheet, preserves Chinese and special characters, exports WhatsApp
and telephone values as text, and safely escapes values that Excel could treat
as formulas. Timezone-aware PostgreSQL timestamps are converted to China
business time and made timezone-free only in the generated workbook, which
keeps the export compatible with Excel without changing stored data. The
export is read-only: it does not alter customers or their commercial
relationships.

## Customer follow-up reminders V1

The **Follow-up reminders** page applies only to customer archive records whose
`customer_acquired_at` (**获得客户时间**) is on or after **2026-08-12**. Earlier
records and records without that archive date remain available for normal CRM
and manual follow-up work, but are excluded from V1 reminder dates, reminders,
the reminder queue, and its Dashboard statistics. Eligible records calculate a
live follow-up queue from `latest_followup_date` and `followup_stage`. The
approved cadence is: 新客户未回复 2 days, 沟通中 1 day, 已报价 and 已成交样品
3 days, 已成交 7 days, and 已复购 30 days. The system always uses the China
(`Asia/Shanghai`) business date, so Vercel's UTC runtime cannot move a
reminder to the wrong calendar day. `冷客户` is no longer a manually selectable
follow-up stage: when `latest_followup_date` is more than 30 days before the
China business date, it dynamically overrides the displayed
`automatic_stage_judgement`. Exactly 30 days is not cold, and no date does not
become cold automatically.

Suggested dates and reminder statuses are deliberately calculated at read
time; they are not stored in the database. An eligible customer with no latest
follow-up is shown as **尚未跟进** and included in the action queue. Creating or
editing a follow-up record updates `customers.latest_followup_date` to the
record's follow-up date, which immediately starts the next cadence cycle.
Legacy manual `next_followup_date` values remain untouched for compatibility.
The historical `response_status` and `followup_requirement` database columns
are retained for compatibility only; the customer archive no longer displays,
filters, edits, or exports them.

Customer responses preserve historical `followup_stage` text so an older
archive value (for example, `已发目录`) cannot make the customer list fail.
The six approved stages are enforced only when creating or editing a customer;
editing an older customer presents only those six choices and changes the
stage only when the user saves a new selection.

## Business analytics

The **经营分析** page is read-only and defaults to the current month. It supports
today, week, month, year, and inclusive custom-date ranges using the
`Asia/Shanghai` business date. New-customer indicators use the archive field
`customers.customer_acquired_at` only—never CRM creation or import timestamps.
Quotation counts and amounts use each quotation's current version exactly once;
amounts are grouped by currency rather than being converted or added together.
Won amount uses a won opportunity's latest quotation `total_amount` when the
database has no separate actual-revenue field. The page also provides aggregated
trends, source/country/product/customer-type analysis, the compatible customer
follow-up-stage funnel, and the existing follow-up reminder summary. Admin sees
all accessible data, Sales sees only records it owns, and Viewer has read-only
access. No analytics snapshot table or migration is needed.

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
