#!/usr/bin/env python3
"""Golden-set test runner — Phase 1 stub.

Loads every case in ai/golden/cases/*.json and checks it has the required
shape (id, input, expected). It does not yet invoke any model or compare
real outputs — that lands once extraction/composition prompts exist. Its
job for now is to prove the harness is wired into CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = ("id", "input", "expected")


def load_cases(cases_dir: Path) -> list[dict]:
    return [json.loads(path.read_text()) for path in sorted(cases_dir.glob("*.json"))]


def check_case(case: dict) -> list[str]:
    return [field for field in REQUIRED_FIELDS if field not in case]


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
        missing = check_case(case)
        case_id = case.get("id", "<unknown>")
        if missing:
            print(f"FAIL {case_id}: missing fields {missing}")
            failures += 1
        else:
            print(f"PASS {case_id}")

    print(f"\n{len(cases) - failures}/{len(cases)} golden cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
