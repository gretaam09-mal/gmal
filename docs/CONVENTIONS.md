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

**Narrow exception — AI cost estimation only.** When a binding obligation
has no expert-authored `CostTemplate`, `services/cost_estimate` may ask an
LLM to produce a best/likely/worst GBP figure and a rationale, scaled to
the specific company's profile (P-COST-ESTIMATE — see
`ai/prompts/P-COST-ESTIMATE.v1.md`). This is the **one** place in the
codebase an LLM is allowed to originate a number a user sees — every other
prompt (P-COMPOSE, P-DIFF-NOTE, P-PREDICATE-ASSIST) must reuse a figure
`engine/` already produced and never invents its own. The exception does
not widen the rule anywhere else, and it comes with its own guardrails:

- An expert `CostTemplate`, once attached, always overrides the AI
  estimate — the AI number is a fallback for when no template exists yet,
  never a competing source of truth.
- Every AI-estimated figure is labelled in the memo as an **AI-generated
  INDICATIVE estimate** and carries a `cost_source` field
  (`expert_template` vs `ai_estimate`) — a reader (and any downstream
  code) can always tell which figures are engine-verified and which are
  the model's own estimate.
- Everything *downstream* of the estimate — phasing, present-value
  discounting, headline aggregation, the diff engine — still runs through
  the same deterministic `engine/impact`/`engine/diff` functions as
  template-sourced figures. Only the seed best/likely/worst numbers may
  originate from the model instead of a formula; nothing about how those
  three numbers are then phased, discounted, or summed is allowed to skip
  `engine/`.

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

## 4. One feature per branch; `engine/` changes still need a human merge

Branches are scoped to a single feature or fix — no bundling unrelated
changes to save a review cycle.

Once every CI check on a pull request is green, the agent may merge its own
PR into `main` automatically, without waiting for manual review — with one
exception: any change that touches `backend/engine/` (the pure cost and
applicability calculation logic — see rule #1) still requires a human to
review and merge it by hand, however green the checks are. That's the one
place every number a client sees comes from; nothing merges there on CI
alone.
