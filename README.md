# Provision

A UK-hosted web app that produces expert-reviewed, quantified
regulatory-exposure memos for private-equity deal teams.

This repository is a monorepo:

- `frontend/` — Next.js (App Router) + TypeScript + Tailwind + shadcn/ui
- `backend/` — Python 3.12 + FastAPI + SQLAlchemy + Alembic + Pydantic
- `ai/` — prompts, golden set, evaluation
- `data/` — fixtures
- `infra/` — infrastructure-as-code stubs (AWS `eu-west-2`) and CI scripts
- `docs/` — runbooks and `CONVENTIONS.md`

Built so far: workspaces, Clerk authentication, roles and audit logging
(F1); an entity profile with Companies House auto-fill (F2); an internal,
staff-only instrument-onboarding workbench — clause segmentation,
P-EXTRACT obligation extraction, expert review/approval, a predicate
editor with P-PREDICATE-ASSIST drafting, cost templates, and a golden-set
regression runner (F3); and the applicability engine — a pure tri-state
predicate evaluator, deterministic rationale assembly, and an Exposure
List screen (F4). See `docs/CONVENTIONS.md` for the non-negotiable rules
that govern everything built on top of it, and
`docs/runbooks/local-development.md` to run everything locally.

Stack: PostgreSQL 16 (+pgvector), a Postgres-backed job queue
(Procrastinate) — no Redis, no Kafka.
