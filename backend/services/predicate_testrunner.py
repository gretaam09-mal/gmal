"""Runs a draft (or approved) predicate against the fixture company
profiles in data/fixtures/company_profiles/ — the admin predicate
editor's "test runner" button. Loads fixtures from disk (I/O), then
delegates the actual evaluation to the pure engine/predicates package —
this module is glue, not logic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.predicates import Expression, PredicateOutcome, evaluate_predicate

_FIXTURES_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "fixtures" / "company_profiles"
)


@dataclass(frozen=True)
class PredicateTestResult:
    profile_name: str
    outcome: PredicateOutcome
    missing_field_keys: tuple[str, ...]


def load_fixture_profiles(fixtures_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    directory = fixtures_dir or _FIXTURES_DIR
    return {
        path.stem: json.loads(path.read_text())
        for path in sorted(directory.glob("*.json"))
    }


def run_predicate_against_fixtures(
    expression: Expression, fixture_profiles: dict[str, dict[str, Any]] | None = None
) -> list[PredicateTestResult]:
    profiles = fixture_profiles if fixture_profiles is not None else load_fixture_profiles()
    results = []
    for name, facts in sorted(profiles.items()):
        evaluation = evaluate_predicate(expression, facts)
        results.append(
            PredicateTestResult(
                profile_name=name,
                outcome=evaluation.outcome,
                missing_field_keys=evaluation.missing_field_keys,
            )
        )
    return results
