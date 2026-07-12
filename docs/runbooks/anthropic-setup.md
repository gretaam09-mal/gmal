# Anthropic API setup (P-EXTRACT / P-PREDICATE-ASSIST)

The F3 instrument-onboarding workbench's two AI-assisted steps —
extracting a structured obligation from a clause (`ai/prompts/P-EXTRACT.v1.md`)
and drafting a predicate for expert review (`ai/prompts/P-PREDICATE-ASSIST.v1.md`)
— call the Anthropic API. No test, golden-set case, or the
`scripts/populate_sample_instruments.py` seed script makes a live call —
they all use `FixtureExtractionProvider` /
`FixturePredicateAssistProvider` (see `services/extraction/fixture_provider.py`),
so a key is only needed to actually onboard a *new* instrument through the
admin UI, not to run the test suite or CI.

## What to create

1. Create an account at [console.anthropic.com](https://console.anthropic.com/).
2. Create an API key.

## Where the key goes

Backend (`backend/.env`, not committed):

```
PROVISION_ANTHROPIC_API_KEY=your-key-here
```

Without it, `api/deps.py::get_extraction_provider` /
`get_predicate_assist_provider` construct `AnthropicExtractionProvider` /
`AnthropicPredicateAssistProvider`, which raise a clear "not configured"
error (surfaced to the admin UI as a 502) rather than crashing the app —
same fail-closed shape as `services/companies_house`.

## Staff access to the workbench

The admin workbench (`/admin`) is gated by `User.is_staff`, which is
`False` for everyone by default — there's no self-serve way to become
staff. Grant it to yourself (after signing in once, so a `User` row
exists):

```
cd backend
poetry run python -m scripts.grant_staff you@example.com
```
