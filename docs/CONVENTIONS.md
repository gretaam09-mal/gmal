# Conventions

Non-negotiable rules for all work on Provision, from Phase 1 onward. These
are not defaults to override with a comment — if a change requires breaking
one of these, stop and raise it rather than working around it.

## 1. All arithmetic lives in `engine/`

Every number that reaches a user — an exposure figure, a quantified impact,
a diff between two versions — is computed by a pure, deterministic function
in `backend/engine/` (`predicates/`, `impact/`, `diff/`). These packages do
no I/O: no network calls, no database access, no filesystem, no wall-clock
reads, no calls to an LLM. Same input, same output, every time.

The LLM never computes a number. It can extract facts from documents and
write narrative text around a figure the engine already produced, but it
never performs the arithmetic itself. If a number appears in a memo, there
must be an `engine/` call that produced it and a test that pins it.

## 2. Approved records are immutable

Once a memo, exposure computation, or review decision is approved, its
content does not change in place. A correction is a new version with a
recorded diff against the one it supersedes, not a mutation of approved
rows. This applies at the database layer (approved rows are not updated by
application code) and at the API layer (no endpoint accepts an edit to an
approved record).

## 3. No database query without tenant scoping

Provision is multi-tenant. Every query against tenant data goes through
tenant-scoped access (see `backend/db/session.py::tenant_session`) — never
a raw session that could cross tenant boundaries. Row-level security in
Postgres is the backstop, not the only line of defence: application code
must still scope every query explicitly.

## 4. One feature per branch, a human merges every pull request

Branches are scoped to a single feature or fix — no bundling unrelated
changes to save a review cycle. No pull request merges itself or gets
merged by automation; a human reviews and merges every one, including PRs
opened by an agent.
