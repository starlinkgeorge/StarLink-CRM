# StarLink CRM database design – V8

## Principles

- PostgreSQL is the source of truth; only the backend connects to it.
- Primary keys use PostgreSQL `BIGINT` identities, and timestamps are timezone-aware.
- Roles, customer levels, customer statuses, and follow-up types are database enums.
- Customer source is deliberately extensible text (e.g. Alibaba, Google, Facebook, LinkedIn, Website).

## Tables

### `users`

Application users who own customers and record follow-ups: `id`, `name`, unique `email`, `password_hash`, `role`, `created_at`, and `updated_at`. Roles are `Admin`, `Sales`, and `Viewer`; the default is `Sales`.

### `customers`

Companies managed by sales: `id`, `company_name`, `contact_name`, `country`, `email`, `phone`, `whatsapp`, `website`, `customer_type`, `source`, `source_platform`, `original_inquiry`, `interested_product`, `level`, `status`, `sales_stage`, `owner_id`, `created_at`, and `updated_at`.

- `customer_type`: optional business classification such as Kindergarten, School, Distributor, or Retailer.
- `source`: optional acquisition channel such as Alibaba, Website, Facebook, or LinkedIn.
- `source_platform`: optional originating marketplace or system, such as Alibaba International. Existing rows are backfilled from `source` where that value is available.
- `original_inquiry`: optional immutable-at-conversion copy of the source inquiry content; it is nullable so existing customer records remain compatible.
- `interested_product`: optional free-text summary of the products requested by the customer.
- `level`: `A`, `B`, or `C` (default `C`).
- `status`: `Lead`, `Contacted`, `Quotation`, `Negotiation`, `Won`, or `Lost` (default `Lead`).
- `sales_stage`: the V3-facing sales stage. It uses the same values as `status`; the service keeps both fields synchronized so V2.2 dashboard queries remain compatible.
- `owner_id` is optional and references `users.id`.

### `contacts`

Named contacts for a customer: `id`, `customer_id`, `name`, `position`, `email`, `phone`, `whatsapp`, and `created_at`. `customer_id` is required.

### `tags` and `customer_tags`

Reusable customer labels. `tags` contains `id`, unique `name`, and `created_at`. `customer_tags` contains `customer_id` and `tag_id`; together they form a composite primary key that prevents duplicate tag assignments.

### `followups`

Sales activity records: `id`, `customer_id`, `user_id`, `type`, `content`, `next_followup_date`, and `created_at`. Types are `Email`, `WhatsApp`, `Phone`, and `Meeting`. The optional `next_followup_date` is also the reminder date. The latest follow-up row for a customer defines its active reminder; older dates remain immutable history and are not counted again after a newer follow-up is recorded.

### `customer_status_history`

Immutable sales-stage audit records: `id`, `customer_id`, nullable `old_status`, required `new_status`, nullable `changed_by_id`, and `created_at`. A row is added only when `status`/`sales_stage` actually changes. Customer creation and follow-up activities remain in their source tables and are combined with these rows by the read-only timeline API.

### `inquiries`

V8 external marketplace inquiries: `id`, UUID `public_id`, nullable `customer_id`, nullable unique `converted_opportunity_id`, `company_name`, `contact_name`, `country`, `email`, `phone`, `whatsapp`, `source`, `source_platform`, `interested_product`, `inquiry_content`, `status`, `created_at`, and `updated_at`.

- `source` records the acquisition channel (for example `Alibaba`); `source_platform` identifies the external system or marketplace (for example `Alibaba International`). Both are required for new inquiries and default to `Alibaba`.
- `inquiry_content` preserves the original incoming message. It is required even when an inquiry is entered manually, making the payload suitable for a future Alibaba API adapter.
- `status` is constrained to `New`, `Processing`, `Converted`, or `Closed`. A closed Inquiry must be reopened before conversion; a converted Inquiry is immutable.
- Conversion atomically creates one customer, its primary contact, and one opportunity. `converted_opportunity_id` is unique, preventing repeat conversions, while `customer_id` preserves a direct audit link.

### `opportunities`

The sales-opportunity record: `id`, UUID `public_id`, `customer_id`, nullable `owner_id`, `name`, `interested_product`, `inquiry_content`, `amount`, three-letter `currency`, `expected_close_date`, legacy `stage`, V7 `sales_stage`, `probability`, `next_action`, `created_at`, and `updated_at`. Monetary values use `NUMERIC(14,2)` and are aggregated by currency.

- `amount` is the estimated opportunity amount; `expected_close_date` is the estimated close date.
- `probability` is a constrained integer from 0 through 100.
- `next_action` is an optional short, actionable note for the next sales step.
- `sales_stage` is the V7 pipeline: `New Lead`, `Contacted`, `Requirement Confirmed`, `Quotation Sent`, `Negotiation`, `Won`, or `Lost`.
- `stage` remains the V3 enum (`Lead`, `Qualified`, `Proposal`, `Negotiation`, `Won`, `Lost`) for client compatibility. The service maps changes in either field to the other field.

### `opportunity_stage_history`

Immutable opportunity stage changes: `id`, `opportunity_id`, nullable `old_stage`, required `new_stage`, nullable `changed_by_id`, and `created_at`. Initial creation is represented by a row with `old_stage = NULL`; every later stage change appends another row.

### `opportunity_sales_stage_history`

V7 immutable sales-pipeline changes: `id`, `opportunity_id`, nullable `old_sales_stage`, required `new_sales_stage`, nullable `changed_by_id`, and `created_at`. Existing opportunities are backfilled with one initial V7 stage record during migration `0014_v7_sales_pipeline`; later stage changes append new records.

### `product_categories`

Hierarchical product classifications: `id`, `name`, nullable self-referencing `parent_id`, and `sort_order`. Removing a parent leaves child categories in place and clears their `parent_id`.

### `products`

The export product catalog: `id`, unique `sku`, `name`, nullable `category_id`, `material`, `dimension_text`, metric dimensions (`length_mm`, `width_mm`, `height_mm`), `weight_kg`, `unit`, `moq`, `reference_price`, three-letter `currency_code`, `description`, `is_active`, `created_at`, and `updated_at`. Exact numeric columns avoid floating-point price and measurement errors. Inactive products remain available to historical opportunities.

### `product_images`

URL-based product images: `id`, `product_id`, `image_url`, `is_primary`, `sort_order`, and `created_at`. A partial unique index permits no more than one primary image per product. Images are deleted with their product.

### `opportunity_products`

Commercial line items joining opportunities and products: composite key (`opportunity_id`, `product_id`), `quantity`, and nullable `target_price`. The composite key prevents duplicate product lines; quantity and target price are opportunity-specific and do not alter the product reference price.

### `quotations`

The quotation master record: `id`, unique `quotation_number`, `customer_id`, nullable `opportunity_id`, `status`, `current_version`, `created_at`, and `updated_at`. Status values are `Draft`, `Sent`, `Accepted`, `Rejected`, and `Expired`. The master points to the editable/current version while preserving every prior version.

### `quotation_versions`

Immutable version headers: `id`, `quotation_id`, `version_no`, `currency`, `payment_term`, `delivery_time`, `validity_days`, `shipping_cost`, `subtotal`, `total_amount`, `pdf_url`, and `created_at`. (`quotation_id`, `version_no`) is unique. Only the current Draft may be edited; a sent version is copied into a new row for later revisions.

### `quotation_items`

Version-specific product snapshots: `id`, `quotation_version_id`, nullable `product_id`, `sku_snapshot`, `product_name_snapshot`, `picture_snapshot`, `unit_price`, `quantity`, and `line_total`. Catalog deletion clears only `product_id`; all snapshot fields remain unchanged for audit and PDF reproduction.

### `refresh_tokens`

Revocable login-session records: `id`, `user_id`, unique `token_hash`, `expires_at`, `revoked_at`, and `created_at`. The raw JWT refresh token is never persisted. `users.last_login_at` records the most recent successful login.

## Relationships

```text
users 1 ──< customers (owner_id; SET NULL on user deletion)
users 1 ──< followups (user_id; deletion restricted to preserve history)
users 1 ──< customer_status_history (changed_by_id; SET NULL on user deletion)
customers 1 ──< contacts (deleted with customer)
customers 1 ──< followups (deleted with customer)
customers 1 ──< customer_status_history (deleted with customer)
customers 1 ──< inquiries (customer_id; SET NULL on Customer deletion)
inquiries 1 ── 0..1 opportunities (converted_opportunity_id; SET NULL on Opportunity deletion)
customers 1 ──< opportunities (deleted with customer)
users 1 ──< opportunities (owner_id; SET NULL on user deletion)
opportunities 1 ──< opportunity_stage_history (deleted with opportunity)
users 1 ──< opportunity_stage_history (changed_by_id; SET NULL on user deletion)
opportunities 1 ──< opportunity_sales_stage_history (deleted with opportunity)
users 1 ──< opportunity_sales_stage_history (changed_by_id; SET NULL on user deletion)
product_categories 1 ──< products (category_id; SET NULL on category deletion)
product_categories 1 ──< product_categories (parent_id; SET NULL on parent deletion)
products 1 ──< product_images (deleted with product)
opportunities >──< products (through opportunity_products)
customers 1 ──< quotations (deletion restricted to preserve commercial records)
opportunities 1 ──< quotations (opportunity_id; SET NULL on opportunity deletion)
quotations 1 ──< quotation_versions (deleted with quotation)
quotation_versions 1 ──< quotation_items (deleted with version)
products 1 ──< quotation_items (product_id; SET NULL on product deletion)
customers >──< tags (through customer_tags)
users 1 ──< refresh_tokens (deleted with user)
```

`users.updated_at` and `customers.updated_at` are updated by PostgreSQL triggers, including when maintenance SQL changes a record directly. Foreign-key columns and common filtering fields are indexed.
