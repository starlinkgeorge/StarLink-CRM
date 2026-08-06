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

Companies managed by sales: `id`, `company_name`, `contact_name`, `country`, `email`, `phone`, `whatsapp`, `website`, `source`, `level`, `status`, `owner_id`, `created_at`, and `updated_at`.

- `level`: `A`, `B`, or `C` (default `C`).
- `status`: `Lead`, `Contacted`, `Quotation`, `Negotiation`, `Won`, or `Lost` (default `Lead`).
- `owner_id` is optional and references `users.id`.

### `contacts`

Named contacts for a customer: `id`, `customer_id`, `name`, `position`, `email`, `phone`, `whatsapp`, and `created_at`. `customer_id` is required.

### `tags` and `customer_tags`

Reusable customer labels. `tags` contains `id`, unique `name`, and `created_at`. `customer_tags` contains `customer_id` and `tag_id`; together they form a composite primary key that prevents duplicate tag assignments.

### `followups`

Sales activity records: `id`, `customer_id`, `user_id`, `type`, `content`, `next_followup_date`, and `created_at`. Types are `Email`, `WhatsApp`, `Phone`, and `Meeting`.

### `refresh_tokens`

Revocable login-session records: `id`, `user_id`, unique `token_hash`, `expires_at`, `revoked_at`, and `created_at`. The raw JWT refresh token is never persisted. `users.last_login_at` records the most recent successful login.

## Relationships

```text
users 1 ──< customers (owner_id; SET NULL on user deletion)
users 1 ──< followups (user_id; deletion restricted to preserve history)
customers 1 ──< contacts (deleted with customer)
customers 1 ──< followups (deleted with customer)
customers >──< tags (through customer_tags)
users 1 ──< refresh_tokens (deleted with user)
```

`users.updated_at` and `customers.updated_at` are updated by PostgreSQL triggers, including when maintenance SQL changes a record directly. Foreign-key columns and common filtering fields are indexed.
