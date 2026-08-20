# Anthropic API setup (P-EXTRACT / P-PREDICATE-ASSIST / P-COMPOSE / P-DIFF-NOTE)

Four AI-assisted steps call the Anthropic API: extracting a structured
obligation from a clause in the instrument-onboarding workbench
(`ai/prompts/P-EXTRACT.v1.md`), drafting a predicate for expert review
(`ai/prompts/P-PREDICATE-ASSIST.v1.md`), composing an Impact Memo's prose
(`ai/prompts/P-COMPOSE.v1.md`), and summarising what changed between two
memo versions (`ai/prompts/P-DIFF-NOTE.v1.md`). No test, golden-set case, or
the `scripts/populate_sample_instruments.py` seed script makes a live call —
they all use the fixture-backed providers (see
`services/extraction/fixture_provider.py` and its siblings under
`services/composition/`, `services/predicate_assist/`, `services/diff_note/`),
so a key is only needed to actually onboard a *new* instrument or generate a
*new* Impact Memo through the app, not to run the test suite or CI.

## What to create

1. Create an account at [console.anthropic.com](https://console.anthropic.com/).
2. Create an API key.

## Where the key goes

Local backend (`backend/.env`, not committed):

```
PROVISION_ANTHROPIC_API_KEY=your-key-here
```

Deployed (Render): the `render.yaml` Blueprint declares
`PROVISION_ANTHROPIC_API_KEY` as a `sync: false` secret on `provision-api` —
Render prompts for it when you apply the Blueprint, or you can set/update it
later under that service's Environment tab.

Without it, `api/deps.py::get_extraction_provider` /
`get_predicate_assist_provider` / `get_composition_provider` /
`get_diff_note_provider` construct their respective `Anthropic*Provider`,
which raise a clear "not configured" error (surfaced to the UI as a 502 with
a message naming `PROVISION_ANTHROPIC_API_KEY`, via the global exception
handlers in `api/main.py`) rather than crashing the app — same fail-closed
shape as `services/companies_house`. An invalid key (rejected at call time)
or a transient Anthropic outage is caught the same way, by
`services/ai/anthropic_calls.py`, and also comes back as a clear 502 rather
than a raw SDK exception.

## Staff access to the workbench

The admin workbench (`/admin`) is gated by `User.is_staff`, which is
`False` for everyone by default — there's no self-serve way to become
staff. Two ways to grant it:

**`PROVISION_ADMIN_EMAILS`** (the deployed-app way): a comma-separated
allowlist of emails, e.g. `you@example.com,teammate@example.com`. Set it on
`provision-api` (in `render.yaml` it's declared as a `sync: false` secret —
blank by default, so nobody is elevated by this mechanism until you set it)
and sign in again — `api/deps.py::_maybe_elevate_to_staff` runs on every
authenticated request and sets `is_staff = True` the first time it sees a
matching email, writing an `auth.staff_granted_via_admin_emails` audit
event. It is elevation-only: it never sets `is_staff` back to `False`, so
removing an email from the list later does not revoke access (nothing in
this codebase auto-revokes staff) — the flag only unlocks the shared
reference-data routes under `/admin`; it carries no workspace `Role` and
does not touch tenant scoping or row-level security anywhere else.

**`scripts/grant_staff.py`** (local dev, or to revoke): after signing in
once, so a `User` row exists —

```
cd backend
poetry run python -m scripts.grant_staff you@example.com
poetry run python -m scripts.grant_staff you@example.com --revoke
```
