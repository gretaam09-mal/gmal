# Golden set

Fixed input/expected-output pairs used to regression-test extraction and
composition prompts. Each case is a JSON file matching `case.schema.json`.

Empty in Phase 1 beyond the schema and one placeholder case, which the
golden-set runner (`ai/eval/run_golden_set.py`) uses to prove the harness
works end to end.
