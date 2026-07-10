from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PredicateResult:
    """Outcome of evaluating a single predicate against deal facts."""

    predicate_id: str
    matched: bool


class Predicate(Protocol):
    """A pure, deterministic rule: facts in, a matched/unmatched result out."""

    def evaluate(self, facts: dict[str, object]) -> PredicateResult: ...
