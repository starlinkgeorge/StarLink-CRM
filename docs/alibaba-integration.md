# Alibaba inquiry integration

## Current simulation boundary

StarLink CRM exposes `POST /api/v1/integrations/alibaba/inquiries` as the stable inbound contract for Alibaba International Station inquiries. The first phase does not call Alibaba APIs and does not claim to be connected. It uses the existing CRM JWT authentication so Admin and Sales users can exercise the contract from the Settings page; Viewer users cannot ingest data.

The companion `GET /api/v1/integrations/alibaba/status` endpoint currently returns `connected: false` and `mode: simulation`.

## Normalization and customer matching

- `source` is always stored as `Alibaba`; an inbound source value is accepted for contract compatibility but ignored.
- A new inbound inquiry creates a Customer with `source_platform = Alibaba`, its original inquiry content, and a primary Contact.
- Leading and trailing whitespace is removed from inbound text.
- A non-empty email is matched case-insensitively against existing customers first.
- If no email match exists, company name plus contact name is matched case-insensitively.
- A duplicate response returns the existing `customer_id` and full Customer payload with `created: false`.
- A new customer response uses `created: true`.

## Production connection work

Before enabling a real Alibaba connection, replace CRM JWT authentication on the inbound machine-to-machine route with a dedicated integration credential and Alibaba callback-signature verification. Add replay protection, request IDs, retry-safe persistence, encrypted credential storage, structured audit logs, and rate limiting. The inbound payload should still pass through the same service-level normalization and customer-matching path.
