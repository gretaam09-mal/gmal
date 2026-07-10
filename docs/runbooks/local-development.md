# Local development

## Backend

```
cd backend
poetry install
poetry run uvicorn api.main:app --reload
```

Health check: `curl http://localhost:8000/health`

Tests: `poetry run pytest`

## Frontend

```
cd frontend
pnpm install
pnpm dev
```

Unit tests: `pnpm test` · E2E smoke test: `pnpm test:e2e`

## Golden set

```
python3 ai/eval/run_golden_set.py
```
