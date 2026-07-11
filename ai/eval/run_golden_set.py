#!/usr/bin/env python3
"""Golden-set regression runner for P-EXTRACT.

Loads every case in ai/golden/cases/*.json and validates its pinned
`input.raw_model_output` (a JSON blob shaped exactly like what P-EXTRACT
— ai/prompts/P-EXTRACT.v1.md — returns for one clause) against
backend/services/extraction/schemas.py::ExtractedObligation, then
asserts the parsed result equals the case's pinned `expected`.

This is a schema/pipeline regression guard, not a live-model eval: there
is no Anthropic API key in CI (see services/extraction/fixture_provider.py
— no test or script in this repo makes a live model call), so what's
actually under test is "does this exact P-EXTRACT-shaped output still
parse into the exact same structured obligation" — a change that breaks
or silently alters that (a tightened Pydantic constraint, a renamed
field, a validator with different rounding, ...) fails the build here,
which is CI wiring for the day a live-model eval is added, not a
replacement for one.

CI (.github/workflows/ci.yml) runs this as a required job — a failure
here blocks the PR the same way pytest/vitest failures do.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from pydantic import ValidationError  # noqa: E402

from services.extraction.schemas import ExtractedObligation  # noqa: E402

REQUIRED_FIELDS = ("id", "input", "expected")


def load_cases(cases_dir: Path) -> list[dict]:
    return [json.loads(path.read_text()) for path in sorted(cases_dir.glob("*.json"))]


def check_case(case: dict) -> list[str]:
    missing = [field for field in REQUIRED_FIELDS if field not in case]
    if missing:
        return [f"missing fields {missing}"]

    raw_output = case["input"].get("raw_model_output")
    if raw_output is None:
        return ["input.raw_model_output is required"]

    try:
        parsed = ExtractedObligation.model_validate(raw_output)
    except ValidationError as exc:
        return [f"raw_model_output failed schema validation: {exc}"]

    actual = parsed.model_dump(mode="json")
    expected = case["expected"]
    if actual != expected:
        return [f"parsed output drifted from expected.\n  actual:   {actual}\n  expected: {expected}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "golden" / "cases",
    )
    args = parser.parse_args()

    cases = load_cases(args.cases_dir)
    if not cases:
        print(f"No golden cases found in {args.cases_dir}", file=sys.stderr)
        return 1

    failures = 0
    for case in cases:
        problems = check_case(case)
        case_id = case.get("id", "<unknown>")
        if problems:
            print(f"FAIL {case_id}:")
            for problem in problems:
                print(f"  {problem}")
            failures += 1
        else:
            print(f"PASS {case_id}")

    print(f"\n{len(cases) - failures}/{len(cases)} golden cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
