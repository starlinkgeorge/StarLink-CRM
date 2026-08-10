# Production deployment: Vercel + Neon

This guide deploys StarLink CRM as two Vercel projects and one Neon PostgreSQL
database. The existing Docker Compose stack remains the local-development
environment and is not used by the cloud deployment.

## Target architecture

| Component | Production service | Source root | Persistent data |
| --- | --- | --- | --- |
| Frontend | Vercel static Vite deployment | `frontend` | None |
| API | Vercel Python / FastAPI function | `backend` | Neon + Vercel Blob |
| Database | Neon PostgreSQL | N/A | Neon PostgreSQL |
| Attachments | Vercel Blob (private) | N/A | Vercel Blob |

The frontend's `public/product-images` directory is published as static Vite
assets. The backend uses `PRODUCT_IMAGE_BASE_URL` when creating catalogue image
links or rendering quotation PDFs.

## Before deploying

1. Keep the current Docker `.env` for local development; do not replace it
   with production values.
2. Copy `.env.production.example` to a safe location outside Git and replace
   every placeholder.
3. Create a Neon database and copy its pooled PostgreSQL connection string.
   Set `DATABASE_URL` to the same string with the `postgresql+psycopg://`
   scheme (the API and Alembic also accept Neon’s standard `postgresql://`
   form and normalize it automatically).
4. Create a Vercel Blob store, connect it to the backend project, and use its
   `BLOB_READ_WRITE_TOKEN`. Follow-up attachments are private and can only be
   downloaded through the authenticated CRM API.
5. Generate a unique `JWT_SECRET_KEY` with at least 32 random characters.
   Do not reuse the local development key.

## Apply the database schema first

Do **not** rely on a Vercel function startup to run migrations. It can race
across serverless instances and make an application deployment mutate the
database unexpectedly.

From the repository root in PowerShell, set the Neon connection string only in
the current terminal, then run the migration using the existing backend image:

```powershell
$env:DATABASE_URL = 'postgresql+psycopg://<neon-user>:<neon-password>@<neon-host>/<database>?sslmode=require'
docker compose run --rm --no-deps -e DATABASE_URL=$env:DATABASE_URL backend alembic upgrade head
docker compose run --rm --no-deps -e DATABASE_URL=$env:DATABASE_URL backend alembic current
Remove-Item Env:DATABASE_URL
```

The second command must show the current Alembic head. Back up the Neon branch
or database before applying a future production migration.

## Deploy the FastAPI backend

1. Create a Vercel project from this repository.
2. Set **Root Directory** to `backend`.
3. Vercel discovers `backend/server.py`, which exports the FastAPI `app`.
   No `vercel.json` is required for this backend entrypoint.
4. In the Vercel project’s **Production** environment variables, add the
   backend entries from `.env.production.example`:

   - `APP_ENV=production`
   - `DATABASE_URL`
   - `DATABASE_POOL_MODE=null`
   - `CORS_ORIGINS` (the final frontend URL only; comma-separate intentional
     additional origins)
   - `JWT_SECRET_KEY`, token durations, and company contact values
   - `PRODUCT_IMAGE_BASE_URL` (the final frontend URL plus `/product-images`)
   - `FILE_STORAGE_BACKEND=vercel_blob` and `BLOB_READ_WRITE_TOKEN`

5. Deploy. Confirm this URL returns JSON:

```text
https://<your-backend>.vercel.app/api/v1/health
```

`server.py` validates production secrets at startup and deliberately does not
run Alembic. A missing production setting fails the deployment instead of
silently serving against an incomplete configuration.

## Deploy the React frontend

1. Create a second Vercel project from the same repository.
2. Set **Root Directory** to `frontend` and let Vercel detect Vite.
3. Set the **Production** environment variable:

   ```text
   VITE_API_BASE_URL=https://<your-backend>.vercel.app/api/v1
   ```

4. Deploy after the backend URL is final. `frontend/vercel.json` provides the
   SPA rewrite required for direct visits to `/customers/123`, `/quotations/5`,
   and other client routes.

The `VITE_` variable is compiled into the frontend build. Redeploy the frontend
whenever the backend domain changes.

## Storage behavior

- Docker development defaults to `FILE_STORAGE_BACKEND=local` and retains the
  existing `followup_attachments` volume.
- Production uses `FILE_STORAGE_BACKEND=vercel_blob`; attachments are stored as
  opaque private Blob URLs, never as paths on the serverless filesystem.
- Quotation PDF downloads are regenerated in memory from the immutable
  quotation-version data. No `uploads` directory or Docker PDF volume is needed
  by Vercel. Excel downloads are already generated in memory.
- Do not use `FILE_STORAGE_BACKEND=local` in production. Vercel function disks
  are ephemeral and cannot provide durable attachment storage.

## Production smoke test

After both deployments finish:

1. Visit the frontend URL and log in with a production administrator account.
2. Load Dashboard, Customers, Opportunities, Pipeline, Quotations, Products,
   Inquiries, and a Customer Center page.
3. Add a small follow-up attachment, download it, and delete it. Verify the
   object appears in the Vercel Blob store and no file was written to a local
   project directory.
4. Create or open a draft quotation, generate and download its PDF and Excel
   files, and verify product images display in both files.
5. In the browser Network panel, verify requests use the configured Vercel API
   host and none use a local address.
6. Confirm a second browser tab can refresh an expired access token without
   requiring the user to log in again.

## Rollback

- Roll back a Vercel deployment from the Vercel dashboard; frontend and backend
  can be rolled back independently.
- Do not roll back a database migration merely because application code was
  rolled back. First restore a compatible application release or use a tested
  Alembic downgrade after confirming the data impact.
- Retain production environment variables and Blob store credentials outside
  source control.

## Vercel free-plan notes

Vercel’s FastAPI Python runtime is serverless. Keep the production API
stateless, use Neon connection pooling (`DATABASE_POOL_MODE=null` in this
application), and monitor execution duration for unusually large quotation PDFs
or attachment transfers. Vercel Blob supports public and private object stores;
StarLink CRM uses the private mode so authenticated downloads remain under API
access control.
