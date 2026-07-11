# Local development

## Database

Provision needs PostgreSQL 16 with the pgvector extension. Locally:

```
sudo apt-get install -y postgresql-16 postgresql-16-pgvector   # or your platform's equivalent
sudo -u postgres psql -c "CREATE ROLE provision LOGIN PASSWORD 'provision';"
sudo -u postgres psql -c "CREATE DATABASE provision OWNER provision;"
sudo -u postgres psql -d provision -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -d provision -c "GRANT ALL ON SCHEMA public TO provision;"
```

The `provision` role must **not** be a superuser — Row-Level Security (see
`backend/db/migrations/versions/*_row_level_security.py`) is bypassed
unconditionally for superusers, which would silently defeat tenant
isolation locally. `CREATE ROLE ... LOGIN PASSWORD ...` is non-superuser by
default, so just don't add `SUPERUSER`.

Apply migrations:

```
cd backend
poetry run alembic upgrade head
```

Tests use a second database, `provision_test`, created the same way (swap
`provision` for `provision_test` in the two `-c` commands above) — the test
suite migrates it automatically on each run (see `backend/tests/conftest.py`).

## Backend

```
cd backend
poetry install
poetry run uvicorn api.main:app --reload
```

Health check: `curl http://localhost:8000/health`

Tests: `poetry run pytest` · Lint: `poetry run ruff check .`

See `docs/runbooks/clerk-setup.md` and `docs/runbooks/companies-house-setup.md`
for the API keys the backend needs to actually authenticate users or fetch
Companies House data (not required to run the test suite).

## Frontend

```
cd frontend
pnpm install
pnpm dev
```

Unit tests: `pnpm test` · E2E smoke test: `pnpm test:e2e`

See `docs/runbooks/clerk-setup.md` for `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
and `CLERK_SECRET_KEY` — without them, sign-in/sign-up show a
"not configured" placeholder instead of crashing.

## Golden set

```
python3 ai/eval/run_golden_set.py
```
