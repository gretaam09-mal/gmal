# Clerk setup

Authentication is wired to Clerk (see `docs/adr/0001-clerk-for-authentication.md`)
but no Clerk application exists yet. Until one does, sign-in is disabled and the
API refuses every authenticated request — this is deliberate fail-closed
behaviour, not a bug.

## What to create

1. Go to [clerk.com](https://clerk.com) and create a free account (the free
   tier covers MFA and social connections — no paid plan needed for this).
2. Create a new Application, named e.g. "Provision" (or "Provision Dev" for a
   separate dev/staging app — recommended so local development doesn't touch
   production users).
3. **Enable Google and Microsoft sign-in**: Dashboard → *User & Authentication*
   → *Social Connections* → toggle on **Google** and **Microsoft**. Clerk's
   own shared OAuth credentials work for development; for production you'll
   want to supply your own Google/Microsoft OAuth app credentials in the same
   screen (each has a "Use custom credentials" toggle).
4. **Require MFA**: Dashboard → *User & Authentication* → *Multi-factor* →
   enable an MFA method (authenticator app is the simplest) and set
   enforcement so it's required, not optional, for all users.
5. Copy the keys from Dashboard → *API Keys*:
   - **Publishable key** (`pk_test_...` / `pk_live_...`)
   - **Secret key** (`sk_test_...` / `sk_live_...`)
   - **Frontend API URL** shown on the same page (e.g.
     `https://<your-app>.clerk.accounts.dev`) — the JWKS endpoint is this URL
     plus `/.well-known/jwks.json`.

## Where the keys go

Frontend (`frontend/.env.local`, not committed):

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

Backend (`backend/.env`, not committed):

```
PROVISION_CLERK_JWKS_URL=https://<your-app>.clerk.accounts.dev/.well-known/jwks.json
PROVISION_CLERK_ISSUER=https://<your-app>.clerk.accounts.dev
```

No code changes are required — `frontend/middleware.ts` and
`backend/services/auth/clerk.py` both read these at runtime and start
enforcing authentication as soon as they're set.

## The session token must include an email claim

By default, Clerk's session token (what `useAuth().getToken()` returns and
what `backend/services/auth/clerk.py::verify_clerk_token` decodes) carries
only `sub`, `sid`, `iss`, etc. — **no email address**, unless you add one.
This matters here specifically: `PROVISION_ADMIN_EMAILS` staff elevation
(`api/deps.py::_maybe_elevate_to_staff`) and invite-acceptance-by-email
(`api/routes/invites.py`) both key off `User.email`, which is populated
from that claim. Without it, every user's stored email is a synthetic
`{clerk_user_id}@users.provision.invalid` placeholder that can never match
a real address — `is_staff` will never flip no matter what
`PROVISION_ADMIN_EMAILS` says.

Fix it once in the Dashboard: *Sessions* → *Customize session token* → add

```json
{ "email": "{{user.primary_email_address}}" }
```

Existing users don't need to sign out — `get_current_user` re-syncs
`User.email` from the token's `email` claim on every request once Clerk
starts sending it (usually within the ~60s life of the next session
token), and `PROVISION_ADMIN_EMAILS` elevation runs immediately after that
sync in the same request.

**To check which of these is actually the problem** (env var not
deployed vs. email mismatch vs. the missing claim above), sign in and hit
`GET /me` — the response includes `email` (look for the
`@users.provision.invalid` placeholder pattern), `admin_emails_configured`
(false means the env var didn't reach this process — check it's set on
`provision-api` and that the service redeployed), and
`email_matches_admin_list` (false with `admin_emails_configured: true` and
a real email means the address just isn't on the list).
