# ADR 0001: Clerk for authentication

## Status

Accepted.

## Context

Provision needs authentication with MFA required and Google + Microsoft
sign-in, for deal teams at PE funds. We don't want to build and maintain
password storage, MFA enrolment, or OAuth broker flows ourselves in Phase 2.

## Decision

Use [Clerk](https://clerk.com) as the identity provider.

- Frontend: `@clerk/nextjs` — `clerkMiddleware()` guards the `(app)` and
  `(admin)` route groups; `(marketing)` and the sign-in/sign-up pages stay
  public. See `frontend/middleware.ts`.
- Backend: the API never talks to Clerk directly for login. It verifies
  the JWT Clerk issues (RS256, verified against Clerk's JWKS endpoint) on
  every request — see `backend/services/auth/clerk.py` and
  `backend/api/deps.py::get_current_user`. On first sight of a valid
  token, a `User` row is created keyed by Clerk's `sub` claim (JIT
  provisioning) — Provision does not mirror Clerk's user database.
- MFA and the Google/Microsoft social connections are **Clerk Dashboard
  configuration**, not code — see `docs/runbooks/clerk-setup.md` for the
  exact steps and why they can't be expressed in this repo.

## Consequences

- No Clerk application exists yet in this repo's CI/dev environment.
  `PROVISION_CLERK_JWKS_URL` is unset by default, and
  `services/auth/clerk.py` fails closed (`ClerkNotConfiguredError`) rather
  than accepting unverified tokens — the backend correctly refuses all
  authenticated requests until it's configured, instead of silently
  trusting anything. The frontend's Clerk middleware and provider are
  similarly no-ops when `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is unset, so
  CI (which only exercises the public marketing route and a component
  smoke test) doesn't need real keys — see `docs/runbooks/clerk-setup.md`.
- Tests exercise the real verification logic against a locally generated
  RSA keypair (`backend/tests/unit/test_clerk_auth.py`) and exercise
  every other route by overriding `get_current_user` with a test-only
  identity (`backend/tests/integration/conftest.py`) — no test depends on
  Clerk being reachable.
- Once real keys exist, no code changes are needed — only environment
  variables (see the runbook).
