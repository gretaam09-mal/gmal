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

**Phase 1**: this is the empty project skeleton. No product features are
implemented yet. See `docs/CONVENTIONS.md` for the non-negotiable rules that
govern everything built on top of it, and `docs/runbooks/local-development.md`
to run everything locally.

Stack: PostgreSQL 16 (+pgvector), a Postgres-backed job queue
(Procrastinate) — no Redis, no Kafka.
