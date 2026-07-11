# Golden set

Fixed input/expected-output pairs used to regression-test P-EXTRACT. Each
case is a JSON file matching `case.schema.json`: `input.raw_model_output`
is a pinned JSON blob shaped exactly like what P-EXTRACT
(`ai/prompts/P-EXTRACT.v1.md`) returns for one clause, and `expected` is
what `ExtractedObligation.model_validate(...).model_dump()` must still
produce from it.

There is no Anthropic API key in CI, so this cannot be a live-model eval
— no test or script in this repo makes a live model call (see
`backend/services/extraction/fixture_provider.py`). What it *does* catch
is a regression in the extraction schema or pipeline itself: a tightened
Pydantic constraint, a renamed field, a validator that rounds
differently — anything that would silently change what a clause extracts
to. `ai/eval/run_golden_set.py` runs every case and fails (non-zero exit)
on the first mismatch; CI (`.github/workflows/ci.yml`, job `golden-set`)
runs it as a required check, same as pytest/vitest.

Four cases today, each pinning something the schema must keep handling
correctly:
- `dpo-appointment` — the common case, one clause with several distinct
  citations (a real regulatory clause is rarely one single reference).
- `client-money-segregation` — every field cites the *same* clause, and
  `when` is genuinely `"not specified in this clause"` rather than a
  guess (P-EXTRACT rule 3).
- `breach-reporting-low-confidence` — several fields with low (not zero)
  confidence, pinning that the schema accepts the full 0-100 range rather
  than silently clamping or rejecting low scores.
- `hazardous-materials-disclosure` — a natural-language threshold
  ("more than 1 tonne...") stored as extracted text, never parsed into a
  number here (CONVENTIONS.md rule 1 — that's engine/predicates's job at
  analysis time, not P-EXTRACT's).
