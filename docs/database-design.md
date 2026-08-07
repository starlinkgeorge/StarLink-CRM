# CRM database design — phase 1

## Principles

- PostgreSQL is the source of truth; only the backend connects to it.
- Primary keys use PostgreSQL `BIGINT` identities, and timestamps are timezone-aware.
- Roles, customer levels, customer statuses, and follow-up types are database enums.
- Customer source is deliberately extensible text (e.g. Alibaba, Google, Facebook, LinkedIn, Website).

## Tables

### `users`

Application users who own customers and record follow-ups: `id`, `name`, unique `email`, `password_hash`, `role`, `created_at`, and `updated_at`. Roles are `Admin`, `Sales`, and `Viewer`; the default is `Sales`.

### `customers`

Companies managed by sales: `id`, `company_name`, `contact_name`, `country`, `email`, `phone`, `whatsapp`, `website`, `customer_type`, `source`, `interested_product`, `level`, `status`, `sales_stage`, `owner_id`, `created_at`, and `updated_at`.

- `customer_type`: optional business classification such as Kindergarten, School, Distributor, or Retailer.
- `source`: optional acquisition channel such as Alibaba, Website, Facebook, or LinkedIn.
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
customers >──< tags (through customer_tags)
users 1 ──< refresh_tokens (deleted with user)
```

`users.updated_at` and `customers.updated_at` are updated by PostgreSQL triggers, including when maintenance SQL changes a record directly. Foreign-key columns and common filtering fields are indexed.
