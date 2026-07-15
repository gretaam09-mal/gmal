# Deploying a free preview (Render + Clerk)

`render.yaml` at the repo root is a Render Blueprint: applying it creates all
three pieces of the stack — Postgres, the backend API, and the frontend — in
one go, under one free Render account.

## Order of operations

1. Create a Render account and apply the Blueprint (`render.yaml`). Both web
   services will build and deploy successfully even with the secret env vars
   still blank — the app fails closed (no crash, sign-in just says "not
   configured yet") rather than needing every key up front.
2. Once `provision-api` is live, copy its URL from the Render dashboard and
   set it as `NEXT_PUBLIC_API_URL` on `provision-web`. Render redeploys the
   frontend automatically when you save an environment variable.
3. Once `provision-web` is live, copy its URL and set it as
   `PROVISION_CORS_ALLOWED_ORIGINS` on `provision-api`, so the browser is
   allowed to call the API cross-origin.
4. Create a Clerk application (see `docs/runbooks/clerk-setup.md`) and set
   `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` + `CLERK_SECRET_KEY` on `provision-web`,
   and `PROVISION_CLERK_JWKS_URL` + `PROVISION_CLERK_ISSUER` on `provision-api`.
5. Optionally set `PROVISION_COMPANIES_HOUSE_API_KEY` on `provision-api` (see
   `docs/runbooks/companies-house-setup.md`) — only needed for the
   auto-fill button, not for the app to run.
6. To reach the internal `/admin` instrument-onboarding workbench, set
   `PROVISION_ADMIN_EMAILS` on `provision-api` to your email (comma-separate
   for more than one) and sign in again — see
   `docs/runbooks/anthropic-setup.md` "Staff access to the workbench".

## Known limitations of this free setup

- Render's free web services spin down after 15 minutes idle and take ~30-60s
  to wake back up on the next request — the first click after a break will be
  slow, that's expected.
- Render's free Postgres database is deleted 30 days after creation (with a
  14-day grace period to upgrade first). Fine for a preview; not for anything
  you want to keep.
- Whether Render's database user is a true Postgres superuser (which would
  bypass the Row-Level Security tenant isolation described in
  `docs/adr/0001-clerk-for-authentication.md` and the `row_level_security`
  migration) isn't confirmed. Isolation is verified by the automated test
  suite against a known-non-superuser role; treat it as unverified on this
  specific free tier until checked, and don't rely on this deployment for
  anything with real multi-tenant data.
