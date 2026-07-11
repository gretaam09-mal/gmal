"""Exercises ai/eval/run_golden_set.py from pytest too, not just CI directly
— see docs/CONVENTIONS.md and F3's spec: "a golden-set regression runner
in CI that blocks deployment on extraction regression". This pins the
runner's own pass/fail logic, independent of whichever cases happen to
be checked in at any given time.
"""

import importlib.util
import sys
from pathlib import Path

_RUNNER_PATH = Path(__file__).resolve().parents[3] / "ai" / "eval" / "run_golden_set.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_golden_set", _RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_checked_in_golden_cases_all_pass():
    runner = _load_runner()
    cases_dir = Path(__file__).resolve().parents[3] / "ai" / "golden" / "cases"
    cases = runner.load_cases(cases_dir)
    assert len(cases) >= 3, "expect several real golden cases, not just a placeholder"

    failures = {case["id"]: runner.check_case(case) for case in cases}
    failed = {case_id: problems for case_id, problems in failures.items() if problems}
    assert failed == {}, failed


def test_check_case_rejects_output_that_fails_schema_validation():
    runner = _load_runner()
    case = {
        "id": "bad",
        "input": {"raw_model_output": {"summary": "missing required fields"}},
        "expected": {},
    }
    problems = runner.check_case(case)
    assert problems and "schema validation" in problems[0]


def test_check_case_rejects_a_drifted_expected_value():
    runner = _load_runner()
    valid_output = {
        "summary": "A firm must do a thing.",
        "obligation_type": "generic",
        "who": {"value": "a firm", "clause_ref": "s.1", "confidence": 80},
        "what": {"value": "do a thing", "clause_ref": "s.1", "confidence": 80},
        "when": {"value": "not specified in this clause", "clause_ref": "s.1", "confidence": 10},
        "threshold": {
            "value": "not specified in this clause",
            "clause_ref": "s.1",
            "confidence": 10,
        },
        "enforcer": {
            "value": "not specified in this clause",
            "clause_ref": "s.1",
            "confidence": 10,
        },
        "confidence": 60,
    }
    case = {
        "id": "drifted",
        "input": {"raw_model_output": valid_output},
        "expected": {**valid_output, "confidence": 1},  # deliberately wrong
    }
    problems = runner.check_case(case)
    assert problems and "drifted from expected" in problems[0]


def test_check_case_requires_raw_model_output():
    runner = _load_runner()
    case = {"id": "missing-input", "input": {}, "expected": {}}
    problems = runner.check_case(case)
    assert problems == ["input.raw_model_output is required"]
