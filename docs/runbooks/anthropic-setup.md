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
staff. Grant it to yourself (after signing in once, so a `User` row
exists):

```
cd backend
poetry run python -m scripts.grant_staff you@example.com
```
